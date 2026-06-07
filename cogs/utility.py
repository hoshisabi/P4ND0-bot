import random
import requests
import json
import discord
from discord.ext import commands
from discord import app_commands

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show all available P4ND0 commands")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="P4ND0 Commands",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Characters",
            value=(
                "`/character add` — Save a D&D Beyond character to your profile\n"
                "`/character list` — View your saved characters\n"
                "`/character play` — Set which character you're using in the next session"
            ),
            inline=False,
        )
        embed.add_field(
            name="Schedule",
            value=(
                "`/schedule` — View upcoming Warhorn sessions (only you see it)\n"
                "`/notify` — Toggle DM notifications when the schedule changes\n"
                "`/watch` — Pin a live-updating schedule to this channel\n"
                "`/unwatch` — Remove the pinned schedule from this channel"
            ),
            inline=False,
        )
        embed.add_field(
            name="Utility",
            value=(
                "`/roll` — Roll dice in NdN format (e.g., `2d6`, `1d20`)\n"
                "`/quote` — Get a random inspirational quote"
            ),
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

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

    @commands.command(name="sync")
    @commands.has_permissions(administrator=True)
    async def sync(self, ctx):
        """Force-sync slash commands. Guild sync is instant; global sync can take up to an hour."""
        guild_synced = await self.bot.tree.sync(guild=ctx.guild)
        global_synced = await self.bot.tree.sync()
        await ctx.send(
            f"Synced {len(guild_synced)} commands to this server (instant) "
            f"and {len(global_synced)} globally (up to 1 hour).",
            delete_after=15,
        )
        print(f"[Sync] Manual sync triggered by {ctx.author}: {len(guild_synced)} guild, {len(global_synced)} global.")


async def setup(bot):
    await bot.add_cog(Utility(bot))
