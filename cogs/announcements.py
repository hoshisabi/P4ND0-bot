import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from utils import db
from utils.warhorn_api import WarhornClient, parse_warhorn_dt

EASTERN = ZoneInfo("America/New_York")
WARHORN_SLUG = "pandodnd"
WARHORN_API_ENDPOINT = "https://warhorn.net/graphql"
DAN_TEXT_CHANNEL_ID = 701628514004238416
ANNOUNCEMENT_WINDOW = timedelta(minutes=15)

ABILITIES_TEXT = (
    "**What can P4ND0 do?**\n"
    "• `/character add` — save a D&D Beyond character to your profile\n"
    "• `/character list` — see your saved characters\n"
    "• `/character play` — set which character you're using for the next session\n"
    "• `/schedule` — view upcoming Warhorn events\n"
    "*Use `/help` for the full command list.*"
)


class Announcements(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.warhorn_client = WarhornClient(WARHORN_API_ENDPOINT, os.getenv("WARHORN_APPLICATION_TOKEN"))
        self.check_announcements.start()

    def cog_unload(self):
        self.check_announcements.cancel()

    @tasks.loop(minutes=2)
    async def check_announcements(self):
        if not self.bot.is_ready():
            return

        now = datetime.now(EASTERN)

        try:
            result = self.warhorn_client.get_sessions_for_gotime(WARHORN_SLUG, now=now.astimezone(timezone.utc))
            nodes = result.get("data", {}).get("eventSessions", {}).get("nodes", [])
        except Exception as e:
            print(f"[Announcements] Failed to fetch Warhorn sessions: {e}")
            return

        channel = self.bot.get_channel(DAN_TEXT_CHANNEL_ID)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(DAN_TEXT_CHANNEL_ID)
            except Exception as e:
                print(f"[Announcements] Could not fetch channel {DAN_TEXT_CHANNEL_ID}: {e}")
                return

        today_session = next(
            (s for s in nodes if parse_warhorn_dt(s["startsAt"]).astimezone(EASTERN).date() == now.date()),
            None,
        )

        await self._check_noon(now, channel, today_session)

        if today_session:
            await self._check_session_reminders(now, channel, today_session)

    async def _check_noon(self, now, channel, today_session):
        if not today_session:
            return

        noon = now.replace(hour=12, minute=0, second=0, microsecond=0)
        if not (noon <= now < noon + ANNOUNCEMENT_WINDOW):
            return

        sentinel = today_session["id"]
        if db.has_announcement_fired(sentinel, "day_of_noon"):
            return

        embed = self._session_embed(today_session, title_prefix="Today's session")
        embed.add_field(name="​", value=ABILITIES_TEXT, inline=False)
        await channel.send(embed=embed)

        db.mark_announcement_fired(sentinel, "day_of_noon")
        print(f"[Announcements] Fired day_of_noon for {sentinel}")

    async def _check_session_reminders(self, now, channel, session):
        starts_at = parse_warhorn_dt(session["startsAt"]).astimezone(EASTERN)
        session_id = session["id"]
        unix_ts = int(starts_at.timestamp())
        name = session["name"]

        reminders = [
            ("one_hour",      starts_at - timedelta(hours=1),   f"⚔️ **{name}** starts in **1 hour** (<t:{unix_ts}:t>)! Use `/character play` to set your character."),
            ("ten_minutes",   starts_at - timedelta(minutes=10), f"⚔️ **{name}** starts in **10 minutes**! (<t:{unix_ts}:t>)"),
            ("starting",      starts_at,                         f"🎲 **{name}** is **starting now**! Good luck everyone!"),
        ]

        for ann_type, target, message in reminders:
            if target <= now < target + ANNOUNCEMENT_WINDOW:
                if not db.has_announcement_fired(session_id, ann_type):
                    await channel.send(message)
                    db.mark_announcement_fired(session_id, ann_type)
                    print(f"[Announcements] Fired {ann_type} for {session_id}")

    def _session_embed(self, session, title_prefix="Session"):
        name = session["name"]
        uuid = session.get("uuid")
        url = (
            f"https://warhorn.net/events/{WARHORN_SLUG}/schedule/sessions/{uuid}"
            if uuid else
            f"https://warhorn.net/events/{WARHORN_SLUG}/schedule"
        )
        starts_at = parse_warhorn_dt(session["startsAt"]).astimezone(EASTERN)
        unix_ts = int(starts_at.timestamp())
        gm = session["gmSignups"][0]["user"]["name"] if session.get("gmSignups") else "TBD"

        embed = discord.Embed(
            title=f"{title_prefix}: {name}",
            url=url,
            color=discord.Color.blue(),
        )
        embed.add_field(name="When", value=f"<t:{unix_ts}:F>", inline=True)
        embed.add_field(name="GM", value=gm, inline=True)

        players = [s["user"]["name"] for s in session.get("playerSignups", [])]
        if players:
            embed.add_field(name="Players", value=", ".join(players), inline=False)

        available = session.get("availablePlayerSeats", 0)
        waitlist = [e["user"]["name"] for e in session.get("playerWaitlistEntries", []) if e.get("user")]
        if available > 0:
            embed.add_field(name="Open seats", value=str(available), inline=True)
        elif waitlist:
            embed.add_field(name="Waitlist", value=", ".join(waitlist), inline=True)

        return embed

    @discord.app_commands.command(name="announce", description="Post the P4ND0 abilities ad (with today's session if there is one).")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def announce(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        now = datetime.now(EASTERN)
        today_session = None
        try:
            result = self.warhorn_client.get_sessions_for_gotime(WARHORN_SLUG, now=now.astimezone(timezone.utc))
            nodes = result.get("data", {}).get("eventSessions", {}).get("nodes", [])
            today_session = next(
                (s for s in nodes if parse_warhorn_dt(s["startsAt"]).astimezone(EASTERN).date() == now.date()),
                None,
            )
        except Exception as e:
            print(f"[Announcements] /announce Warhorn fetch failed: {e}")

        channel = self.bot.get_channel(DAN_TEXT_CHANNEL_ID)
        if not channel:
            channel = await self.bot.fetch_channel(DAN_TEXT_CHANNEL_ID)

        if today_session:
            embed = self._session_embed(today_session, title_prefix="Today's session")
            embed.add_field(name="​", value=ABILITIES_TEXT, inline=False)
        else:
            embed = discord.Embed(description=ABILITIES_TEXT, color=discord.Color.blurple())

        await channel.send(embed=embed)
        await interaction.followup.send("Posted.", ephemeral=True)

    @announce.error
    async def announce_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        if isinstance(error, discord.app_commands.MissingPermissions):
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)

    @check_announcements.before_loop
    async def before_check_announcements(self):
        await self.bot.wait_until_ready()
        print("[Announcements] Loop ready.")


async def setup(bot):
    await bot.add_cog(Announcements(bot))
