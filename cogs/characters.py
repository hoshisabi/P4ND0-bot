import re
import requests
import json
import discord
from discord.ext import commands
from discord import app_commands

from utils.persistence import save_json_data, load_json_data

CHARACTERS_FILE = "characters.json"

class Characters(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Use UTC timestamp for startup logs
        timestamp = discord.utils.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        self.characters = load_json_data(
            CHARACTERS_FILE, 
            f"[{timestamp}] {CHARACTERS_FILE} not found. Starting with empty characters."
        )
        if self.characters:
            print(f"[{timestamp}] Characters loaded from {CHARACTERS_FILE}")

    def save_characters(self):
        serializable_characters = {str(k): v for k, v in self.characters.items()}
        save_json_data(CHARACTERS_FILE, serializable_characters, f"Characters saved to {CHARACTERS_FILE}")

    char_group = app_commands.Group(name="character", description="Manage your D&D Beyond characters")

    @char_group.command(name="add", description="Add or update a D&D Beyond character to your profile")
    @app_commands.describe(url="The full link to your D&D Beyond character sheet (e.g., https://www.dndbeyond.com/characters/12345)")
    async def add(self, interaction: discord.Interaction, url: str):
        """
        Adds a D&D Beyond character using its URL.
        """
        await interaction.response.defer()
        user_id = interaction.user.id
        user_characters = self.characters.setdefault(user_id, [])

        # Extract just the ID block regardless of what comes after it (e.g. /builder)
        match = re.search(r"characters/(\d+)", url)
        if not match:
            await interaction.followup.send("Please provide a valid D&D Beyond character URL or ID (e.g., `https://www.dndbeyond.com/characters/1234567`).")
            return

        character_id = match.group(1)
        
        # Clean the url so the saved embed link isn't /builder
        clean_url = f"https://www.dndbeyond.com/characters/{character_id}"
        json_api_url = f"https://character-service.dndbeyond.com/character/v5/character/{character_id}"

        try:
            print(f"Fetching character data from: {json_api_url}")
            response = requests.get(json_api_url, timeout=10)
            response.raise_for_status()
            char_data = response.json()

            if not char_data or "data" not in char_data:
                await interaction.followup.send("Could not retrieve character data from D&D Beyond. The character might be private or the ID is incorrect.")
                print(f"D&D Beyond API response missing 'data' key: {char_data}")
                return

            char_info = char_data["data"]
            character_name = char_info.get("name", "Unknown Character")
            if not character_name and char_info.get("username"):
                    character_name = char_info.get("username")
            
            avatar_url = char_info.get("decorations", {}).get("avatarUrl")

            found = False
            for i, char_entry in enumerate(user_characters):
                if char_entry["url"] == url:
                    user_characters[i] = {"url": url, "name": character_name, "avatar_url": avatar_url}
                    found = True
                    break
            if not found:
                user_characters.append({"url": url, "name": character_name, "avatar_url": avatar_url})

            self.save_characters()

            try:
                embed = discord.Embed(
                    title=f"Character Added/Updated: {character_name}",
                    url=clean_url,
                    color=discord.Color.gold()
                )
                if avatar_url:
                    embed.set_thumbnail(url=avatar_url)
                embed.set_footer(text=f"Saved for {interaction.user.display_name}")

                await interaction.followup.send(embed=embed)
                print(f"User {interaction.user.id} added/updated character: {character_name} ({url})")
            except Exception as embed_e:
                await interaction.followup.send(f"An error occurred while preparing or sending the Discord embed: {embed_e}")
                print(f"Error during embed creation/sending for character add: {embed_e}")

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                await interaction.followup.send(
                    "❌ Could not retrieve character data! D&D Beyond returned a `403 Forbidden` error.\n\n"
                    "**Fix:** The bot cannot read Private character sheets. Please go to your character's `Preferences` page on D&D Beyond and ensure **Character Privacy** is set to **Public**."
                )
            else:
                await interaction.followup.send(f"Could not fetch character data due to an HTTP error: {e}")
            print(f"HTTPError fetching D&D Beyond character: {e}")
        except requests.exceptions.RequestException as e:
            await interaction.followup.send(f"Could not fetch character data due to a network error: {e}")
            print(f"Network error fetching D&D Beyond character: {e}")
        except json.JSONDecodeError:
            await interaction.followup.send("Could not parse D&D Beyond character data. The response was not valid JSON.")
            print("JSONDecodeError for D&D Beyond character data.")
        except Exception as e:
            await interaction.followup.send(f"An unexpected error occurred while fetching character data: {e}")
            print(f"Unexpected error in /character add command: {e}")

    @char_group.command(name="list", description="List all your currently saved D&D Beyond characters")
    async def list(self, interaction: discord.Interaction):
        """
        Lists the user's saved D&D Beyond characters.
        """
        user_id = interaction.user.id
        user_characters = self.characters.get(user_id, [])

        if not user_characters:
            await interaction.response.send_message("You have no D&D Beyond characters saved. Use `/character add url:<URL>` to add one.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"{interaction.user.display_name}'s Saved D&D Beyond Characters",
            color=discord.Color.purple()
        )
        description_parts = []
        for char_entry in user_characters:
            char_name = char_entry.get("name", "Unknown Character")
            char_url = char_entry.get("url", "#")
            description_parts.append(f"• [{char_name}]({char_url})")

        embed.description = "\n".join(description_parts)
        embed.set_footer(text="Click on a character name to view it on D&D Beyond.")
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Characters(bot))
