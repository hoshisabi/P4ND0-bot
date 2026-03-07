import re
import requests
import json
import discord
from discord.ext import commands

from utils.persistence import save_json_data, load_json_data

CHARACTERS_FILE = "characters.json"

class Characters(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.characters = load_json_data(CHARACTERS_FILE, f"{CHARACTERS_FILE} not found. Starting with empty characters.")
        if self.characters:
            print(f"Characters loaded from {CHARACTERS_FILE}")

    def save_characters(self):
        serializable_characters = {str(k): v for k, v in self.characters.items()}
        save_json_data(CHARACTERS_FILE, serializable_characters, f"Characters saved to {CHARACTERS_FILE}")

    @commands.command()
    async def character(self, ctx, character_url: str = None):
        """
        Manages D&D Beyond characters.
        - Use $character <D&D Beyond URL> to add or update a character.
        - Use $character to list your saved characters.
        """
        user_id = ctx.author.id
        user_characters = self.characters.setdefault(user_id, [])

        if character_url:
            match = re.search(r"characters/(\d+)", character_url)
            if not match:
                await ctx.send("Please provide a valid D&D Beyond character URL (e.g., `https://www.dndbeyond.com/characters/1234567`).")
                return

            character_id = match.group(1)
            json_api_url = f"https://character-service.dndbeyond.com/character/v5/character/{character_id}"

            try:
                print(f"Fetching character data from: {json_api_url}")
                response = requests.get(json_api_url)
                response.raise_for_status()
                char_data = response.json()

                if not char_data or "data" not in char_data:
                    await ctx.send("Could not retrieve character data from D&D Beyond. The character might be private or the ID is incorrect.")
                    print(f"D&D Beyond API response missing 'data' key: {char_data}")
                    return

                char_info = char_data["data"]
                character_name = char_info.get("name", "Unknown Character")
                if not character_name and char_info.get("username"):
                     character_name = char_info.get("username")
                
                avatar_url = char_info.get("decorations", {}).get("avatarUrl")

                found = False
                for i, char_entry in enumerate(user_characters):
                    if char_entry["url"] == character_url:
                        user_characters[i] = {"url": character_url, "name": character_name, "avatar_url": avatar_url}
                        found = True
                        break
                if not found:
                    user_characters.append({"url": character_url, "name": character_name, "avatar_url": avatar_url})

                self.save_characters()

                try:
                    embed = discord.Embed(
                        title=f"Character Added/Updated: {character_name}",
                        url=character_url,
                        color=discord.Color.gold()
                    )
                    if avatar_url:
                        embed.set_thumbnail(url=avatar_url)
                    embed.set_footer(text=f"Saved for {ctx.author.display_name}")

                    await ctx.send(embed=embed, suppress_embeds=True)
                    print(f"User {ctx.author.id} added/updated character: {character_name} ({character_url})")
                except Exception as embed_e:
                    await ctx.send(f"An error occurred while preparing or sending the Discord embed: {embed_e}")
                    print(f"Error during embed creation/sending for !character: {embed_e}")

            except requests.exceptions.RequestException as e:
                await ctx.send(f"Could not fetch character data due to a network error: {e}")
                print(f"Error fetching D&D Beyond character: {e}")
            except json.JSONDecodeError:
                await ctx.send("Could not parse D&D Beyond character data. The response was not valid JSON.")
                print("JSONDecodeError for D&D Beyond character data.")
            except Exception as e:
                await ctx.send(f"An unexpected error occurred while fetching character data: {e}")
                print(f"Unexpected error in !character command: {e}")

        else:
            if not user_characters:
                await ctx.send("You have no D&D Beyond characters saved. Use `$character <D&D Beyond URL>` to add one.")
                return

            embed = discord.Embed(
                title=f"{ctx.author.display_name}'s Saved D&D Beyond Characters",
                color=discord.Color.purple()
            )
            description_parts = []
            for char_entry in user_characters:
                char_name = char_entry.get("name", "Unknown Character")
                char_url = char_entry.get("url", "#")
                description_parts.append(f"• [{char_name}]({char_url})")

            embed.description = "\n".join(description_parts)
            embed.set_footer(text="Click on a character name to view it on D&D Beyond.")
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Characters(bot))
