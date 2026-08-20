import os

import discord
from discord.ext import commands
from discord import app_commands

from utils import db
from utils.log import log
from utils.session_format import build_gotime_embed
from utils.warhorn_api import (
    WarhornClient,
    find_current_session,
    parse_warhorn_dt,
)
from utils.wishlist_format import (
    build_browse_catalog,
    build_wishlist_catalog,
    format_browse_catalog,
    format_trim_result,
    match_wishlist_adventure,
    plan_wishlist_trim,
    resolve_wishlist_number,
)

WARHORN_SLUG = "pandodnd"
WARHORN_API_ENDPOINT = "https://warhorn.net/graphql"
DAN_TEXT_CHANNEL_ID = 701628514004238416
DAN_SESSION_LOGS_CHANNEL_ID = 1324201074382344213
REWARDS_STATIC = "10 downtime, level if you want it"
DEFAULT_STREAMING = "2 hours streaming"


def _format_user_wishlist(entries: list[dict]) -> str:
    if not entries:
        return "*Nothing wishlisted yet.*"
    return "\n".join(f"• {entry['adventure']}" for entry in entries)


def _format_all_wishlists(entries: list[dict]) -> str:
    catalog = build_wishlist_catalog(entries)
    if not catalog:
        return "*No wishlist entries yet.*"

    sections = []
    for item in catalog:
        names = ", ".join(item["requesters"])
        sections.append(f"**{item['adventure']}**\n{names}")
    return "\n\n".join(sections)


def _wishlist_browse_embed(*, include_requesters: bool = False) -> discord.Embed | None:
    catalog = _wishlist_browse_catalog()
    if not catalog:
        return None

    body = format_browse_catalog(catalog, include_requesters=include_requesters)
    if len(body) > 4000:
        body = body[:3997] + "..."

    embed = discord.Embed(
        title="Adventure Wishlist",
        description=body,
        color=discord.Color.gold(),
    )
    embed.set_footer(
        text="Use /wishlist add number:N to join a request or pick a recent session, or adventure:... for something new."
    )
    return embed


def _wishlist_browse_catalog() -> list[dict]:
    return build_browse_catalog(db.get_adventure_wishlist(), db.get_recent_warhorn_sessions(limit=8))


class Sessions(commands.Cog):
    wishlist_group = app_commands.Group(
        name="wishlist",
        description="Request adventures you'd like the GM to run someday.",
    )
    def __init__(self, bot):
        self.bot = bot
        self.warhorn_client = WarhornClient(WARHORN_API_ENDPOINT, os.getenv("WARHORN_APPLICATION_TOKEN"))

    async def _get_channel(self, channel_id: int):
        channel = self.bot.get_channel(channel_id)
        if not channel:
            channel = await self.bot.fetch_channel(channel_id)
        return channel

    def _warhorn_current_session_name(self) -> str | None:
        try:
            result = self.warhorn_client.get_sessions_for_gotime(WARHORN_SLUG)
            nodes = result.get("data", {}).get("eventSessions", {}).get("nodes", [])
        except Exception as e:
            log(f"[Sessions] Warhorn fetch failed: {e}")
            return None

        if not nodes:
            return None

        session = find_current_session(nodes)
        return session.get("name") if session else None

    def _derive_adventure_name(self, rewards_session: dict | None = None) -> str | None:
        session = rewards_session if rewards_session is not None else db.get_rewards_session()
        if session and session.get("session_name"):
            return session["session_name"]
        return self._warhorn_current_session_name()

    @staticmethod
    def _format_participant_mentions(participant_ids: list[int]) -> str:
        if not participant_ids:
            return ""
        return " ".join(f"<@{user_id}>" for user_id in participant_ids)

    @staticmethod
    def _format_rewards_message(
        rewards: str,
        adventure: str | None,
        streaming: str,
        *,
        participant_ids: list[int] | None = None,
    ) -> str:
        rewards = rewards.strip()
        if REWARDS_STATIC in rewards:
            message = rewards
        elif not adventure:
            raise ValueError("no_adventure")
        else:
            message = f"{adventure}, {REWARDS_STATIC}, {streaming}, {rewards}"

        mentions = Sessions._format_participant_mentions(participant_ids or [])
        if mentions:
            message = f"{message}\n{mentions}"
        return message

    def _fetch_current_warhorn_session(self) -> tuple[dict | None, str | None]:
        try:
            result = self.warhorn_client.get_sessions_for_gotime(WARHORN_SLUG)
            nodes = result.get("data", {}).get("eventSessions", {}).get("nodes", [])
        except Exception as e:
            return None, f"Failed to fetch Warhorn sessions: {e}"

        if not nodes:
            return None, "No Warhorn sessions found for today."

        db.record_warhorn_sessions(nodes)

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
                log(f"[Sessions] Cleared {cleared} stale character selection(s) from prior sessions.")

        session, error = self._fetch_current_warhorn_session()
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

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

        embed = build_gotime_embed(session, player_data, preview=preview)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @wishlist_group.command(name="browse", description="View adventures others have requested, numbered for easy joining.")
    async def wishlist_browse(self, interaction: discord.Interaction):
        is_admin = bool(interaction.user.guild_permissions.administrator)
        embed = _wishlist_browse_embed(include_requesters=is_admin)
        if not embed:
            await interaction.response.send_message(
                "No adventures on the wishlist yet. Use `/wishlist add adventure:...` to request one.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @wishlist_group.command(name="add", description="Add an adventure to the wishlist.")
    @app_commands.describe(
        adventure="Adventure name (freeform text)",
        number="Join an existing request by number from /wishlist browse",
        player="Another player to add for (admin only)",
    )
    async def wishlist_add(
        self,
        interaction: discord.Interaction,
        adventure: str | None = None,
        number: int | None = None,
        player: discord.Member | None = None,
    ):
        if adventure and number is not None:
            await interaction.response.send_message(
                "Provide either `adventure` or `number`, not both.",
                ephemeral=True,
            )
            return

        if adventure is None and number is None:
            is_admin = bool(interaction.user.guild_permissions.administrator)
            embed = _wishlist_browse_embed(include_requesters=is_admin)
            if not embed:
                await interaction.response.send_message(
                    "No adventures on the wishlist yet. Use `/wishlist add adventure:...` to request one.",
                    ephemeral=True,
                )
                return
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if number is not None:
            catalog = _wishlist_browse_catalog()
            resolved = resolve_wishlist_number(catalog, number)
            if not resolved:
                await interaction.response.send_message(
                    f"Invalid number. Use `/wishlist browse` to see options 1–{len(catalog)}.",
                    ephemeral=True,
                )
                return
            adventure = resolved
        else:
            adventure = adventure.strip()
            if not adventure:
                await interaction.response.send_message("Please provide an adventure name.", ephemeral=True)
                return

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

        target = player or interaction.user
        added_by_other = target.id != interaction.user.id

        newly_added = db.add_adventure_wishlist(
            target.id,
            adventure,
            target.display_name,
            interaction.user.id,
        )

        if not newly_added:
            await interaction.response.send_message(
                f"{target.display_name} already wishlisted **{adventure}**.",
                ephemeral=True,
            )
            return

        if added_by_other:
            message = f"Added **{adventure}** to {target.display_name}'s wishlist."
        else:
            message = (
                f"Added **{adventure}** to your wishlist. "
                f"Use `/wishlist remove adventure:{adventure}` to take it off."
            )
        await interaction.response.send_message(message, ephemeral=True)

    @wishlist_group.command(name="remove", description="Remove an adventure from the wishlist.")
    @app_commands.describe(
        adventure="The adventure name to remove",
        player="Another player to remove for (admin only)",
    )
    async def wishlist_remove(
        self,
        interaction: discord.Interaction,
        adventure: str,
        player: discord.Member | None = None,
    ):
        adventure = adventure.strip()
        if not adventure:
            await interaction.response.send_message("Please provide an adventure name.", ephemeral=True)
            return

        if player and player.id != interaction.user.id:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "Only admins can manage another player's wishlist entry.",
                    ephemeral=True,
                )
                return

        target = player or interaction.user
        added_by_other = target.id != interaction.user.id

        if not db.remove_adventure_wishlist(target.id, adventure):
            await interaction.response.send_message(
                f"{target.display_name} hasn't wishlisted **{adventure}**.",
                ephemeral=True,
            )
            return

        if added_by_other:
            message = f"Removed **{adventure}** from {target.display_name}'s wishlist."
        else:
            message = f"Removed **{adventure}** from your wishlist."
        await interaction.response.send_message(message, ephemeral=True)

    @wishlist_group.command(name="list", description="View adventure wishlist entries.")
    @app_commands.describe(
        all="Show every wishlist entry (admin only)",
        player="View another player's list (admin only)",
    )
    async def wishlist_list(
        self,
        interaction: discord.Interaction,
        all: bool = False,
        player: discord.Member | None = None,
    ):
        is_admin = bool(
            interaction.guild and interaction.user.guild_permissions.administrator
        )

        if all:
            if not is_admin:
                await interaction.response.send_message(
                    "Only admins can view the full wishlist.",
                    ephemeral=True,
                )
                return

            entries = db.get_adventure_wishlist()
            body = _format_all_wishlists(entries)
            title = "Adventure Wishlist"
        elif player and player.id != interaction.user.id:
            if not is_admin:
                await interaction.response.send_message(
                    "Only admins can view another player's wishlist.",
                    ephemeral=True,
                )
                return

            entries = db.get_adventure_wishlist_for_user(player.id)
            body = _format_user_wishlist(entries)
            title = f"{player.display_name}'s Wishlist"
        else:
            entries = db.get_adventure_wishlist_for_user(interaction.user.id)
            body = _format_user_wishlist(entries)
            title = "Your Adventure Wishlist"

        if len(body) > 4000:
            body = body[:3997] + "..."

        embed = discord.Embed(title=title, description=body, color=discord.Color.gold())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def trim_adventure_autocomplete(self, interaction: discord.Interaction, current: str):
        catalog = build_wishlist_catalog(db.get_adventure_wishlist())
        current_lower = current.lower()
        choices = []
        for item in catalog:
            name = item["adventure"]
            if current_lower and current_lower not in name.lower():
                continue
            choices.append(app_commands.Choice(name=name[:100], value=name[:100]))
            if len(choices) >= 25:
                break
        return choices

    @staticmethod
    def _unique_members(members: list[discord.Member | None]) -> list[discord.Member]:
        unique: list[discord.Member] = []
        seen: set[int] = set()
        for member in members:
            if member is None or member.id in seen:
                continue
            seen.add(member.id)
            unique.append(member)
        return unique

    @wishlist_group.command(
        name="trim",
        description="After a session, remove an adventure, selected players, or everyone except keep.",
    )
    @app_commands.describe(
        adventure="Adventure to trim (defaults to the latest /gotime session)",
        number="Adventure number from /wishlist browse",
        player="Remove this player instead of everyone listed",
        player2="Another player to remove",
        player3="Another player to remove",
        player4="Another player to remove",
        player5="Another player to remove",
        keep="Leave this player on the list; remove everyone else",
        keep2="Another player to leave on the list",
        keep3="Another player to leave on the list",
        keep4="Another player to leave on the list",
        keep5="Another player to leave on the list",
    )
    @app_commands.autocomplete(adventure=trim_adventure_autocomplete)
    @app_commands.checks.has_permissions(administrator=True)
    async def wishlist_trim(
        self,
        interaction: discord.Interaction,
        adventure: str | None = None,
        number: int | None = None,
        player: discord.Member | None = None,
        player2: discord.Member | None = None,
        player3: discord.Member | None = None,
        player4: discord.Member | None = None,
        player5: discord.Member | None = None,
        keep: discord.Member | None = None,
        keep2: discord.Member | None = None,
        keep3: discord.Member | None = None,
        keep4: discord.Member | None = None,
        keep5: discord.Member | None = None,
    ):
        if adventure and number is not None:
            await interaction.response.send_message(
                "Provide either `adventure` or `number`, not both.",
                ephemeral=True,
            )
            return

        if adventure is not None:
            adventure = adventure.strip()
            if not adventure:
                await interaction.response.send_message("Please provide an adventure name.", ephemeral=True)
                return
        elif number is not None:
            catalog = _wishlist_browse_catalog()
            resolved = resolve_wishlist_number(catalog, number)
            if not resolved:
                await interaction.response.send_message(
                    f"Invalid number. Use `/wishlist browse` to see options 1–{len(catalog)}.",
                    ephemeral=True,
                )
                return
            adventure = resolved
        else:
            session_name = self._derive_adventure_name()
            if not session_name:
                await interaction.response.send_message(
                    "Could not determine the adventure. Pass `adventure` or `number`, or run `/gotime` first.",
                    ephemeral=True,
                )
                return
            matched = match_wishlist_adventure(
                build_wishlist_catalog(db.get_adventure_wishlist()),
                session_name,
            )
            if not matched:
                await interaction.response.send_message(
                    f"Could not match the latest session **{session_name}** to a wishlist adventure. "
                    "Pass `adventure` or `number`.",
                    ephemeral=True,
                )
                return
            adventure = matched

        remove_targets = self._unique_members([player, player2, player3, player4, player5])
        keep_targets = self._unique_members([keep, keep2, keep3, keep4, keep5])
        remove_humans = [member for member in remove_targets if not member.bot]
        keep_humans = [member for member in keep_targets if not member.bot]
        if (remove_targets and not remove_humans) or (keep_targets and not keep_humans):
            await interaction.response.send_message("Bots can't be wishlisted.", ephemeral=True)
            return
        if remove_humans and keep_humans:
            await interaction.response.send_message(
                "Use `player` to remove people, or `keep` to leave people, not both.",
                ephemeral=True,
            )
            return

        name_by_id = {member.id: member.display_name for member in [*remove_humans, *keep_humans]}
        entries = db.get_adventure_wishlist_for_adventure(adventure)
        delete_ids, not_listed_ids, abort = plan_wishlist_trim(
            entries,
            remove_ids=[member.id for member in remove_humans] if remove_humans else None,
            keep_ids=[member.id for member in keep_humans] if keep_humans else None,
        )
        removed = [] if abort else db.remove_adventure_wishlist_entries(adventure, delete_ids)
        remaining = (
            db.get_adventure_wishlist_for_adventure(adventure)
            if remove_humans or keep_humans
            else []
        )
        message = format_trim_result(
            adventure,
            removed,
            targeted=bool(remove_humans),
            kept=bool(keep_humans),
            abort=abort,
            remaining=remaining,
            not_listed_names=[name_by_id[user_id] for user_id in not_listed_ids],
        )
        await interaction.response.send_message(message, ephemeral=True)

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

        rewards_session = db.get_rewards_session()
        resolved_adventure = adventure or self._derive_adventure_name(rewards_session)
        participant_ids = (
            db.get_session_players(rewards_session["id"]) if rewards_session else []
        )

        try:
            message_text = self._format_rewards_message(
                rewards,
                resolved_adventure,
                streaming,
                participant_ids=participant_ids,
            )
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

    @wishlist_trim.error
    async def wishlist_trim_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("Only the GM can run this command.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Sessions(bot))
