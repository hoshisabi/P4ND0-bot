import json
import random
import typing
from datetime import datetime

import discord
import feedparser
import markdownify
import requests
from discord.ext import commands


def to_discordtimestamp(incoming_time):
    return int(datetime.fromisoformat(incoming_time).timestamp())


description = '''
A placeholder bot for the P4ND0 server, much more will eventually be here
but right now, it's just a very basic thing. Look for more capabilities later!
'''

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='$', description=description, intents=intents)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')


@bot.command()
async def schedule(ctx, arg: typing.Optional[bool]):
    """Pulls the most recent schedule of upcoming events from Warhorn displayed in local time
    Pass "True" to get full details of event. """
    await rss(ctx)


@bot.command()
async def quote(ctx):
    """Generate a random quote (no parameters)"""
    response = requests.get("https://zenquotes.io/api/random")
    json_data = json.loads(response.text)
    quote = f"{json_data[0]['q']}\n\t-*{json_data[0]['a']}*\n"
    print(quote)
    embed = discord.Embed(title="Quote", color=discord.Color.blue())
    embed.description = quote
    embed.set_author(name="zenquotes.io", url="https://zenquotes.io/")
    await ctx.send(embed=embed)


@bot.command()
async def rss(ctx, arg: typing.Optional[bool]):
    """Pulls the most recent schedule of upcoming events from Warhorn displayed in local time
    Pass "True" to get full details of event. """
    print(arg)
    rss_feed = feedparser.parse("https://warhorn.net/events/pandodnd/schedule/Ya7RynA9U_XsaE_Ve6Ht.atom")
    print(rss_feed)
    desc_text = f"The following games are upcoming on this server, click on a link to schedule a seat.\n"
    for x in rss_feed.entries:
        desc_text += f"  * [{x.title}]({x.link}) <t:{to_discordtimestamp(x.gd_when['starttime'])}>"
        if (arg): desc_text += f"\n>{markdownify.markdownify(x.summary)}"
        desc_text += "\n"
    embed = discord.Embed(title="Schedule", type="rich", description=desc_text, color=discord.Color.green())

    print(f"Printed out schedule:\n{desc_text}")
    await ctx.send(embed=embed)


@bot.command()
async def roll(ctx, dice: str):
    """Rolls a dice in NdN format."""
    try:
        rolls, limit = map(int, dice.split('d'))
    except Exception:
        await ctx.send('Format has to be in NdN!')
        return
    result = ', '.join(str(random.randint(1, limit)) for _ in range(rolls))
    embed = discord.Embed(title="Dice", type="rich", description=result, color=discord.Color.blue())

    print(f"Dice result: {result}")
    await ctx.send(embed=embed)

with open(".env") as fd:
    token = fd.readline()

bot.run(token)
