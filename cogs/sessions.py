import os
from datetime import datetime, timezone

import discord
from discord.ext import commands
from discord import app_commands

from utils import db
from utils.warhorn_api import WarhornClient

WARHORN_SLUG = "pandodnd"
WARHORN_API_ENDPOINT = "https://warhorn.net/graphql"


class Sessions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.warhorn_client = WarhornClient(WARHORN_API_ENDPOINT, os.getenv("WARHORN_APPLICATION_TOKEN"))

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

    @gotime.error
    async def gotime_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("Only the GM can run this command.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Sessions(bot))
