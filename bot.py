import datetime
import json
import os
import random
import typing
from datetime import datetime, timezone

import discord
import feedparser
import markdownify
import requests
from discord.ext import commands, tasks
from dotenv import load_dotenv
import asyncio

# Import the WarhornClient and API constants from your warhorn_api.py file
from warhorn_api import WarhornClient, WARHORN_API_ENDPOINT, WARHORN_APPLICATION_TOKEN


load_dotenv()

discord_token = os.getenv("DISCORD_TOKEN")
rssfeed = os.getenv("FEED_URL")

# --- Define JSON File Paths for Persistence ---
CHARACTERS_FILE = "characters.json"
WATCHED_SCHEDULES_FILE = "watched_schedules.json"

# Initialize the WarhornClient globally
warhorn_client = WarhornClient(WARHORN_API_ENDPOINT, WARHORN_APPLICATION_TOKEN)

# Dictionary to store (channel_id, message_id) for watched schedule messages
# And also the last fetched Warhorn data to compare against
watched_schedules = {}

# --- Utility to get Warhorn embed ---
def get_warhorn_embed(full: bool):
    desc_text = """The following games are upcoming on this server, click on a link to schedule a seat.

"""
    pandodnd_slug = "pandodnd"
    result = warhorn_client.get_event_sessions(pandodnd_slug)

    if "data" not in result or "eventSessions" not in result["data"] or "nodes" not in result["data"]["eventSessions"]:
        print("Unexpected Warhorn API response structure.")
        return discord.Embed(title="Schedule Error", description="Could not retrieve schedule from Warhorn. Please try again later.", color=discord.Color.red()), None

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
            desc_text += f"  * **Players:** {player_names}, *({available_seats} empty slots)*\n"


    return discord.Embed(title="Schedule", type="rich", description=desc_text, color=discord.Color.blue()), sessions_to_display


description = '''
A placeholder bot for the P4ND0 server, much more will eventually be here
but right now, it's just a very basic thing. Look for more capabilities later!
'''

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='$', description=description, intents=intents)


# --- Character Persistence Functions (using local JSON file) ---
characters = {} # Initialize characters dictionary

def save_characters():
    try:
        # Convert set to list for JSON serialization
        serializable_characters = {k: list(v) for k, v in characters.items()}
        with open(CHARACTERS_FILE, 'w') as f:
            json.dump(serializable_characters, f, indent=4)
        print(f"Characters saved to {CHARACTERS_FILE}")
    except Exception as e:
        print(f"Error saving characters to file: {e}")

def load_characters():
    global characters # Declare global to modify the outer dictionary
    try:
        if os.path.exists(CHARACTERS_FILE):
            with open(CHARACTERS_FILE, 'r') as f:
                loaded_data = json.load(f)
                # Convert list back to set
                characters = {k: set(v) for k, v in loaded_data.items()}
            print(f"Characters loaded from {CHARACTERS_FILE}")
        else:
            print(f"{CHARACTERS_FILE} not found. Starting with empty characters.")
            characters = {} # Ensure characters is empty if file doesn't exist
    except Exception as e:
        print(f"Error loading characters from file: {e}")
        characters = {} # Fallback to empty characters on error


# --- Watched Schedules Persistence Functions (using local JSON file) ---
def save_watched_schedules():
    try:
        # watched_schedules contains message_id (int) and last_sessions_data (list of dicts)
        # This structure is already JSON serializable
        with open(WATCHED_SCHEDULES_FILE, 'w') as f:
            json.dump(watched_schedules, f, indent=4)
        print(f"Watched schedules saved to {WATCHED_SCHEDULES_FILE}")
    except Exception as e:
        print(f"Error saving watched schedules to file: {e}")

def load_watched_schedules():
    global watched_schedules # Declare global to modify the outer dictionary
    try:
        if os.path.exists(WATCHED_SCHEDULES_FILE):
            with open(WATCHED_SCHEDULES_FILE, 'r') as f:
                watched_schedules = json.load(f)
            print(f"Watched schedules loaded from {WATCHED_SCHEDULES_FILE}")
        else:
            print(f"{WATCHED_SCHEDULES_FILE} not found. Starting with no watched channels.")
            watched_schedules = {} # Ensure watched_schedules is empty if file doesn't exist
    except Exception as e:
        print(f"Error loading watched schedules from file: {e}")
        watched_schedules = {} # Fallback to empty schedules on error


# --- Discord Bot Events ---
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
    load_characters()
    load_watched_schedules()
    update_warhorn_schedule.start()

@bot.event
async def on_message(message):
    await bot.process_commands(message)


@bot.command()
async def character(ctx, url: str = None, user: discord.User = commands.parameter(default=lambda ctx: ctx.author)):
    name = f"{user.name}#{user.discriminator}"
    mychars = characters.setdefault(name, set())
    if url:
        mychars.add(url)
        save_characters() # Save characters after modification
        await ctx.send(f"Saving {url} for {name}.")
        print(characters)
    else:
        desc_text = f"The following characters belong to {name}:\n"
        for mychar in mychars:
            desc_text += f"\t{mychar}\n"
        await ctx.send(desc_text)
        print(desc_text)

    # Note: Sending `characters` directly can be very verbose for large datasets
    # await ctx.send(characters)


@bot.command()
async def schedule(ctx, arg: typing.Optional[bool] = False):
    """Pulls the most recent schedule of upcoming events from Warhorn displayed in local time
    Pass "True" to get full details of event. """
    embed, _ = get_warhorn_embed(arg)
    if embed.color == discord.Color.red():
        await ctx.send(embed=embed)
        return
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
    """Watches this channel for Warhorn schedule updates, maintaining a pinned message."""
    if ctx.channel.id in watched_schedules:
        old_message_info = watched_schedules[ctx.channel.id]
        try:
            old_message = await ctx.channel.fetch_message(old_message_info["message_id"])
            await old_message.unpin()
            await old_message.delete()
            print(f"Old schedule message unpinned and deleted in channel {ctx.channel.id}.")
        except discord.NotFound:
            print(f"Old schedule message not found in channel {ctx.channel.id}, it might have been deleted manually.")
        except discord.Forbidden:
            print(f"Bot does not have permissions to unpin/delete messages in channel {ctx.channel.id}.")
        except Exception as e:
            print(f"Error handling old message in watched channel: {e}")

    embed, sessions_data = get_warhorn_embed(False)
    if embed.color == discord.Color.red():
        await ctx.send(embed=embed)
        return

    message = await ctx.send(embed=embed)
    
    try:
        await message.pin()
        print(f"Pinned schedule message in channel {ctx.channel.id}.")
    except discord.Forbidden:
        await ctx.send("I don't have permissions to pin messages in this channel! Please grant 'Manage Messages' permission.")
        print(f"Bot lacks permissions to pin in channel {ctx.channel.id}.")
        return

    watched_schedules[ctx.channel.id] = {
        "message_id": message.id,
        "last_sessions_data": sessions_data
    }
    save_watched_schedules() # Save watched schedules after modification
    print(f"Set to watch channel {ctx.channel.id} with message ID {message.id}.")


@bot.command()
async def unwatch(ctx):
    """Stops watching this channel for Warhorn schedule updates and unpins/deletes the message."""
    if ctx.channel.id in watched_schedules:
        message_info = watched_schedules[ctx.channel.id]
        try:
            message = await ctx.channel.fetch_message(message_info["message_id"])
            await message.unpin()
            await message.delete()
            del watched_schedules[ctx.channel.id]
            save_watched_schedules() # Save watched schedules after modification
            await ctx.send("Stopped watching this channel and removed the schedule message.")
            print(f"Stopped watching channel {ctx.channel.id}.")
        except discord.NotFound:
            await ctx.send("No schedule message found to unwatch in this channel.")
            del watched_schedules[ctx.channel.id] # Clear stale entry in memory
            save_watched_schedules() # Save updated state to file
        except discord.Forbidden:
            await ctx.send("I don't have permissions to unpin/delete messages in this channel!")
        except Exception as e:
            await ctx.send(f"An error occurred while unwatching: {e}")
            print(f"Error unwatching channel {ctx.channel.id}: {e}")
    else:
        await ctx.send("This channel is not currently being watched.")


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


# --- Scheduled Task to Update Warhorn Schedule ---
@tasks.loop(minutes=30)
async def update_warhorn_schedule():
    print("Running scheduled Warhorn schedule update check...")
    if not watched_schedules:
        print("No channels are being watched for schedules.")
        return
    
    for channel_id, info in list(watched_schedules.items()):
        message_id = info["message_id"]
        last_sessions_data = info["last_sessions_data"]
        
        channel = bot.get_channel(channel_id)
        if not channel:
            print(f"Watched channel {channel_id} not found, removing from watched_schedules.")
            del watched_schedules[channel_id]
            save_watched_schedules()
            continue
        
        try:
            new_embed, new_sessions_data = get_warhorn_embed(False)

            if new_embed.color == discord.Color.red():
                print(f"Error fetching new Warhorn data for channel {channel_id}. Skipping update.")
                continue

            if json.dumps(new_sessions_data, sort_keys=True) != json.dumps(last_sessions_data, sort_keys=True):
                print(f"Warhorn schedule changed for channel {channel_id}. Updating message...")
                message = await channel.fetch_message(message_id)
                await message.edit(embed=new_embed)
                watched_schedules[channel_id]["last_sessions_data"] = new_sessions_data
                save_watched_schedules()
            else:
                print(f"Warhorn schedule for channel {channel_id} is unchanged.")

        except discord.NotFound:
            print(f"Schedule message {message_id} not found in channel {channel_id}, removing from watched_schedules.")
            del watched_schedules[channel_id]
            save_watched_schedules()
        except discord.Forbidden:
            print(f"Bot lacks permissions to edit message {message_id} in channel {channel_id}, removing from watched_schedules.")
            del watched_schedules[channel_id]
            save_watched_schedules()
        except Exception as e:
            print(f"An error occurred during scheduled update for channel {channel_id}: {e}")


@update_warhorn_schedule.before_loop
async def before_update_warhorn_schedule():
    await bot.wait_until_ready()
    print("Warhorn schedule update loop ready to start.")
    await asyncio.sleep(5) # <--- ADD THIS LINE (5-10 seconds is usually sufficient)
    print("Finished initial delay for cache.") # Added for debug clarity

bot.run(discord_token)