import asyncio
import re
import requests
import json
import discord
from discord.ext import commands
from discord import app_commands

from utils import db

DDB_CHARACTER_ID_RE = re.compile(r"characters/(\d+)")


class Characters(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        timestamp = discord.utils.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        self.characters = db.load_all_characters()
        if self.characters:
            print(f"[{timestamp}] Characters loaded from database.")

    char_group = app_commands.Group(name="character", description="Manage your D&D Beyond characters")

    @staticmethod
    def _extract_character_id(text: str) -> str | None:
        match = DDB_CHARACTER_ID_RE.search(text)
        return match.group(1) if match else None

    @staticmethod
    def _clean_character_url(character_id: str) -> str:
        return f"https://www.dndbeyond.com/characters/{character_id}"

    @staticmethod
    def _character_urls_match(url1: str, url2: str) -> bool:
        id1 = Characters._extract_character_id(url1)
        id2 = Characters._extract_character_id(url2)
        return id1 is not None and id1 == id2

    async def _fetch_character_from_ddb(self, character_id: str) -> tuple[str, str | None]:
        json_api_url = f"https://character-service.dndbeyond.com/character/v5/character/{character_id}"
        print(f"Fetching character data from: {json_api_url}")
        response = await asyncio.to_thread(requests.get, json_api_url, timeout=10)
        response.raise_for_status()
        char_data = response.json()

        if not char_data or "data" not in char_data:
            raise ValueError("missing_data")

        char_info = char_data["data"]
        character_name = char_info.get("name", "Unknown Character")
        if not character_name and char_info.get("username"):
            character_name = char_info.get("username")

        avatar_url = char_info.get("decorations", {}).get("avatarUrl")
        return character_name, avatar_url

    def _upsert_user_character(
        self, user_id: int, clean_url: str, character_name: str, avatar_url: str | None
    ) -> bool:
        user_characters = self.characters.setdefault(user_id, [])
        found = False
        for i, char_entry in enumerate(user_characters):
            if self._character_urls_match(char_entry["url"], clean_url):
                user_characters[i] = {"url": clean_url, "name": character_name, "avatar_url": avatar_url}
                found = True
                break
        if not found:
            user_characters.append({"url": clean_url, "name": character_name, "avatar_url": avatar_url})

        db.save_character(user_id, clean_url, character_name, avatar_url)
        return not found

    async def _handle_ddb_fetch_error(self, send, error: Exception):
        if isinstance(error, requests.exceptions.HTTPError):
            if error.response.status_code == 403:
                await send(
                    "❌ Could not retrieve character data! D&D Beyond returned a `403 Forbidden` error.\n\n"
                    "**Fix:** The bot cannot read Private character sheets. Please go to your character's `Preferences` page on D&D Beyond and ensure **Character Privacy** is set to **Public**.",
                )
            else:
                await send(f"Could not fetch character data due to an HTTP error: {error}")
            print(f"HTTPError fetching D&D Beyond character: {error}")
        elif isinstance(error, requests.exceptions.RequestException):
            await send(f"Could not fetch character data due to a network error: {error}")
            print(f"Network error fetching D&D Beyond character: {error}")
        elif isinstance(error, json.JSONDecodeError):
            await send("Could not parse D&D Beyond character data. The response was not valid JSON.")
            print("JSONDecodeError for D&D Beyond character data.")
        elif isinstance(error, ValueError) and str(error) == "missing_data":
            await send("Could not retrieve character data from D&D Beyond. The character might be private or the ID is incorrect.")
            print("D&D Beyond API response missing 'data' key.")
        else:
            await send(f"An unexpected error occurred while fetching character data: {error}")
            print(f"Unexpected error fetching D&D Beyond character: {error}")

    @char_group.command(name="add", description="Add or update a D&D Beyond character to a player's profile")
    @app_commands.describe(
        url="The full link to your D&D Beyond character sheet (e.g., https://www.dndbeyond.com/characters/12345)",
        player="Another player to add to (admin only)",
    )
    async def add(
        self,
        interaction: discord.Interaction,
        url: str,
        player: discord.Member | None = None,
    ):
        """
        Adds a D&D Beyond character using its URL.
        """
        if player and player.id != interaction.user.id:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "Only admins can add a character to another player's profile.",
                    ephemeral=True,
                )
                return

        await interaction.response.defer(ephemeral=True)
        target = player or interaction.user
        added_by_other = target.id != interaction.user.id

        character_id = self._extract_character_id(url)
        if not character_id:
            await interaction.followup.send("Please provide a valid D&D Beyond character URL or ID (e.g., `https://www.dndbeyond.com/characters/1234567`).", ephemeral=True)
            return

        clean_url = self._clean_character_url(character_id)

        try:
            character_name, avatar_url = await self._fetch_character_from_ddb(character_id)
            was_new = self._upsert_user_character(target.id, clean_url, character_name, avatar_url)

            if added_by_other:
                title = f"{target.display_name} — {'Character Added' if was_new else 'Character Updated'}: {character_name}"
                footer = f"Added by {interaction.user.display_name}"
            else:
                title = f"Character Added: {character_name}" if was_new else f"Character Updated: {character_name}"
                footer = f"Saved for {target.display_name}"

            embed = discord.Embed(title=title, url=clean_url, color=discord.Color.gold())
            if avatar_url:
                embed.set_thumbnail(url=avatar_url)
            embed.set_footer(text=footer)

            await interaction.followup.send(embed=embed, ephemeral=True)
            print(f"User {interaction.user.id} added/updated character for {target.id}: {character_name} ({clean_url})")
        except Exception as e:
            await self._handle_ddb_fetch_error(
                lambda msg: interaction.followup.send(msg, ephemeral=True), e
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.content:
            return

        character_id = self._extract_character_id(message.content)
        if not character_id:
            return

        clean_url = self._clean_character_url(character_id)
        user_id = message.author.id

        try:
            character_name, avatar_url = await self._fetch_character_from_ddb(character_id)
            was_new = self._upsert_user_character(user_id, clean_url, character_name, avatar_url)
            db.set_character_selection(user_id, clean_url, character_name)

            if was_new:
                title = f"Character added and set for next session: {character_name}"
            else:
                title = f"Character set for next session: {character_name}"

            embed = discord.Embed(title=title, url=clean_url, color=discord.Color.green())
            if avatar_url:
                embed.set_thumbnail(url=avatar_url)
            embed.set_footer(text=f"Detected from {message.author.display_name}'s message")

            await message.reply(embed=embed, mention_author=False)
            print(f"Auto-detected character for user {user_id}: {character_name} ({clean_url})")
        except Exception as e:
            await self._handle_ddb_fetch_error(
                lambda msg: message.reply(msg, mention_author=False), e
            )

    def _build_character_list_embed(self, target: discord.Member, user_characters: list[dict]) -> discord.Embed:
        selection = db.get_character_selection(target.id)

        embed = discord.Embed(
            title=f"{target.display_name}'s D&D Beyond Characters",
            color=discord.Color.purple(),
        )

        if selection:
            embed.add_field(
                name="Playing next session",
                value=f"[{selection['character_name']}]({selection['character_url']})",
                inline=False,
            )
        else:
            embed.add_field(name="Playing next session", value="*Not set*", inline=False)

        if not user_characters:
            embed.add_field(
                name="Saved characters",
                value="*None saved* — use `/character add` or paste a D&D Beyond link in chat.",
                inline=False,
            )
        else:
            lines = []
            for i, char_entry in enumerate(user_characters):
                char_name = char_entry.get("name", "Unknown Character")
                char_url = char_entry.get("url", "#")
                marker = ""
                if selection and self._character_urls_match(char_entry["url"], selection["character_url"]):
                    marker = " ▶ "
                lines.append(f"{i + 1}.{marker} [{char_name}]({char_url})")
            embed.add_field(name="Saved characters", value="\n".join(lines), inline=False)

        embed.set_footer(text="Use /character play to set a character for the next session.")
        return embed

    @char_group.command(name="list", description="List saved D&D Beyond characters and session selection")
    @app_commands.describe(player="Another player to look up (admin only)")
    async def list(self, interaction: discord.Interaction, player: discord.Member | None = None):
        if player and player.id != interaction.user.id:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "Only admins can view another player's characters.",
                    ephemeral=True,
                )
                return

        target = player or interaction.user
        user_characters = self.characters.get(target.id, [])

        embed = self._build_character_list_embed(target, user_characters)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    def _target_user_id(self, interaction: discord.Interaction, player: discord.Member | None) -> int:
        return player.id if player else interaction.user.id

    async def play_autocomplete(self, interaction: discord.Interaction, current: str):
        player = interaction.namespace.player
        user_id = player.id if player else interaction.user.id
        user_characters = self.characters.get(user_id, [])
        return [
            app_commands.Choice(name=f"{i + 1}. {char['name']}", value=str(i + 1))
            for i, char in enumerate(user_characters)
            if current.lower() in char["name"].lower()
        ][:25]

    def _send_play_embed(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
        character_name: str,
        character_url: str,
        avatar_url: str | None,
        *,
        assigned_by_other: bool,
    ):
        if assigned_by_other:
            title = f"{target.display_name} → {character_name}"
            footer = f"Set by {interaction.user.display_name} for the next session"
        else:
            title = f"Ready for session: {character_name}"
            footer = "Your character has been set for the next session."

        embed = discord.Embed(title=title, url=character_url, color=discord.Color.green())
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
        embed.set_footer(text=footer)
        return embed

    @char_group.command(name="play", description="Set which character is playing in the next session")
    @app_commands.describe(
        character="A saved character (by number from /character list)",
        url="D&D Beyond character URL (adds or updates the sheet if needed)",
        player="Another player to set (admin only)",
    )
    @app_commands.autocomplete(character=play_autocomplete)
    async def play(
        self,
        interaction: discord.Interaction,
        character: str | None = None,
        url: str | None = None,
        player: discord.Member | None = None,
    ):
        if not character and not url:
            await interaction.response.send_message(
                "Provide a saved character or a D&D Beyond URL.",
                ephemeral=True,
            )
            return

        if player and player.id != interaction.user.id:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "Only admins can set another player's character.",
                    ephemeral=True,
                )
                return

        target = player or interaction.user
        assigned_by_other = target.id != interaction.user.id

        if url:
            await interaction.response.defer(ephemeral=True)

            character_id = self._extract_character_id(url)
            if not character_id:
                await interaction.followup.send(
                    "Please provide a valid D&D Beyond character URL (e.g., `https://www.dndbeyond.com/characters/1234567`).",
                    ephemeral=True,
                )
                return

            clean_url = self._clean_character_url(character_id)

            try:
                character_name, avatar_url = await self._fetch_character_from_ddb(character_id)
                self._upsert_user_character(target.id, clean_url, character_name, avatar_url)
                db.set_character_selection(target.id, clean_url, character_name)

                embed = self._send_play_embed(
                    interaction,
                    target,
                    character_name,
                    clean_url,
                    avatar_url,
                    assigned_by_other=assigned_by_other,
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                print(f"User {interaction.user.id} set character for {target.id}: {character_name} ({clean_url})")
            except Exception as e:
                await self._handle_ddb_fetch_error(
                    lambda msg: interaction.followup.send(msg, ephemeral=True), e
                )
            return

        user_characters = self.characters.get(target.id, [])

        try:
            idx = int(character) - 1
        except (ValueError, TypeError):
            await interaction.response.send_message("Invalid selection.", ephemeral=True)
            return

        if not user_characters or idx < 0 or idx >= len(user_characters):
            if assigned_by_other:
                hint = f"{target.display_name} has no saved characters. Use the `url` option with a D&D Beyond link."
            else:
                hint = "Invalid selection. Use `/character list` to see your characters."
            await interaction.response.send_message(hint, ephemeral=True)
            return

        char = user_characters[idx]
        db.set_character_selection(target.id, char["url"], char["name"])

        embed = self._send_play_embed(
            interaction,
            target,
            char["name"],
            char["url"],
            char.get("avatar_url"),
            assigned_by_other=assigned_by_other,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Characters(bot))
