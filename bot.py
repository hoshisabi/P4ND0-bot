import datetime
import json
import os
import random
import typing
from datetime import datetime, timezone
import asyncio
import re # Import re for regex operations

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import requests 

# Import the WarhornClient from your warhorn_api.py file
from warhorn_api import WarhornClient

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
async def get_warhorn_embed_and_data(full: bool): 
    desc_text = """The following games are upcoming on this server, click on a link to schedule a seat.

"""
    pandodnd_slug = "pandodnd"
    try:
        # Get all session data, including uuid
        initial_result = warhorn_client.get_event_sessions(pandodnd_slug)

        if "data" not in initial_result or "eventSessions" not in initial_result["data"] or "nodes" not in initial_result["data"]["eventSessions"]:
            print("Unexpected Warhorn API response structure or no data from initial fetch.")
            return discord.Embed(title="Schedule Error", description="Could not retrieve schedule from Warhorn. Please try again later.", color=discord.Color.red()), []

        sessions_to_display = sorted(
            initial_result["data"]["eventSessions"]["nodes"],
            key=lambda x: datetime.fromisoformat(x["startsAt"].replace("Z", "+00:00"))
        )

        if not sessions_to_display:
            embed = discord.Embed(title="Upcoming Warhorn Events", description="No upcoming sessions found.", color=discord.Color.blue())
            return embed, sessions_to_display


        for session in sessions_to_display: 
            session_name = session["name"]
            
            # MODIFIED: Construct warhorn_url using the 'uuid'
            session_uuid = session.get("uuid")
            if session_uuid:
                warhorn_url = f"https://warhorn.net/events/{pandodnd_slug}/schedule/sessions/{session_uuid}"
            else:
                warhorn_url = f"https://warhorn.net/events/{pandodnd_slug}/schedule" # Fallback to main schedule link if UUID is missing
            
            session_start_str = session["startsAt"]
            session_location = session["location"] 
            scenario_name = session["scenario"]["name"] if session["scenario"] else "N/A"
            game_system_name = session["scenario"]["gameSystem"]["name"] if session["scenario"] and session["scenario"]["gameSystem"] else "N/A"
            
            max_players = session["maxPlayers"]
            available_seats = session["availablePlayerSeats"]
            gm_name = session["gmSignups"][0]["user"]["name"] if session["gmSignups"] else "No GM"
            
            # --- Player List Logic: Now parsing names for embedded Discord tags ---
            parsed_player_names = []
            for signup in session["playerSignups"]:
                full_player_name = signup["user"]["name"]
                # Regex to match "DiscordTag (Real Name)" or just "Name)"
                match = re.match(r"^(.*?)(?:\s*\((.*)\))?$", full_player_name)
                if match:
                    discord_tag_or_primary_name = match.group(1).strip()
                    real_name_in_parentheses = match.group(2)

                    if real_name_in_parentheses:
                        parsed_player_names.append(f"{real_name_in_parentheses} ({discord_tag_or_primary_name})")
                    else:
                        parsed_player_names.append(discord_tag_or_primary_name)
                else:
                    parsed_player_names.append(full_player_name)

            if parsed_player_names:
                players_list_str = ", ".join(parsed_player_names)
            else:
                players_list_str = "No players signed up"

            waitlist_names = []
            if session.get("playerWaitlistEntries"): # Check if the key exists and is not empty
                for entry in session["playerWaitlistEntries"]:
                    if entry.get("user") and entry["user"].get("name"):
                        waitlist_names.append(entry["user"]["name"])

            status_line = ""
                
            if available_seats > 0:
                status_line = f"* 🟢 **Status:** {available_seats} slots available!"
            elif waitlist_names: # Checks if the list 'waitlist_names' is not empty
                status_line = f"* 🟡 **Waitlist:** {', '.join(waitlist_names)}"
            else:
                # This branch means available_seats is 0 AND waitlist_names is empty
                status_line = "* 🟡 **Status:** Full (empty waitlist) "

            # Convert to Unix timestamp for Discord's specialized time handling
            utc_dt = datetime.fromisoformat(session_start_str.replace("Z", "+00:00"))
            unix_timestamp = int(utc_dt.timestamp())
            
            # Format using Discord's timestamp markdown (F for Long Date/Time)
            time_str = f"<t:{unix_timestamp}:F>"

            session_block = f"**[{session_name}]({warhorn_url})**  \n"
            session_block += f"* 📅 **When:** {time_str}  \n"
            session_block += f"* 🧙‍ **GM:** ️ {gm_name}  \n"
            session_block += f"* 👥 **Players:** {players_list_str}  \n"
            session_block += f"{status_line}  \n"
            
            session_block += "\n" 

            desc_text += session_block # This line appends to desc_text

        desc_text += ("*Join the waitlist to be next in line if there is a cancellation.*\n"
                      "*If you are on a waitlist, you may still get a spot due to cancellations.*\n"
                      "*If you still are unable to attend, I will schedule an encore session and sign you up in advance.*\n")
        embed = discord.Embed(
            title="Upcoming Warhorn Events",
            description=desc_text, # This is the final description
            color=discord.Color.blue(),
            url=f"https://warhorn.net/events/{pandodnd_slug}/schedule"
        )
        return embed, sessions_to_display 

    except requests.exceptions.RequestException as e:
        print(f"Error fetching Warhorn schedule: {e}")
        return discord.Embed(title="Schedule Error", description=f"Could not retrieve schedule from Warhorn due to a network error: {e}", color=discord.Color.red()), []
    except Exception as e:
        print(f"An unexpected error occurred in get_warhorn_embed_and_data: {e}")
        return discord.Embed(title="Schedule Error", description=f"An unexpected error occurred while fetching schedule: {e}", color=discord.Color.red()), []


# --- Discord Bot Commands ---
@bot.command()
async def schedule(ctx, full: typing.Optional[bool] = False):
    """Pulls the most recent schedule of upcoming events from Warhorn displayed in your local time."""
    embed_to_send, _ = await get_warhorn_embed_and_data(full) 

    if embed_to_send.color == discord.Color.red():
        await ctx.send(embed=embed_to_send)
        return
    await ctx.send(embed=embed_to_send)


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
        embed.set_footer(text="Click on a character name to view it on D&D Beyond.")
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
    embed_to_send, sessions_data = await get_warhorn_embed_and_data(False)

    if embed_to_send.color == discord.Color.red():
        await ctx.send(embed=embed_to_send)
        return

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

    message = await ctx.send(embed=embed_to_send)
    
    watched_schedules[channel_id] = message
    last_warhorn_sessions_data[channel_id] = sessions_data 

    save_watched_schedules()
    save_last_warhorn_sessions_data()

    print(f"Set to watch channel {ctx.channel.name} ({channel_id}) with message ID {message.id}.")
    await ctx.send(f"This channel is now being watched for Warhorn schedule updates. I will keep the schedule at the bottom of the channel.")


@bot.command()
async def unwatch(ctx):
    """Stops watching this channel for Warhorn schedule updates and deletes the message."""
    channel_id = ctx.channel.id
    if channel_id in watched_schedules:
        message_object = watched_schedules.pop(channel_id)
        last_warhorn_sessions_data.pop(channel_id, None)

        try:
            if isinstance(message_object, discord.Message):
                await message_object.delete()
                print(f"Deleted schedule message {message_object.id} in {ctx.channel.name} and unwatched.")
            else:
                print(f"Unwatched channel {ctx.channel.name} but no message object to delete (was likely from initial load).")
            
            await ctx.send(f"This channel is no longer being watched for Warhorn schedule updates.")
            save_watched_schedules()
            save_last_warhorn_sessions_data()
        except discord.NotFound:
            print(f"Message not found when trying to delete for unwatch in {ctx.channel.name} ({channel_id}). Already gone?")
            await ctx.send(f"This channel is no longer being watched, but I couldn't find the message to delete (it might have been deleted manually).")
            save_watched_schedules()
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


# --- Scheduled Task to Update Warhorn Schedule ---
@tasks.loop(minutes=10)
async def update_warhorn_schedule():
    if not bot.is_ready() or not watched_schedules:
        print("Scheduled update skipped: Bot not ready or no channels watched.")
        return

    print("Running scheduled Warhorn schedule update check...")
    
    new_embed, new_sessions_data = await get_warhorn_embed_and_data(False) 

    if new_embed.color == discord.Color.red():
        print("Scheduled update: Error fetching new Warhorn data. Skipping update for all channels.")
        return

    # Canonicalized representations for comparisons
    try:
        new_sessions_json = json.dumps(new_sessions_data, sort_keys=True, default=str)
        new_embed_sig = json.dumps(new_embed.to_dict(), sort_keys=True, default=str)
    except Exception as e:
        print(f"Error serializing new embed/sessions for comparison: {e}")
        return

    # Helper to format a channel label safely (works for guild channels and DMs)
    def _chan_label(ch) -> str:
        try:
            # Guild channels (TextChannel, Thread, etc.)
            if isinstance(ch, discord.abc.GuildChannel):
                return f"#{ch.name}"
            # 1:1 DM
            if isinstance(ch, discord.DMChannel):
                user = getattr(ch, "recipient", None)
                return f"DM with {user}" if user else "DM"
            # Group DM
            if isinstance(ch, discord.GroupChannel):
                recips = getattr(ch, "recipients", None) or []
                if recips:
                    names = ", ".join(str(u) for u in recips[:3])
                    more = f" +{len(recips)-3} more" if len(recips) > 3 else ""
                    return f"Group DM ({names}{more})"
                return "Group DM"
        except Exception:
            pass
        return f"Channel {getattr(ch, 'id', 'unknown')}"

    channels_to_remove = []
    for channel_id, message_object in list(watched_schedules.items()):
        if not isinstance(message_object, discord.Message):
            print(f"Scheduled update: Message object for channel {channel_id} not yet fetched. Skipping.")
            continue

        try:
            channel = message_object.channel
            chan_label = _chan_label(channel)

            # 1) Ensure the schedule message stays at the bottom:
            try:
                last_message = None
                async for m in channel.history(limit=1):
                    last_message = m
                if last_message and last_message.id != message_object.id:
                    print(f"Schedule is not the last message in {chan_label}. Reposting at the bottom...")
                    try:
                        await message_object.delete()
                    except discord.NotFound:
                        print(f"Old schedule message {message_object.id} already deleted in {chan_label}.")
                    except discord.Forbidden:
                        print(f"Forbidden deleting old schedule message {message_object.id} in {chan_label}.")

                    # Post a fresh message at the bottom
                    new_msg = await channel.send(embed=new_embed)
                    watched_schedules[channel_id] = new_msg
                    last_warhorn_sessions_data[channel_id] = new_sessions_data
                    save_watched_schedules()
                    save_last_warhorn_sessions_data()
                    print(f"Reposted schedule as message {new_msg.id} in {chan_label}.")
                    # Since we replaced the message, continue to next channel
                    continue
            except Exception as e:
                print(f"Error while ensuring bottom message in {chan_label}: {e}")

            # 2) Check if content needs updating (even if sessions list is the same)
            try:
                last_sessions_json = json.dumps(
                    last_warhorn_sessions_data.get(channel_id, []),
                    sort_keys=True,
                    default=str
                )
            except Exception as e:
                print(f"Error serializing previous sessions for channel {channel_id}: {e}")
                last_sessions_json = "[]"

            current_embed_sig = None
            try:
                if message_object.embeds:
                    current_embed_sig = json.dumps(message_object.embeds[0].to_dict(), sort_keys=True, default=str)
            except Exception as e:
                print(f"Error reading current embed for message {message_object.id} in {chan_label}: {e}")

            sessions_changed = (new_sessions_json != last_sessions_json)
            embed_changed = (current_embed_sig != new_embed_sig)

            if sessions_changed or embed_changed:
                print(f"Updating schedule message in {chan_label} (sessions_changed={sessions_changed}, embed_changed={embed_changed})...")
                try:
                    await message_object.edit(embed=new_embed)
                    last_warhorn_sessions_data[channel_id] = new_sessions_data
                    save_last_warhorn_sessions_data()
                    print(f"Edited schedule message {message_object.id} in {chan_label}.")
                except discord.NotFound:
                    print(f"Scheduled update: Message {message_object.id} not found in {chan_label}. Removing from watch.")
                    channels_to_remove.append(channel_id)
                except discord.Forbidden:
                    print(f"Scheduled update: Forbidden editing message {message_object.id} in {chan_label}. Removing from watch.")
                    channels_to_remove.append(channel_id)
                except Exception as e:
                    print(f"Error editing schedule message in {chan_label}: {e}")
            else:
                print(f"Warhorn schedule for {chan_label} is unchanged (sessions and embed).")

        except Exception as e:
            print(f"Unexpected error handling channel {channel_id}: {e}")

    for ch_id in channels_to_remove:
        if ch_id in watched_schedules:
            del watched_schedules[ch_id]
        if ch_id in last_warhorn_sessions_data:
            del last_warhorn_sessions_data[ch_id]
    save_watched_schedules()
    save_last_warhorn_sessions_data()


@update_warhorn_schedule.before_loop
async def before_update_warhorn_schedule():
    await bot.wait_until_ready()
    print("Warhorn schedule update loop ready to start.")
    await asyncio.sleep(5)
    print("Finished initial delay for cache.")


bot.run(discord_token)