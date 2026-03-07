import random
import requests
import json
import discord
from discord.ext import commands

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def quote(self, ctx):
        """Generate a random quote (no parameters)"""
        response = requests.get("https://zenquotes.io/api/random")
        json_data = json.loads(response.text)
        quote = f"{json_data[0]['q']}\n\t-*{json_data[0]['a']}*\n"
        print(quote)
        embed = discord.Embed(title="Quote", color=discord.Color.blue())
        embed.description = quote
        embed.set_author(name="zenquotes.io", url="https://zenquotes.io/")
        await ctx.send(embed=embed)

    @commands.command()
    async def roll(self, ctx, dice: str):
        """Rolls a dice in NdN format."""
        try:
            rolls, limit = map(int, dice.lower().split('d'))
            if rolls <= 0 or limit <= 0:
                await ctx.send('Number of rolls and dice faces must be positive!')
                return
            if rolls > 1000:
                await ctx.send('Please do not roll more than 1000 dice at once.')
                return
            if limit > 1000000:
                await ctx.send('Dice faces must be 1,000,000 or less.')
                return
        except ValueError:
            await ctx.send('Format has to be in NdN (e.g., `2d6`)!')
            return

        results = [random.randint(1, limit) for _ in range(rolls)]
        result_str = ', '.join(map(str, results))

        if len(result_str) > 1000:
            result_str = result_str[:1000] + "..."

        embed = discord.Embed(title="Dice Roll", description=f"{rolls}d{limit}", color=discord.Color.blue())
        embed.add_field(name="Results", value=result_str, inline=False)
        if rolls > 1:
            embed.add_field(name="Total", value=sum(results), inline=False)

        print(f"Dice result: {result_str}")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Utility(bot))
