import os

import discord
from discord.ext import commands
from discord import app_commands

from utils import db
from utils.session_format import build_gotime_embed
from utils.warhorn_api import (
    WarhornClient,
    find_current_session,
    parse_warhorn_dt,
)

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

        session = min(nodes, key=lambda x: parse_warhorn_dt(x["startsAt"]))
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

    def _fetch_current_warhorn_session(self) -> tuple[dict | None, str | None]:
        try:
            result = self.warhorn_client.get_sessions_for_gotime(WARHORN_SLUG)
            nodes = result.get("data", {}).get("eventSessions", {}).get("nodes", [])
        except Exception as e:
            return None, f"Failed to fetch Warhorn sessions: {e}"

        if not nodes:
            return None, "No Warhorn sessions found for today."

        session = find_current_session(nodes)
        if not session:
            return None, "Could not determine the current Warhorn session."

        return session, None

    @staticmethod
    def _collect_voice_players(voice_channel) -> list[dict]:
        player_data = []
        for member in voice_channel.members:
            if member.bot:
                continue
            selection = db.get_character_selection(member.id)
            player_data.append({
                "user_id": member.id,
                "display_name": member.display_name,
                "character_url": selection["character_url"] if selection else None,
                "character_name": selection["character_name"] if selection else None,
            })
        return player_data

    @staticmethod
    def _collect_wishlist_players(warhorn_session_id: str, exclude_user_ids: set[int]) -> list[dict]:
        wishlist = []
        for entry in db.get_session_wishlist(warhorn_session_id):
            user_id = entry["discord_user_id"]
            if user_id in exclude_user_ids:
                continue
            selection = db.get_character_selection(user_id)
            wishlist.append({
                "user_id": user_id,
                "display_name": entry["display_name"],
                "character_url": selection["character_url"] if selection else None,
                "character_name": selection["character_name"] if selection else None,
            })
        return wishlist

    async def _run_gotime(self, interaction: discord.Interaction, *, preview: bool):
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.followup.send("You need to be in a voice channel to run this.", ephemeral=True)
            return

        voice_channel = interaction.user.voice.channel
        player_data = self._collect_voice_players(voice_channel)

        if not player_data:
            await interaction.followup.send("No players found in your voice channel.", ephemeral=True)
            return

        if not preview:
            cleared = db.clear_stale_session_selections()
            if cleared:
                print(f"[Sessions] Cleared {cleared} stale character selection(s) from prior sessions.")

        session, error = self._fetch_current_warhorn_session()
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        voice_user_ids = {p["user_id"] for p in player_data}
        wishlist_data = self._collect_wishlist_players(session["id"], voice_user_ids)

        if not preview:
            starts_at = parse_warhorn_dt(session["startsAt"])
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
            db.clear_session_wishlist(session["id"])

        embed = build_gotime_embed(
            session,
            player_data,
            preview=preview,
            wishlist_data=wishlist_data,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="wishlist",
        description="Request a spot in the upcoming session, or remove yourself from the wishlist.",
    )
    @app_commands.describe(
        player="Another player to add or remove (admin only)",
        remove="Remove from the wishlist instead of adding",
    )
    async def wishlist(
        self,
        interaction: discord.Interaction,
        player: discord.Member | None = None,
        remove: bool = False,
    ):
        if player and player.id != interaction.user.id:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "Only admins can manage another player's wishlist entry.",
                    ephemeral=True,
                )
                return

        if player and player.bot:
            await interaction.response.send_message("Bots can't be wishlisted.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        session, error = self._fetch_current_warhorn_session()
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        target = player or interaction.user
        added_by_other = target.id != interaction.user.id
        starts_at = parse_warhorn_dt(session["startsAt"])
        unix_ts = int(starts_at.timestamp())

        if remove:
            if not db.remove_session_wishlist(session["id"], target.id):
                await interaction.followup.send(
                    f"{target.display_name} is not on the wishlist for **{session['name']}**.",
                    ephemeral=True,
                )
                return

            if added_by_other:
                message = (
                    f"Removed {target.display_name} from the wishlist for **{session['name']}** "
                    f"(<t:{unix_ts}:F>)."
                )
            else:
                message = f"You've been removed from the wishlist for **{session['name']}** (<t:{unix_ts}:F>)."
            await interaction.followup.send(message, ephemeral=True)
            return

        newly_added = db.add_session_wishlist(
            session["id"],
            target.id,
            target.display_name,
            interaction.user.id,
        )

        if not newly_added:
            await interaction.followup.send(
                f"{target.display_name} is already on the wishlist for **{session['name']}** (<t:{unix_ts}:F>).",
                ephemeral=True,
            )
            return

        selection = db.get_character_selection(target.id)
        character_note = ""
        if selection:
            character_note = f" Character: [{selection['character_name']}]({selection['character_url']})."
        elif not added_by_other:
            character_note = " Use `/character play` to set your character before session time."

        if added_by_other:
            message = (
                f"Added {target.display_name} to the wishlist for **{session['name']}** "
                f"(<t:{unix_ts}:F>).{character_note}"
            )
        else:
            message = (
                f"You're on the wishlist for **{session['name']}** (<t:{unix_ts}:F>).{character_note} "
                "Run `/wishlist remove:true` to take yourself off."
            )
        await interaction.followup.send(message, ephemeral=True)

    @app_commands.command(name="gotime", description="Log the current session with everyone in your voice channel.")
    @app_commands.checks.has_permissions(administrator=True)
    async def gotime(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self._run_gotime(interaction, preview=False)

    @app_commands.command(
        name="gotime-preview",
        description="Preview what /gotime would log without saving or clearing character selections.",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def gotime_preview(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self._run_gotime(interaction, preview=True)

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

    @gotime_preview.error
    async def gotime_preview_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("Only the GM can run this command.", ephemeral=True)

    @rewards.error
    async def rewards_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("Only the GM can run this command.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Sessions(bot))
