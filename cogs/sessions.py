import os
from datetime import datetime, timezone

import discord
from discord.ext import commands
from discord import app_commands

from utils import db
from utils.warhorn_api import WarhornClient

WARHORN_SLUG = "pandodnd"
WARHORN_API_ENDPOINT = "https://warhorn.net/graphql"
DAN_TEXT_CHANNEL_ID = 701628514004238416
DAN_SESSION_LOGS_CHANNEL_ID = 1324201074382344213
REWARDS_STATIC = "10 downtime, level if you want it"
DEFAULT_STREAMING = "2 hours streaming"


class Sessions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.warhorn_client = WarhornClient(WARHORN_API_ENDPOINT, os.getenv("WARHORN_APPLICATION_TOKEN"))

    async def _get_channel(self, channel_id: int):
        channel = self.bot.get_channel(channel_id)
        if not channel:
            channel = await self.bot.fetch_channel(channel_id)
        return channel

    def _warhorn_next_session_name(self) -> str | None:
        try:
            result = self.warhorn_client.get_event_sessions(WARHORN_SLUG)
            nodes = result.get("data", {}).get("eventSessions", {}).get("nodes", [])
        except Exception as e:
            print(f"[Sessions] Warhorn fetch failed: {e}")
            return None

        if not nodes:
            return None

        session = min(nodes, key=lambda x: datetime.fromisoformat(x["startsAt"].replace("Z", "+00:00")))
        return session.get("name")

    def _derive_adventure_name(self) -> str | None:
        latest = db.get_latest_session()
        if latest and latest.get("session_name"):
            return latest["session_name"]
        return self._warhorn_next_session_name()

    @staticmethod
    def _format_rewards_message(rewards: str, adventure: str | None, streaming: str) -> str:
        rewards = rewards.strip()
        if REWARDS_STATIC in rewards:
            return rewards

        if not adventure:
            raise ValueError("no_adventure")

        return f"{adventure}, {REWARDS_STATIC}, {streaming}, {rewards}"

    @app_commands.command(name="gotime", description="Log the current session with everyone in your voice channel.")
    @app_commands.checks.has_permissions(administrator=True)
    async def gotime(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.followup.send("You need to be in a voice channel to run this.", ephemeral=True)
            return

        voice_channel = interaction.user.voice.channel
        human_members = [m for m in voice_channel.members if not m.bot]

        if not human_members:
            await interaction.followup.send("No players found in your voice channel.", ephemeral=True)
            return

        try:
            result = self.warhorn_client.get_event_sessions(WARHORN_SLUG)
            nodes = result.get("data", {}).get("eventSessions", {}).get("nodes", [])
        except Exception as e:
            await interaction.followup.send(f"Failed to fetch Warhorn sessions: {e}", ephemeral=True)
            return

        if not nodes:
            await interaction.followup.send("No upcoming Warhorn sessions found.", ephemeral=True)
            return

        session = min(nodes, key=lambda x: datetime.fromisoformat(x["startsAt"].replace("Z", "+00:00")))
        starts_at = datetime.fromisoformat(session["startsAt"].replace("Z", "+00:00"))

        player_data = []
        for member in human_members:
            selection = db.get_character_selection(member.id)
            player_data.append({
                "user_id": member.id,
                "display_name": member.display_name,
                "character_url": selection["character_url"] if selection else None,
                "character_name": selection["character_name"] if selection else None,
            })

        session_db_id = db.upsert_session(
            session["id"],
            session["name"],
            starts_at,
            voice_channel.id,
            interaction.user.id,
        )
        for player in player_data:
            db.upsert_session_player(
                session_db_id,
                player["user_id"],
                player["display_name"],
                player["character_url"],
                player["character_name"],
            )

        db.clear_character_selections([p["user_id"] for p in player_data])

        unix_ts = int(starts_at.timestamp())
        embed = discord.Embed(
            title=f"Session logged: {session['name']}",
            color=discord.Color.green(),
        )
        embed.add_field(name="When", value=f"<t:{unix_ts}:F>", inline=False)

        unknown = []
        lines = []
        for p in player_data:
            if p["character_url"]:
                lines.append(f"• {p['display_name']} → [{p['character_name']}]({p['character_url']})")
            else:
                lines.append(f"• {p['display_name']} → Unknown")
                unknown.append(p["display_name"])
        embed.add_field(name=f"Players ({len(player_data)})", value="\n".join(lines), inline=False)

        if unknown:
            embed.set_footer(text=f"No character set: {', '.join(unknown)} — use /character play to set yours!")

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="rewards", description="Post session rewards to #dan-session-logs and link in #dan-text.")
    @app_commands.describe(
        rewards="Gold and magic items (e.g. `116.67gp each, ring of protection (guardian), scroll of tongues`)",
        adventure="Adventure name (defaults to the latest /gotime session)",
        streaming="Streaming time (defaults to `2 hours streaming`)",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def rewards(
        self,
        interaction: discord.Interaction,
        rewards: str,
        adventure: str | None = None,
        streaming: str = DEFAULT_STREAMING,
    ):
        await interaction.response.defer(ephemeral=True)

        resolved_adventure = adventure or self._derive_adventure_name()

        try:
            message_text = self._format_rewards_message(rewards, resolved_adventure, streaming)
        except ValueError:
            await interaction.followup.send(
                "Could not determine the adventure name. Run `/gotime` first or pass the `adventure` option.",
                ephemeral=True,
            )
            return

        try:
            logs_channel = await self._get_channel(DAN_SESSION_LOGS_CHANNEL_ID)
            text_channel = await self._get_channel(DAN_TEXT_CHANNEL_ID)
        except Exception as e:
            await interaction.followup.send(f"Could not access a target channel: {e}", ephemeral=True)
            return

        logs_message = await logs_channel.send(message_text)

        adventure_label = resolved_adventure or message_text.split(",")[0]
        await text_channel.send(
            f"📋 **Rewards posted** for {adventure_label} → {logs_message.jump_url}"
        )

        await interaction.followup.send(
            f"Posted rewards to {logs_channel.mention} and linked in {text_channel.mention}.",
            ephemeral=True,
        )

    @gotime.error
    async def gotime_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("Only the GM can run this command.", ephemeral=True)

    @rewards.error
    async def rewards_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("Only the GM can run this command.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Sessions(bot))
