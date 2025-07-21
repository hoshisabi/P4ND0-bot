import datetime
import json
import os
import random
import typing
from datetime import datetime, timezone # Import timezone for Warhorn API calls

import discord
import requests
from discord.ext import commands, tasks # Import tasks for the loop
from dotenv import load_dotenv

# Import the WarhornClient and API constants from your warhorn_api.py file
# Ensure warhorn_api.py is in the same directory or accessible via PYTHONPATH
from warhorn_api import WarhornClient, WARHORN_API_ENDPOINT, WARHORN_APPLICATION_TOKEN


load_dotenv()

discord_token = os.getenv("DISCORD_TOKEN")
rssfeed = os.getenv("FEED_URL")


# --- Define JSON File Paths for Persistence ---
CHARACTERS_FILE = "characters.json"
WATCHED_SCHEDULES_FILE = "watched_schedules.json"

# Initialize the WarhornClient globally
warhorn_client = WarhornClient(WARHORN_API_ENDPOINT, WARHORN_APPLICATION_TOKEN)

# Dictionary to store (channel_id, message_id, last_sessions_data) for watched schedule messages
# Key: channel_id, Value: {"message_id": int, "last_sessions_data": list_of_dicts}
watched_schedules = {}

# --- Utility to get Warhorn embed (Modified to use WarhornClient) ---
def get_warhorn_embed_and_data(full: bool):
    desc_text = """The following games are upcoming on this server, click on a link to schedule a seat.

"""
    pandodnd_slug = "pandodnd"
    # Use the WarhornClient to fetch sessions, passing the current UTC time for startsAt_gte filter
    result = warhorn_client.get_event_sessions(pandodnd_slug)

    # Debugging print for raw API response structure
    # print(f"Warhorn API response: {json.dumps(result, indent=2)}")

    if "data" not in result or "eventSessions" not in result["data"] or "nodes" not in result["data"]["eventSessions"]:
        print("Unexpected Warhorn API response structure or no data.")
        # Return an error embed and None for sessions_to_display
        return discord.Embed(title="Schedule Error", description="Could not retrieve schedule from Warhorn. Please try again later.", color=discord.Color.red()), None

    sessions_to_display = result["data"]["eventSessions"]["nodes"]

    if not sessions_to_display:
        desc_text += "\nNo upcoming games currently scheduled. Check back later!\n"
    else:
        for session in sessions_to_display:
            session_name = session["name"]
            session_id = session["id"].replace("EventSession-", "")
            # Ensure datetime object handles timezone correctly
            starts_at_dt = datetime.fromisoformat(session["startsAt"])
            starts_at = starts_at_dt.strftime("%B %d, %Y %I:%M %p")
            
            # Formatting player and GM names to match your screenshot and include Discord handles
            gm_names_list = []
            for gm in session["gmSignups"]:
                name = gm["user"]["name"]
                if "(" in name and name.endswith(")"):
                    # Assuming format "DisplayName (DiscordHandle)" or "DiscordHandle (DisplayName)"
                    parts = name.split("(", 1)
                    display_name = parts[0].strip()
                    discord_handle = parts[1][:-1].strip()
                    # Re-arranging to prioritize Discord handle display as per screenshot
                    gm_names_list.append(f"{discord_handle} ({display_name})")
                elif "#" in name: # If it's just a Discord handle like Name#1234
                    gm_names_list.append(name)
                else: # Generic name without special formatting
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
            
            available_seats = session["availablePlayerSeats"]

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
intents.message_content = True # Needed for on_message to read content

bot = commands.Bot(command_prefix='$', description=description, intents=intents)


# --- Character Persistence Functions (using local JSON file) ---
characters = {} # Initialize characters dictionary

def save_characters():
    try:
        # Convert set to list for JSON serialization
        serializable_characters = {str(k): list(v) for k, v in characters.items()}
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
                # Convert list back to set. Keys (discord_id) might be saved as strings.
                characters = {int(k) if str(k).isdigit() else k: set(v) for k, v in loaded_data.items()}
            print(f"Characters loaded from {CHARACTERS_FILE}")
        else:
            print(f"{CHARACTERS_FILE} not found. Starting with empty characters.")
            characters = {}
    except Exception as e:
        print(f"Error loading characters from file: {e}")
        characters = {}


# --- Watched Schedules Persistence Functions (using local JSON file) ---
def save_watched_schedules():
    try:
        # channel_id keys need to be strings for JSON if they are ints/longs
        serializable_watched_schedules = {str(k): v for k, v in watched_schedules.items()}
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
                # Convert channel_id keys back to int
                watched_schedules = {int(k): v for k, v in loaded_data.items()}
            print(f"Watched schedules loaded from {WATCHED_SCHEDULES_FILE}")
        else:
            print(f"{WATCHED_SCHEDULES_FILE} not found. Starting with no watched channels.")
            watched_schedules = {}
    except Exception as e:
        print(f"Error loading watched schedules from file: {e}")
        watched_schedules = {}


# --- Discord Bot Events ---
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
    load_characters() # Load characters on startup
    load_watched_schedules() # Load watched schedules on startup
    update_warhorn_schedule.start() # Start the scheduled task


@bot.event
async def on_message(message):
    # Always process commands first
    await bot.process_commands(message)

    # Ignore messages from the bot itself to prevent infinite loops
    if message.author == bot.user:
        return

    # Check if the channel is being watched for schedule updates
    channel_id = message.channel.id
    if channel_id in watched_schedules:
        print(f"New message detected in watched channel {channel_id}. Re-posting schedule...")
        
        # Get the current schedule embed and data
        embed, sessions_data = get_warhorn_embed_and_data(False)

        if embed.color == discord.Color.red():
            print(f"Error fetching new Warhorn data for channel {channel_id} on message trigger. Skipping re-post.")
            return

        old_message_info = watched_schedules[channel_id]
        old_message_id = old_message_info["message_id"]

        try:
            # Attempt to delete the old schedule message
            old_message = await message.channel.fetch_message(old_message_id)
            await old_message.delete()
            print(f"Deleted old schedule message {old_message_id} in channel {channel_id}.")
        except discord.NotFound:
            print(f"Old schedule message {old_message_id} not found in channel {channel_id}. It might have been deleted manually.")
            # If not found, no need to stop; just proceed to send a new one
        except discord.Forbidden:
            print(f"Bot does not have permissions to delete messages in channel {channel_id}.")
            await message.channel.send("I don't have permissions to delete messages in this channel! Please grant 'Manage Messages' permission for the schedule to always be recent.")
            # Do not return, try to send new message even if old cannot be deleted
        except Exception as e:
            print(f"Error deleting old message {old_message_id} in channel {channel_id}: {e}. Proceeding to send new message.")
        
        # Send the new schedule message (this will put it at the bottom)
        new_message = await message.channel.send(embed=embed)
        print(f"Re-posted schedule message {new_message.id} in channel {channel_id}.")

        # Update the watched_schedules with the new message ID and current data
        watched_schedules[channel_id]["message_id"] = new_message.id
        watched_schedules[channel_id]["last_sessions_data"] = sessions_data # Also update data in case of content changes
        save_watched_schedules() # Persist the new message ID and data


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
    embed, _ = get_warhorn_embed_and_data(arg) # get_warhorn_embed_and_data now returns embed and data
    if embed.color == discord.Color.red(): # Check for error embed
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
    """Watches this channel for Warhorn schedule updates, ensuring the schedule message is always the most recent."""
    # If this channel is already being watched, delete the old message first
    if ctx.channel.id in watched_schedules:
        old_message_info = watched_schedules[ctx.channel.id]
        try:
            old_message = await ctx.channel.fetch_message(old_message_info["message_id"])
            await old_message.delete()
            print(f"Old schedule message {old_message_info['message_id']} deleted in channel {ctx.channel.id} before re-watching.")
        except discord.NotFound:
            print(f"Old schedule message {old_message_info['message_id']} not found in channel {ctx.channel.id} (might have been deleted manually).")
        except discord.Forbidden:
            print(f"Bot does not have permissions to delete old message {old_message_info['message_id']} in channel {ctx.channel.id}.")
            await ctx.send("I don't have permissions to delete old schedule messages in this channel! Please grant 'Manage Messages' permission.")
        except Exception as e:
            print(f"Error handling old message {old_message_info['message_id']} in watched channel {ctx.channel.id}: {e}")

    embed, sessions_data = get_warhorn_embed_and_data(False)
    if embed.color == discord.Color.red(): # Check for error embed
        await ctx.send(embed=embed)
        return

    # Send the new message (this will put it at the bottom)
    message = await ctx.send(embed=embed)
    print(f"Posted initial schedule message {message.id} in channel {ctx.channel.id} for watching.")

    # Store the channel ID, the message ID of the new message, and the current schedule data
    watched_schedules[ctx.channel.id] = {
        "message_id": message.id,
        "last_sessions_data": sessions_data # Store the data to compare for changes later
    }
    save_watched_schedules() # Save the updated state to file
    await ctx.send("This channel is now being watched for Warhorn schedule updates. The schedule message will always appear at the bottom.")


@bot.command()
async def unwatch(ctx):
    """Stops watching this channel for Warhorn schedule updates and deletes the message."""
    if ctx.channel.id in watched_schedules:
        message_info = watched_schedules[ctx.channel.id]
        try:
            message = await ctx.channel.fetch_message(message_info["message_id"])
            await message.delete()
            del watched_schedules[ctx.channel.id] # Remove from memory
            save_watched_schedules() # Save updated state to file
            await ctx.send("Stopped watching this channel and removed the schedule message.")
            print(f"Stopped watching channel {ctx.channel.id} and deleted message {message_info['message_id']}.")
        except discord.NotFound:
            await ctx.send("No schedule message found to unwatch in this channel (it might have been deleted manually). Removing from watched channels.")
            del watched_schedules[ctx.channel.id] # Clear stale entry in memory
            save_watched_schedules() # Save updated state to file
        except discord.Forbidden:
            await ctx.send("I don't have permissions to delete messages in this channel!")
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
@tasks.loop(minutes=10) # Check for updates every 10 minutes
async def update_warhorn_schedule():
    print("Running scheduled Warhorn schedule update check...")
    if not watched_schedules:
        print("No channels are being watched for schedules.")
        return

    # Iterate over a copy of the dictionary to allow deletion during iteration
    for channel_id, info in list(watched_schedules.items()):
        message_id = info["message_id"]
        last_sessions_data = info["last_sessions_data"] # Retrieve the last known data

        # First, try to get the channel from cache. If not found, fetch it.
        channel = bot.get_channel(channel_id)
        if not channel:
            print(f"Channel {channel_id} not in cache. Attempting to fetch via API...")
            try:
                channel = await bot.fetch_channel(channel_id)
                print(f"Successfully fetched channel {channel_id} via API.")
            except discord.NotFound:
                print(f"Channel {channel_id} not found via API. It might have been deleted or bot removed from guild. Removing from watched_schedules.")
                del watched_schedules[channel_id]
                save_watched_schedules()
                continue # Skip to the next channel
            except discord.Forbidden:
                print(f"Bot forbidden from accessing channel {channel_id} via API. Removing from watched_schedules.")
                del watched_schedules[channel_id]
                save_watched_schedules()
                continue # Skip to the next channel
            except Exception as e:
                print(f"Unexpected error fetching channel {channel_id}: {e}. Skipping update for this channel.")
                continue

        # If we successfully got a channel object (either from cache or API fetch)
        if not channel: # This should ideally not happen if fetches are handled
            print(f"Could not retrieve channel {channel_id} even after API fetch attempt. Removing from watched_schedules.")
            del watched_schedules[channel_id]
            save_watched_schedules()
            continue

        try:
            # Get the new embed and the raw session data from Warhorn
            new_embed, new_sessions_data = get_warhorn_embed_and_data(False)

            if new_embed.color == discord.Color.red(): # Check if there was an error fetching data
                print(f"Error fetching new Warhorn data for channel {channel_id}. Skipping update.")
                continue

            # Compare the new data with the last known data
            # Use json.dumps to compare dictionaries/lists robustly (order-independent if sort_keys=True)
            if json.dumps(new_sessions_data, sort_keys=True) != json.dumps(last_sessions_data, sort_keys=True):
                print(f"Warhorn schedule content changed for channel {channel_id}. Editing message...")
                # Fetch the specific message to edit (it might have been re-posted by on_message)
                message = await channel.fetch_message(message_id)
                await message.edit(embed=new_embed) # EDIT the existing message
                watched_schedules[channel_id]["last_sessions_data"] = new_sessions_data # Update stored data
                save_watched_schedules() # Persist the new data
            else:
                print(f"Warhorn schedule for channel {channel_id} is unchanged.")

        except discord.NotFound:
            print(f"Schedule message {message_id} not found in channel {channel_id}. It might have been deleted manually or by on_message. Removing from watched_schedules.")
            del watched_schedules[channel_id]
            save_watched_schedules()
        except discord.Forbidden:
            print(f"Bot lacks permissions to edit message {message_id} in channel {channel_id}. Removing from watched_schedules.")
            del watched_schedules[channel_id]
            save_watched_schedules()
        except Exception as e:
            print(f"An error occurred during scheduled update for channel {channel_id}: {e}")


@update_warhorn_schedule.before_loop
async def before_update_warhorn_schedule():
    await bot.wait_until_ready() # Wait until the bot is connected and ready
    print("Warhorn schedule update loop ready to start.")
    await asyncio.sleep(5) # Give Discord's cache a moment to populate
    print("Finished initial delay for cache.")


bot.run(discord_token)