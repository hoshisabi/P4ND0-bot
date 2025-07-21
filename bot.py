import datetime
import json
import os
import random
import re # Import re for regex operations
import typing
from datetime import datetime, timezone # Import timezone for Warhorn API calls

import discord
import feedparser
import markdownify # For cleaning RSS summary
import requests
from discord.ext import commands, tasks # Import tasks for the loop
from dotenv import load_dotenv
import asyncio # For the sleep in before_loop

load_dotenv()

discord_token = os.getenv("DISCORD_TOKEN")
rssfeed = os.getenv("FEED_URL")


# --- Define JSON File Paths for Persistence ---
CHARACTERS_FILE = "characters.json"
WATCHED_SCHEDULES_FILE = "watched_schedules.json" # Stores channel_id, message_id
LAST_WARHORN_SESSIONS_FILE = "last_warhorn_sessions.json" # Stores actual data for comparison

# Dictionary to store (channel_id, message_id) for watched schedule messages
# Key: channel_id (int), Value: {"message_id": int, "channel_id": int} (initially)
# After on_ready, Value will be discord.Message objects for live interaction
watched_schedules: typing.Dict[int, typing.Union[discord.Message, typing.Dict[str, int]]] = {}

# Dictionary to store the last known Warhorn session data for comparison
# Key: channel_id (int), Value: list_of_dicts (the raw sessions data from Warhorn)
last_warhorn_sessions_data: typing.Dict[int, typing.List[typing.Dict]] = {}

# Dictionary to store characters per user
# Key: user_id (int)
# Value: list of {"url": original_url, "name": character_name, "avatar_url": avatar_url}
characters: typing.Dict[int, typing.List[typing.Dict[str, str]]] = {}


# --- Persistence Functions (using local JSON files) ---
def save_watched_schedules():
    try:
        # Convert discord.Message objects back to dictionaries for serialization
        serializable_watched_schedules = {}
        for channel_id, msg_or_data in watched_schedules.items():
            if isinstance(msg_or_data, discord.Message):
                serializable_watched_schedules[str(channel_id)] = {
                    "channel_id": msg_or_data.channel.id,
                    "message_id": msg_or_data.id
                }
            elif isinstance(msg_or_data, dict): # In case it's still just IDs from load
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
                # Convert channel_id keys back to int
                # Store as dicts for now; discord.Message objects will be fetched in on_ready
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
        # channel_id keys need to be strings for JSON if they are ints/longs
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
                # Convert channel_id keys back to int
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
        # Convert user_id keys to strings for JSON serialization
        serializable_characters = {str(k): v for k, v in characters.items()}
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
                # Convert user_id keys back to int
                characters = {int(k): v for k, v in loaded_data.items()}
            print(f"Characters loaded from {CHARACTERS_FILE}")
        else:
            print(f"{CHARACTERS_FILE} not found. Starting with empty characters.")
            characters = {}
    except Exception as e:
        print(f"Error loading characters from file: {e}")
        characters = {}


# --- Warhorn API Related ---
WARHORN_APPLICATION_TOKEN = os.getenv("WARHORN_APPLICATION_TOKEN")
WARHORN_API_ENDPOINT = "https://warhorn.net/graphql"

event_sessions_query = """
query EventSessions($events: [String!]!, $now: DateTime!) {
  eventSessions(events: $events, startsAt_gte: $now) {
    nodes {
      id
      name
      startsAt
      location
      maxPlayers
      availablePlayerSeats
      gmSignups {
        user {
          name
        }
      }
      playerSignups {
        user {
          name
        }
      }
      scenario {
        name
        gameSystem {
          name
        }
      }
    }
  }
}
"""

class WarhornClient:
    def __init__(self, api_endpoint, app_token):
        self.api_endpoint = api_endpoint
        self.app_token = app_token

    def run_query(self, query, variables=None):
        headers = {
            "Authorization": f"Bearer {self.app_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        response = requests.post(self.api_endpoint, headers=headers, data=json.dumps(payload))
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        try:
            return response.json()
        except json.JSONDecodeError as e:
            print(f"JSON decoding error from Warhorn API: {e}")
            print(f"Warhorn API raw response content: {response.text}")
            raise

    def get_event_sessions(self, event_slug):
        # Pass the current UTC time for startsAt_gte filter
        current_utc_time = datetime.now(timezone.utc).isoformat(timespec='seconds') + 'Z' # ISO 8601 format with Z for UTC
        return self.run_query(event_sessions_query, variables={"events": [event_slug], "now": current_utc_time})

warhorn_client = WarhornClient(WARHORN_API_ENDPOINT, WARHORN_APPLICATION_TOKEN)


# --- Discord Bot Setup ---
description = '''
A placeholder bot for the P4ND0 server, much more will eventually be here
but right now, it's just a very basic thing. Look for more capabilities later!
'''

intents = discord.Intents.default()
intents.message_content = True # Needed for on_message to read content
intents.members = True # Needed for certain member-related operations, like fetching members if bot restarts

bot = commands.Bot(command_prefix='$', description=description, intents=intents)


# --- Discord Bot Events ---
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
    load_characters() # Load characters on startup
    load_watched_schedules() # Load watched schedules (as dicts with IDs)
    load_last_warhorn_sessions_data() # Load last known Warhorn data

    # After loading, try to fetch the actual message objects for watched_schedules
    # This loop ensures that the bot can interact with the messages it's supposed to watch
    channels_to_remove = []
    # Iterate over a copy of the dictionary because we might modify it during iteration
    for channel_id, data_or_message in list(watched_schedules.items()): 
        if isinstance(data_or_message, discord.Message): # Already a Message object, skip
            continue 

        # It's a dictionary with IDs, so try to fetch the actual Message object
        message_id = data_or_message.get("message_id")
        # channel_id is the key, so we already have it

        try:
            channel = bot.get_channel(channel_id) # Try cache first
            if not channel: # Not in cache, fetch
                channel = await bot.fetch_channel(channel_id)
            
            if channel:
                message = await channel.fetch_message(message_id)
                watched_schedules[channel_id] = message # Replace dict with actual Message object
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

    # Clean up any channels that couldn't be fetched
    for ch_id in channels_to_remove:
        if ch_id in watched_schedules:
            del watched_schedules[ch_id]
        if ch_id in last_warhorn_sessions_data:
            del last_warhorn_sessions_data[ch_id]
    save_watched_schedules() # Save the cleaned list
    save_last_warhorn_sessions_data() # Save cleaned data
    
    update_warhorn_schedule.start() # Start the scheduled task


# --- get_warhorn_embed helper function ---
def get_warhorn_embed_and_data(full: bool): # Renamed to return both embed and raw data
    desc_text = """# Schedule
The following games are upcoming on this server, click on a link to schedule a seat.

"""
    pandodnd_slug = "pandodnd"
    try:
        result = warhorn_client.get_event_sessions(pandodnd_slug)
        # print(f"Warhorn API response: {json.dumps(result, indent=2)}") # Debug print

        if "data" not in result or "eventSessions" not in result["data"] or "nodes" not in result["data"]["eventSessions"]:
            print("Unexpected Warhorn API response structure or no data.")
            return discord.Embed(title="Schedule Error", description="Could not retrieve schedule from Warhorn. Please try again later.", color=discord.Color.red()), []

        sessions_data = sorted( # Store this raw data for comparison
            result["data"]["eventSessions"]["nodes"],
            key=lambda x: datetime.fromisoformat(x["startsAt"].replace("Z", "+00:00")) # Ensure timezone awareness for sorting
        )

        if not sessions_data:
            embed = discord.Embed(title="Warhorn Schedule", description="No upcoming sessions found.", color=discord.Color.blue())
            embed.set_footer(text="Updates every 10 minutes or on channel activity.")
            return embed, sessions_data

        for session in sessions_data:
            session_name = session["name"]
            session_id = session["id"].replace("EventSession-", "") # Remove prefix for URL
            session_start_str = session["startsAt"]
            session_location = session["location"]
            max_players = session["maxPlayers"]
            available_seats = session["availablePlayerSeats"]
            scenario_name = session["scenario"]["name"] if session["scenario"] else "N/A"
            game_system_name = session["scenario"]["gameSystem"]["name"] if session["scenario"] and session["scenario"]["gameSystem"] else "N/A"
            gm_name = session["gmSignups"][0]["user"]["name"] if session["gmSignups"] else "No GM"
            players_signed_up = len(session["playerSignups"])

            # Convert startsAt to a readable local time (e.g., Eastern Time)
            from pytz import timezone # pytz needs to be installed: pip install pytz
            utc_dt = datetime.fromisoformat(session_start_str.replace("Z", "+00:00"))
            eastern = timezone('America/New_York') # Assuming Romulus, Michigan is Eastern Time
            local_dt = utc_dt.astimezone(eastern)

            time_str = local_dt.strftime("%A, %B %d, %I:%M %p %Z") # e.g., Monday, July 22, 07:00 PM EDT

            warhorn_url = f"https://warhorn.net/events/{pandodnd_slug}/schedule/sessions/{session_id}"

            desc_text += (
                f"### [{session_name}]({warhorn_url})\n"
                f"**System:** {game_system_name}\n"
                f"**Scenario:** {scenario_name}\n"
                f"**When:** {time_str}\n"
                f"**GM:** {gm_name}\n"
                f"**Players:** {players_signed_up}/{max_players} ({available_seats} seats left)\n"
                f"**Location:** {session_location}\n\n"
            )

        embed = discord.Embed(
            title="Warhorn Schedule for P4ND0",
            description=desc_text,
            color=discord.Color.blue(),
            url=f"https://warhorn.net/events/{pandodnd_slug}/schedule" # Link the title to the main schedule
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
        # Regex to extract the character ID from the URL
        match = re.search(r"characters/(\d+)", character_url)
        if not match:
            await ctx.send("Please provide a valid D&D Beyond character URL (e.g., `https://www.dndbeyond.com/characters/1234567`).")
            return

        character_id = match.group(1)
        json_api_url = f"https://character-service.dndbeyond.com/character/v5/character/{character_id}"

        try:
            print(f"Fetching character data from: {json_api_url}") # Debug print
            response = requests.get(json_api_url)
            response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
            char_data = response.json()

            if not char_data or "data" not in char_data:
                await ctx.send("Could not retrieve character data from D&D Beyond. The character might be private or the ID is incorrect.")
                print(f"D&D Beyond API response missing 'data' key: {char_data}") # Debug print
                return

            char_info = char_data["data"]
            character_name = char_info.get("name", "Unknown Character")
            if not character_name and char_info.get("username"):
                 character_name = char_info.get("username")
            
            avatar_url = char_info.get("decorations", {}).get("avatarUrl")

            print(f"Extracted Character Name: {character_name}") # Debug print
            print(f"Extracted Avatar URL: {avatar_url}") # Debug print

            # Check if character already exists for the user and update it
            found = False
            for i, char_entry in enumerate(user_characters):
                if char_entry["url"] == character_url:
                    user_characters[i] = {"url": character_url, "name": character_name, "avatar_url": avatar_url}
                    found = True
                    break
            if not found:
                user_characters.append({"url": character_url, "name": character_name, "avatar_url": avatar_url})

            save_characters()

            # Create the embed
            try:
                embed = discord.Embed(
                    title=f"Character Added/Updated: {character_name}",
                    url=character_url,
                    color=discord.Color.gold()
                )
                if avatar_url:
                    embed.set_thumbnail(url=avatar_url)
                embed.set_footer(text=f"Saved for {ctx.author.display_name}")

                print(f"Attempting to send embed: {embed.to_dict()}") # Debug print: See the full embed content
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
        # List saved characters
        if not user_characters:
            await ctx.send("You have no D&D Beyond characters saved. Use `$character <D&D Beyond URL>` to add one.")
            return

        embed = discord.Embed(
            title=f"{ctx.author.display_name}'s Saved D&D Beyond Characters", # More specific title
            color=discord.Color.purple()
        )
        description_parts = []
        for char_entry in user_characters:
            char_name = char_entry.get("name", "Unknown Character")
            char_url = char_entry.get("url", "#")
            description_parts.append(f"• [{char_name}]({char_url})")

        embed.description = "\n".join(description_parts)
        embed.set_footer(text="Click on a character name to view it on D&D Beyond.")
        await ctx.send(embed=embed)


@bot.command()
async def schedule(ctx, full: typing.Optional[bool] = False):
    """Pulls the most recent schedule of upcoming events from Warhorn displayed in local time.
    Pass 'True' to get full details of events (though current implementation always gives details).
    """
    # Renamed variable to avoid confusion with the command parameter 'full'
    embed_to_send, _ = get_warhorn_embed_and_data(full) # full parameter is not currently used by internal logic

    if embed_to_send.color == discord.Color.red(): # Check for error embed
        await ctx.send(embed=embed_to_send)
        return
    await ctx.send(embed=embed_to_send)


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
    embed_to_send, sessions_data = get_warhorn_embed_and_data(False) # Get current schedule and raw data

    if embed_to_send.color == discord.Color.red(): # Check for error embed
        await ctx.send(embed=embed_to_send) # Send the error embed
        return

    # Delete existing watched message if any for this channel before posting a new one
    channel_id = ctx.channel.id
    old_message_object = watched_schedules.get(channel_id)
    
    if old_message_object and isinstance(old_message_object, discord.Message):
        try:
            await old_message_object.delete()
            print(f"Deleted old schedule message {old_message_object.id} in channel {ctx.channel.name} before setting new watch.")
        except discord.NotFound:
            print(f"Old schedule message {old_message_object.id} for {ctx.channel.name} not found on delete attempt, proceeding.")
        except discord.Forbidden:
            print(f"Bot lacks permissions to delete old message {old_message_object.id} in {ctx.channel.name}.")
            await ctx.send("Warning: I couldn't delete the previous schedule message. Please ensure I have 'Manage Messages' permission.")
        except Exception as e:
            print(f"Error handling old message {old_message_object.id} in watched channel {ctx.channel.name}: {e}")

    # Send the new message (this will put it at the bottom)
    message = await ctx.send(embed=embed_to_send)
    
    # Store the channel ID and the message object
    watched_schedules[channel_id] = message
    # Store the raw sessions data for comparison by the scheduled task
    last_warhorn_sessions_data[channel_id] = sessions_data 

    save_watched_schedules() # Save the updated state to file
    save_last_warhorn_sessions_data() # Save the initial sessions data

    print(f"Set to watch channel {ctx.channel.name} ({channel_id}) with message ID {message.id}.")
    await ctx.send(f"This channel is now being watched for Warhorn schedule updates. I will keep the schedule at the bottom of the channel.")


@bot.command()
async def unwatch(ctx):
    """Stops watching this channel for Warhorn schedule updates and deletes the message."""
    channel_id = ctx.channel.id
    if channel_id in watched_schedules:
        message_object = watched_schedules.pop(channel_id) # Remove from memory first
        last_warhorn_sessions_data.pop(channel_id, None) # Remove its last data as well

        try:
            if isinstance(message_object, discord.Message): # Try to delete the last posted message if it's a valid object
                await message_object.delete()
                print(f"Deleted schedule message {message_object.id} in {ctx.channel.name} and unwatched.")
            else:
                # If it's not a discord.Message object (e.g., just IDs from load), it can't be deleted directly
                print(f"Unwatched channel {ctx.channel.name} but no message object to delete (was likely from initial load).")
            
            await ctx.send(f"This channel is no longer being watched for Warhorn schedule updates.")
            save_watched_schedules() # Save changes to file
            save_last_warhorn_sessions_data()
        except discord.NotFound:
            print(f"Message not found when trying to delete for unwatch in {ctx.channel.name} ({channel_id}). Already gone?")
            await ctx.send(f"This channel is no longer being watched, but I couldn't find the message to delete (it might have been deleted manually).")
            save_watched_schedules() # Still save to unwatch it
            save_last_warhorn_sessions_data()
        except discord.Forbidden:
            print(f"Bot lacks permissions to delete message in {ctx.channel.name} ({channel_id}).")
            await ctx.send(f"This channel is no longer being watched, but I couldn't delete the message. Please delete it manually.")
            save_watched_schedules()
            save_last_warhorn_sessions_data()
        except Exception as e:
            await ctx.send(f"An error occurred while unwatching: {e}")
            print(f"Error unwatching channel {ctx.channel.name} ({channel_id}): {e}")
    else:
        await ctx.send("This channel is not currently being watched.")


@bot.command()
async def roll(ctx, dice: str):
    """Rolls a dice in NdN format."""
    try:
        rolls, limit = map(int, dice.lower().split('d')) # .lower() to handle 'D'
        if rolls <= 0 or limit <= 0:
            await ctx.send('Number of rolls and dice faces must be positive!')
            return
        if rolls > 1000: # Prevent spam/abuse
            await ctx.send('Please do not roll more than 1000 dice at once.')
            return
        if limit > 1000000: # Prevent extremely large dice
            await ctx.send('Dice faces must be 1,000,000 or less.')
            return
    except ValueError:
        await ctx.send('Format has to be in NdN (e.g., `2d6`)!')
        return

    results = [random.randint(1, limit) for _ in range(rolls)]
    result_str = ', '.join(map(str, results))

    if len(result_str) > 1000: # Keep it within reasonable limits for a single field
        result_str = result_str[:1000] + "..." # Truncate if too long

    embed = discord.Embed(title="Dice Roll", description=f"{rolls}d{limit}", color=discord.Color.blue())
    embed.add_field(name="Results", value=result_str, inline=False)
    if rolls > 1:
        embed.add_field(name="Total", value=sum(results), inline=False)

    print(f"Dice result: {result_str}")
    await ctx.send(embed=embed)


# --- Scheduled Task to Update Warhorn Schedule ---
@tasks.loop(minutes=10) # Check for updates every 10 minutes
async def update_warhorn_schedule():
    # Only run this if the bot is ready and there are channels being watched
    if not bot.is_ready() or not watched_schedules:
        print("Scheduled update skipped: Bot not ready or no channels watched.")
        return

    print("Running scheduled Warhorn schedule update check...")
    
    new_embed, new_sessions_data = get_warhorn_embed_and_data(False) # Get the latest schedule and its raw data

    if new_embed.color == discord.Color.red(): # Check if there was an error fetching data
        print("Scheduled update: Error fetching new Warhorn data. Skipping update for all channels.")
        return # Don't try to update messages with error data

    # Compare the new data with the stored last_sessions_data
    new_sessions_json = json.dumps(new_sessions_data, sort_keys=True)

    channels_to_remove = []
    # Iterate over a copy of the dictionary to allow deletion during iteration
    for channel_id, message_object in list(watched_schedules.items()):
        if not isinstance(message_object, discord.Message): # If it's not a message object yet, skip
            print(f"Scheduled update: Message object for channel {channel_id} not yet fetched. Skipping.")
            continue # Skip if the message object hasn't been fetched by on_ready yet

        last_sessions_json = json.dumps(last_warhorn_sessions_data.get(channel_id, []), sort_keys=True) # Default to empty list if no data

        if new_sessions_json != last_sessions_json:
            print(f"Warhorn schedule content changed for channel {message_object.channel.name}. Editing message...")
            try:
                # Edit the existing message object
                await message_object.edit(embed=new_embed)
                last_warhorn_sessions_data[channel_id] = new_sessions_data # Update stored data
                save_last_warhorn_sessions_data() # Persist the new data
                print(f"Edited schedule message {message_object.id} in {message_object.channel.name}.")
            except discord.NotFound:
                print(f"Scheduled update: Message {message_object.id} not found in channel {message_object.channel.name}. It might have been deleted manually or by on_message. Removing from watched_schedules.")
                channels_to_remove.append(channel_id)
            except discord.Forbidden:
                print(f"Scheduled update: Bot lacks permissions to edit message {message_object.id} in channel {message_object.channel.name}. Removing from watched_schedules.")
                channels_to_remove.append(channel_id)
            except Exception as e:
                print(f"An error occurred during scheduled update for channel {message_object.channel.name}: {e}")
        else:
            print(f"Warhorn schedule for channel {message_object.channel.name} is unchanged (content-wise).")

    # Clean up any channels that caused errors
    for ch_id in channels_to_remove:
        if ch_id in watched_schedules:
            del watched_schedules[ch_id]
        if ch_id in last_warhorn_sessions_data:
            del last_warhorn_sessions_data[ch_id]
    save_watched_schedules() # Save the cleaned list
    save_last_warhorn_sessions_data() # Save cleaned data


@update_warhorn_schedule.before_loop
async def before_update_warhorn_schedule():
    await bot.wait_until_ready() # Wait until the bot is connected and ready
    print("Warhorn schedule update loop ready to start.")
    await asyncio.sleep(5) # Give Discord's cache a moment to populate
    print("Finished initial delay for cache.")


bot.run(discord_token)