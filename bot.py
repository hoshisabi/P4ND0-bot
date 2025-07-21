import datetime
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

# Import the WarhornClient from your new file
from warhorn_api import WarhornClient, event_sessions_query, WARHORN_API_ENDPOINT, WARHORN_APPLICATION_TOKEN


load_dotenv()

discord_token = os.getenv("DISCORD_TOKEN")
dbhost = os.getenv("DATABASE_HOST")
dbuser = os.getenv("DATABASE_USER")
dbpass = os.getenv("DATABASE_PASS")
dbname = os.getenv("DATABASE_NAME")
rssfeed = os.getenv("FEED_URL")

# Initialize the WarhornClient globally or pass it where needed
warhorn_client = WarhornClient(WARHORN_API_ENDPOINT, WARHORN_APPLICATION_TOKEN)


def get_warhorn_embed(full: bool):
    # Removed the redundant '# Schedule' from here. Discord Embed's title handles that.
    desc_text = """The following games are upcoming on this server, click on a link to schedule a seat.

"""
    pandodnd_slug = "pandodnd"
    # Use the warhorn_client to get event sessions (now filtered server-side)
    result = warhorn_client.get_event_sessions(pandodnd_slug)
    print(f"Warhorn API raw response for embed generation: {result}")

    if "data" not in result or "eventSessions" not in result["data"] or "nodes" not in result["data"]["eventSessions"]:
        print("Unexpected Warhorn API response structure.")
        return discord.Embed(title="Schedule Error", description="Could not retrieve schedule from Warhorn. Please try again later.", color=discord.Color.red())

    sessions_to_display = result["data"]["eventSessions"]["nodes"]

    if not sessions_to_display:
        desc_text += "\nNo upcoming games currently scheduled. Check back later!\n"
    else:
        for session in sessions_to_display:
            session_name = session["name"]
            session_id = session["id"].replace("EventSession-", "")
            starts_at = datetime.fromisoformat(session["startsAt"]).strftime("%B %d, %Y %I:%M %p")
            location = session["location"]
            max_players = session["maxPlayers"]
            available_seats = session["availablePlayerSeats"]
            
            gm_names_list = []
            for gm in session["gmSignups"]:
                name = gm["user"]["name"]
                if "(" in name and name.endswith(")"):
                    parts = name.split("(", 1)
                    display_name = parts[0].strip()
                    discord_handle = parts[1][:-1].strip()
                    gm_names_list.append(f"{discord_handle} ({display_name})")
                elif "#" in name:
                    gm_names_list.append(name)
                else:
                    gm_names_list.append(name)
            gm_names = ", ".join(gm_names_list) if gm_names_list else "(None)"

            player_names_list = []
            for player in session["playerSignups"]:
                name = player["user"]["name"]
                if "(" in name and name.endswith(")"):
                    parts = name.split("(", 1)
                    display_name = parts[0].strip()
                    discord_handle = parts[1][:-1].strip()
                    player_names_list.append(f"{discord_handle} ({display_name})")
                elif "#" in name:
                    player_names_list.append(name)
                else:
                    player_names_list.append(name)
            player_names = ", ".join(player_names_list) if player_names_list else "(empty)"
            scenario_name = session["scenario"]["name"]
            game_system = session["scenario"]["gameSystem"]["name"]

            warhorn_url = f"https://warhorn.net/events/{pandodnd_slug}/schedule/sessions/{session_id}"

            desc_text += f"* [{session_name}]({warhorn_url}) `{starts_at}`\n"
            desc_text += f"  * **DM:** {gm_names}\n"
            desc_text += f"  * **Players:** {player_names}, ({available_seats} empty slots)\n"


    return discord.Embed(title="Schedule", type="rich", description=desc_text, color=discord.Color.green())

description = '''
A placeholder bot for the P4ND0 server, much more will eventually be here
but right now, it's just a very basic thing. Look for more capabilities later!
'''

watched_channels = {}

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='$', description=description, intents=intents)


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


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')


def get_key_from_message(message):
    return f"{message.guild}:{message.channel}"


@bot.event
async def on_message(message):
    await bot.process_commands(message)
    if message.author != bot.user:
        key = get_key_from_message(message)
        if key in watched_channels and (schedule_message := watched_channels[key]):
            await schedule_message.delete()
            watched_channels[key] = await message.channel.send(embed=get_warhorn_embed(False))
            print("Updated channel with new events")


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
async def schedule(ctx, arg: typing.Optional[bool] = False):
    """Pulls the most recent schedule of upcoming events from Warhorn displayed in local time
    Pass "True" to get full details of event. """
    embed = get_warhorn_embed(arg)
    await ctx.send(embed=embed)


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
async def watch(ctx):
    """Watch a channel to ensure that the schedule is always the most recent message"""
    embed = get_warhorn_embed(False)
    message = await ctx.send(embed=embed)
    key = get_key_from_message(message)
    watched_channels[key] = message
    print(f"Set to watch channel {message.channel}: {watched_channels}")


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


characters = {}

# load_characters()
bot.run(discord_token)