import random
import requests
import json
import discord
from discord.ext import commands
from discord import app_commands

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="quote", description="Generate a random quote")
    async def quote(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            response = requests.get("https://zenquotes.io/api/random", timeout=5)
            response.raise_for_status()
            json_data = response.json()
            quote = f"{json_data[0]['q']}\n\t-*{json_data[0]['a']}*\n"
            
            embed = discord.Embed(title="Quote", color=discord.Color.blue())
            embed.description = quote
            embed.set_author(name="zenquotes.io", url="https://zenquotes.io/")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            print(f"Error fetching quote: {e}")
            await interaction.followup.send("Sorry, I couldn't fetch a quote right now.")

    @app_commands.command(name="roll", description="Rolls a dice in NdN format (e.g., 2d6)")
    @app_commands.describe(dice="The dice to roll in NdN format (e.g., 1d20, 2d6, 4d8)")
    async def roll(self, interaction: discord.Interaction, dice: str):
        try:
            rolls, limit = map(int, dice.lower().split('d'))
            if rolls <= 0 or limit <= 0:
                await interaction.response.send_message('Number of rolls and dice faces must be positive!', ephemeral=True)
                return
            if rolls > 1000:
                await interaction.response.send_message('Please do not roll more than 1000 dice at once.', ephemeral=True)
                return
            if limit > 1000000:
                await interaction.response.send_message('Dice faces must be 1,000,000 or less.', ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message('Format has to be in NdN (e.g., `2d6`)!', ephemeral=True)
            return

        results = [random.randint(1, limit) for _ in range(rolls)]
        result_str = ', '.join(map(str, results))

        if len(result_str) > 1000:
            result_str = result_str[:1000] + "..."

        embed = discord.Embed(title="Dice Roll", description=f"{rolls}d{limit}", color=discord.Color.blue())
        embed.add_field(name="Results", value=result_str, inline=False)
        if rolls > 1:
            embed.add_field(name="Total", value=str(sum(results)), inline=False)

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Utility(bot))
