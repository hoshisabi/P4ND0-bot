import datetime
import json
import os
import random
import re
import typing
from datetime import datetime, timezone
import asyncio

import discord
import requests
from discord.ext import commands, tasks
from dotenv import load_dotenv

# Import the WarhornClient from your warhorn_api.py file
from warhorn_api import WarhornClient, event_sessions_query

load_dotenv()

discord_token = os.getenv("DISCORD_TOKEN")
rssfeed = os.getenv("FEED_URL")


# --- Define JSON File Paths for Persistence ---
CHARACTERS_FILE = "characters.json"
WATCHED_SCHEDULES_FILE = "watched_schedules.json"
LAST_WARHORN_SESSIONS_FILE = "last_warhorn_sessions.json"

watched_schedules: typing.Dict[int, typing.Union[discord.Message, typing.Dict[str, int]]] = {}
last_warhorn_sessions_data: typing.Dict[int, typing.List[typing.Dict]] = {}
characters: typing.Dict[int, typing.List[typing.Dict[str, str]]] = {}


# --- Persistence Functions (using local JSON files) ---
def save_watched_schedules():
    try:
        serializable_watched_schedules = {}
        for channel_id, msg_or_data in watched_schedules.items():
            if isinstance(msg_or_data, discord.Message):
                serializable_watched_schedules[str(channel_id)] = {
                    "channel_id": msg_or_data.channel.id,
                    "message_id": msg_or_data.id
                }
            elif isinstance(msg_or_data, dict):
                 serializable_watched_schedules[str(channel_id)] = msg_or_data
        
        with open(WATCHED_SCHEDULES_FILE, 'w') as f:
            json.dump(serializable_watched_schedules, f, indent=4)
        print(f"Watched schedules saved to {WATCHED_SCHEDULES_FILE}")
    except Exception as e:
        print(f"Error saving watched schedules to file: {e}")

def load_watched_schedules():
    global watched_schedules
    try:
        if os.path.exists(WATCHED_SCHEDULES_FILE):
            with open(WATCHED_SCHEDULES_FILE, 'r') as f:
                loaded_data = json.load(f)
                watched_schedules = {int(k): v for k, v in loaded_data.items()}
            print(f"Watched schedules loaded from {WATCHED_SCHEDULES_FILE} (IDs only, messages will be fetched).")
        else:
            print(f"{WATCHED_SCHEDULES_FILE} not found. Starting with no watched channels.")
            watched_schedules = {}
    except Exception as e:
        print(f"Error loading watched schedules from file: {e}")
        watched_schedules = {}

def save_last_warhorn_sessions_data():
    try:
        serializable_data = {str(k): v for k, v in last_warhorn_sessions_data.items()}
        with open(LAST_WARHORN_SESSIONS_FILE, 'w') as f:
            json.dump(serializable_data, f, indent=4)
        print(f"Last Warhorn sessions data saved to {LAST_WARHORN_SESSIONS_FILE}")
    except Exception as e:
        print(f"Error saving last Warhorn sessions data to file: {e}")

def load_last_warhorn_sessions_data():
    global last_warhorn_sessions_data
    try:
        if os.path.exists(LAST_WARHORN_SESSIONS_FILE):
            with open(LAST_WARHORN_SESSIONS_FILE, 'r') as f:
                loaded_data = json.load(f)
                last_warhorn_sessions_data = {int(k): v for k, v in loaded_data.items()}
            print(f"Last Warhorn sessions data loaded from {LAST_WARHORN_SESSIONS_FILE}")
        else:
            print(f"{LAST_WARHORN_SESSIONS_FILE} not found. Starting with no last sessions data.")
            last_warhorn_sessions_data = {}
    except Exception as e:
        print(f"Error loading last Warhorn sessions data from file: {e}")
        last_warhorn_sessions_data = {}

def save_characters():
    try:
        serializable_characters = {str(k): v for k, v in characters.items()}
        with open(CHARACTERS_FILE, 'w') as f:
            json.dump(serializable_characters, f, indent=4)
        print(f"Characters saved to {CHARACTERS_FILE}")
    except Exception as e:
        print(f"Error saving characters to file: {e}")

def load_characters():
    global characters
    try:
        if os.path.exists(CHARACTERS_FILE):
            with open(CHARACTERS_FILE, 'r') as f:
                loaded_data = json.load(f)
                characters = {int(k): v for k, v in loaded_data.items()}
            print(f"Characters loaded from {CHARACTERS_FILE}")
        else:
            print(f"{CHARACTERS_FILE} not found. Starting with empty characters.")
            characters = {}
    except Exception as e:
        print(f"Error loading characters from file: {e}")
        characters = {}


# --- Warhorn API Client Instantiation (using imported class) ---
WARHORN_APPLICATION_TOKEN = os.getenv("WARHORN_APPLICATION_TOKEN")
WARHORN_API_ENDPOINT = "https://warhorn.net/graphql"
warhorn_client = WarhornClient(WARHORN_API_ENDPOINT, WARHORN_APPLICATION_TOKEN)


# --- Discord Bot Setup ---
description = '''
A placeholder bot for the P4ND0 server, much more will eventually be here
but right now, it's just a very basic thing. Look for more capabilities later!
'''

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='$', description=description, intents=intents)


# --- Discord Bot Events ---
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
    load_characters()
    load_watched_schedules()
    load_last_warhorn_sessions_data()

    channels_to_remove = []
    for channel_id, data_or_message in list(watched_schedules.items()): 
        if isinstance(data_or_message, discord.Message):
            continue 

        message_id = data_or_message.get("message_id")

        try:
            channel = bot.get_channel(channel_id)
            if not channel:
                channel = await bot.fetch_channel(channel_id)
            
            if channel:
                message = await channel.fetch_message(message_id)
                watched_schedules[channel_id] = message
                print(f"Successfully fetched watched message {message_id} in channel {channel_id}.")
            else:
                print(f"Channel {channel_id} not found for watched message {message_id}. Removing from watch list.")
                channels_to_remove.append(channel_id)
        except discord.NotFound:
            print(f"Message {message_id} not found in channel {channel_id}. It might have been deleted. Removing from watch list.")
            channels_to_remove.append(channel_id)
        except discord.Forbidden:
            print(f"Bot does not have permission to access channel {channel_id} or message {message_id}. Removing from watch list.")
            channels_to_remove.append(channel_id)
        except Exception as e:
            print(f"An error occurred while fetching watched message {message_id} in channel {channel_id}: {e}. Removing.")
            channels_to_remove.append(channel_id)

    for ch_id in channels_to_remove:
        if ch_id in watched_schedules:
            del watched_schedules[ch_id]
        if ch_id in last_warhorn_sessions_data:
            del last_warhorn_sessions_data[ch_id]
    save_watched_schedules()
    save_last_warhorn_sessions_data()
    
    update_warhorn_schedule.start()


# --- get_warhorn_embed helper function ---
def get_warhorn_embed_and_data(full: bool):
    desc_text = """The following games are upcoming on this server, click on a link to schedule a seat.

"""
    pandodnd_slug = "pandodnd"
    try:
        # The warhorn_api.py's get_event_sessions already uses 'startsAfter'
        result = warhorn_client.get_event_sessions(pandodnd_slug)
        print(f"Warhorn API response: {json.dumps(result, indent=2)}")

        if "data" not in result or "eventSessions" not in result["data"] or "nodes" not in result["data"]["eventSessions"]:
            print("Unexpected Warhorn API response structure or no data.")
            return discord.Embed(title="Schedule Error", description="Could not retrieve schedule from Warhorn. Please try again later.", color=discord.Color.red()), []

        # The API already filters for startsAfter, so we just sort the received nodes
        sessions_data = sorted(
            result["data"]["eventSessions"]["nodes"],
            key=lambda x: datetime.fromisoformat(x["startsAt"].replace("Z", "+00:00"))
        )

        if not sessions_data:
            embed = discord.Embed(title="Upcoming Warhorn Events", description="No upcoming sessions found.", color=discord.Color.blue())
            embed.set_footer(text="Updates every 10 minutes or on channel activity.")
            return embed, sessions_data

        for session in sessions_data:
            session_name = session["name"]
            session_id = session["id"].replace("EventSession-", "")
            session_start_str = session["startsAt"]
            # These are no longer used for display, but kept if needed for other logic:
            session_location = session["location"] 
            scenario_name = session["scenario"]["name"] if session["scenario"] else "N/A"
            game_system_name = session["scenario"]["gameSystem"]["name"] if session["scenario"] and session["scenario"]["gameSystem"] else "N/A"

            max_players = session["maxPlayers"]
            available_seats = session["availablePlayerSeats"]
            gm_name = session["gmSignups"][0]["user"]["name"] if session["gmSignups"] else "No GM"
            players_signed_up = len(session["playerSignups"])

            # Convert to Unix timestamp for Discord's specialized time handling
            utc_dt = datetime.fromisoformat(session_start_str.replace("Z", "+00:00"))
            unix_timestamp = int(utc_dt.timestamp())
            
            # Format using Discord's timestamp markdown (F for Long Date/Time)
            time_str = f"<t:{unix_timestamp}:F>"

            warhorn_url = f"https://warhorn.net/events/{pandodnd_slug}/schedule/sessions/{session_id}"

            # Constructing the session block based on image_b772da.png
            session_block = f"**[{session_name}]({warhorn_url})**\n"
            session_block += f"• **When:** {time_str}\n"
            session_block += f"• **GM:** {gm_name}\n"
            session_block += f"• **Players:** {players_signed_up}/{max_players} ({available_seats} seats left)\n"
            
            session_block += "\n" # Add a newline to separate sessions

            desc_text += session_block

        embed = discord.Embed(
            title="Upcoming Warhorn Events", # Confirmed from image
            description=desc_text,
            color=discord.Color.blue(),
            url=f"https://warhorn.net/events/{pandodnd_slug}/schedule"
        )
        embed.set_footer(text="Updates every 10 minutes or on channel activity.")
        return embed, sessions_data

    except requests.exceptions.RequestException as e:
        print(f"Error fetching Warhorn schedule: {e}")
        return discord.Embed(title="Schedule Error", description=f"Could not retrieve schedule from Warhorn due to a network error: {e}", color=discord.Color.red()), []
    except Exception as e:
        print(f"An unexpected error occurred in get_warhorn_embed_and_data: {e}")
        return discord.Embed(title="Schedule Error", description=f"An unexpected error occurred while fetching schedule: {e}", color=discord.Color.red()), []


# --- Discord Bot Commands ---
@bot.command()
async def character(ctx, character_url: typing.Optional[str] = None):
    """
    Manages D&D Beyond characters.
    - Use $character <D&D Beyond URL> to add or update a character.
    - Use $character to list your saved characters.
    """
    user_id = ctx.author.id
    user_characters = characters.setdefault(user_id, [])

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

            print(f"Extracted Character Name: {character_name}")
            print(f"Extracted Avatar URL: {avatar_url}")

            found = False
            for i, char_entry in enumerate(user_characters):
                if char_entry["url"] == character_url:
                    user_characters[i] = {"url": character_url, "name": character_name, "avatar_url": avatar_url}
                    found = True
                    break
            if not found:
                user_characters.append({"url": character_url, "name": character_name, "avatar_url": avatar_url})

            save_characters()

            try:
                embed = discord.Embed(
                    title=f"Character Added/Updated: {character_name}",
                    url=character_url,
                    color=discord.Color.gold()
                )
                if avatar_url:
                    embed.set_thumbnail(url=avatar_url)
                embed.set_footer(text=f"Saved for {ctx.author.display_name}")

                print(f"Attempting to send embed: {embed.to_dict()}")
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