import json
import os
import random
import typing
from datetime import datetime

import discord
import feedparser
import markdownify
import requests
from mysql.connector import Error
from discord.ext import commands
from dotenv import load_dotenv
import mysql.connector

load_dotenv()

discord_token = os.getenv("DISCORD_TOKEN")
dbhost = os.getenv("DATABASE_HOST")
dbuser = os.getenv("DATABASE_USER")
dbpass = os.getenv("DATABASE_PASS")
dbname = os.getenv("DATABASE_NAME")
characters = {}


def save_characters():
    try:
        cnx = mysql.connector.connect(host=dbhost,
                                      database=dbname,
                                      user=dbuser,
                                      password=dbpass)
        if cnx.is_connected():
            dbinfo = cnx.get_server_info()
            print(f"Connected to server: {dbinfo}")

        cursor = cnx.cursor()
        insert_sql = "INSERT INTO characters (discord_id, character_url) VALUES (%s, %s);"
        delete_sql = "delete from characters where discord_id = %s"

        for (discord_id, url_set) in characters.items():
            cursor.execute(delete_sql, tuple(character))
            for url in url_set:
                cursor.execute(insert_sql, tuple(discord_id, url))

    except Error as e:
        print("Error connecting to db", e)
    finally:
        if cnx.is_connected():
            cursor.close()
            cnx.close()
            print("closed connection to db")


def load_characters():
    try:
        cnx = mysql.connector.connect(host=dbhost,
                                      database=dbname,
                                      user=dbuser,
                                      password=dbpass)
        if cnx.is_connected():
            dbinfo = cnx.get_server_info()
            print(f"Connected to server: {dbinfo}")

        cursor = cnx.cursor()
        sql = "select discord_id, character_url from characters"
        cursor.execute(sql)

        for (discord_id, url) in cursor:
            mychars = characters.setdefault(discord_id, set())
            mychars.add(url)

        cnx.commit()

    except Error as e:
        print("Error connecting to db", e)
    finally:
        if cnx.is_connected():
            cursor.close()
            cnx.close()
            print("closed connection to db")


def to_discord_timestamp(incoming_time):
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


@bot.hybrid_command()
async def character(ctx, url: str = None, user: discord.User = commands.parameter(default=lambda ctx: ctx.author)):
    name = f"{user.name}#{user.discriminator}"
    mychars = characters.setdefault(name, set())
    if url:
        mychars.add(url)
        save_characters()
        await ctx.send(f"Saving {url} for {name}.")
        print(characters)
    else:
        desc_text = f"The following characters belong to {name}:\n"
        for mychar in mychars:
            desc_text += f"\t{mychar}\n"
        await ctx.send(desc_text)
        print(desc_text)

    await ctx.send(characters)


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
        desc_text += f"  * [{x.title}]({x.link}) <t:{to_discord_timestamp(x.gd_when['starttime'])}>"
        if arg:
            mdif = markdownify.markdownify(x.summary)
            lines = mdif.splitlines()
            desc_text += "\n>".join([line for line in lines if line.strip()])
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


load_characters()
bot.run(discord_token)
