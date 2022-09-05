import discord
from discord.ext import commands
from discord import app_commands
import random
import os
import requests
import json
import feedparser

guild = discord.Object(id=613440179088130082)
print(guild)


class PandoClient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.synced = False

    async def on_ready(self):
        await self.wait_until_ready()
        if not self.synced:
            await tree.sync(guild=guild)
            self.synced = True
        print(f'Logged in as {bot.user} (ID: {bot.user.id})')
        print('------')


@commands.hybrid_command()
async def quote(ctx):
    response = requests.get("https://zenquotes.io/api/random")
    json_data = json.loads(response.text)
    quote = json_data[0]['q'] + " -" + json_data[0]['a']
    print(quote)
    await ctx.send_message(quote)

bot = PandoClient()
tree = app_commands.CommandTree(bot)

#
# intents = discord.Intents.default()
# intents.members = True
# intents.message_content = True
#
#
# description = '''
# A placeholder bot for the P4ND0 server, much more will eventually be here
# but right now, it's just a very basic thing.
#
# There are two commands: $quote and $rss
# '''
#
# intents = discord.Intents.default()
# intents.members = True
# intents.message_content = True
#
# bot = commands.Bot(command_prefix='?', description=description, intents=intents)
#
# @bot.event
# async def on_ready():
#     print(f'Logged in as {bot.user} (ID: {bot.user.id})')
#     print('------')
#
# @bot.command()
#
# @bot.command()
# async def rss(ctx):
#     """Get the schedule of upcoming events off of the Warhorn"""
#     rss = feedparser.parse("https://warhorn.net/events/pandodnd/schedule/Ya7RynA9U_XsaE_Ve6Ht.atom")
#     print(rss.entries[0])
#     rsslist = [f"\t{x.title}: {x.link}\n" for x in rss.entries]
#     reply = f"The following games are coming up:\n\n:{rsslist}\n"
#     print(reply)
#     await ctx.send(reply)
#
# @bot.command()
# async def roll(ctx, dice: str):
#     """Rolls a dice in NdN format."""
#     try:
#         rolls, limit = map(int, dice.split('d'))
#     except Exception:
#         await ctx.send('Format has to be in NdN!')
#         return
#     result = ', '.join(str(random.randint(1, limit)) for r in range(rolls))
#     await ctx.send(result)

bot.run(os.getenv('TOKEN'))
