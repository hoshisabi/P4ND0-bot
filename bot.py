import discord
from discord.ext import commands
import random
import os
import requests
import json
import feedparser

intents = discord.Intents.default()
intents.members = True
intents.message_content = True


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
async def quote(ctx):
    """Generate a random quote"""
    response = requests.get("https://zenquotes.io/api/random")
    json_data = json.loads(response.text)
    quote = "Quote courtesy of https://zenquotes.io/\n" + json_data[0]['q'] + "\n\t-" + json_data[0]['a'] + "\n"
    print(quote)
    await ctx.send(quote)

@bot.command()
async def quote2(ctx):
    """Generate a random quote: experimental"""
    response = requests.get("https://zenquotes.io/api/random")
    json_data = json.loads(response.text)
    embed = discord.embed(title="Quote", color = discord.Color.blue())
    quote = "Quote courtesy of https://zenquotes.io/\n" + json_data[0]['q'] + "\n\t-" + json_data[0]['a'] + "\n"
    print(quote)
    embed.add_field(field = json_data[0]['q'], name = json_data[0]['a'], inline = false)
    await ctx.send(embed)



@bot.command()
async def rss(ctx):
    """Get the schedule of upcoming events off of the Warhorn"""
    rss = feedparser.parse("https://warhorn.net/events/pandodnd/schedule/Ya7RynA9U_XsaE_Ve6Ht.atom")
    print(rss.entries[0])
    rsslist = [f"{x.title} {x.gd_when['starttime']}: {x.link}" for x in rss.entries]
    rssoutput = "\n\t".join(rsslist)
    reply = f"The following games are coming up:\n\n\t{rssoutput}\n"
    print(reply)
    await ctx.send(reply)

@bot.command()
async def roll(ctx, dice: str):
    """Rolls a dice in NdN format."""
    try:
        rolls, limit = map(int, dice.split('d'))
    except Exception:
        await ctx.send('Format has to be in NdN!')
        return

    result = ', '.join(str(random.randint(1, limit)) for r in range(rolls))
    await ctx.send(result)

bot.run(os.getenv('TOKEN'))