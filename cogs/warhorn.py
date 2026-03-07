import os
import json
import re
import asyncio
from datetime import datetime, timezone
import requests

import discord
from discord.ext import commands, tasks
from utils.persistence import save_json_data, load_json_data
from warhorn_api import WarhornClient

WATCHED_SCHEDULES_FILE = "watched_schedules.json"
LAST_WARHORN_SESSIONS_FILE = "last_warhorn_sessions.json"

class Warhorn(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.watched_schedules = load_json_data(WATCHED_SCHEDULES_FILE, f"{WATCHED_SCHEDULES_FILE} not found. Starting with no watched channels.")
        if self.watched_schedules:
            print(f"Watched schedules loaded from {WATCHED_SCHEDULES_FILE} (IDs only, messages will be fetched).")
            
        self.last_warhorn_sessions_data = load_json_data(LAST_WARHORN_SESSIONS_FILE, f"{LAST_WARHORN_SESSIONS_FILE} not found. Starting with no last sessions data.")
        if self.last_warhorn_sessions_data:
            print(f"Last Warhorn sessions data loaded from {LAST_WARHORN_SESSIONS_FILE}")
            
        WARHORN_APPLICATION_TOKEN = os.getenv("WARHORN_APPLICATION_TOKEN")
        WARHORN_API_ENDPOINT = "https://warhorn.net/graphql"
        self.warhorn_client = WarhornClient(WARHORN_API_ENDPOINT, WARHORN_APPLICATION_TOKEN)
        
        self.update_warhorn_schedule.start()

    def cog_unload(self):
        self.update_warhorn_schedule.cancel()

    def save_watched_schedules(self):
        serializable_watched_schedules = {}
        for channel_id, msg_or_data in self.watched_schedules.items():
            if isinstance(msg_or_data, discord.Message):
                serializable_watched_schedules[str(channel_id)] = {
                    "channel_id": msg_or_data.channel.id,
                    "message_id": msg_or_data.id
                }
            elif isinstance(msg_or_data, dict):
                 serializable_watched_schedules[str(channel_id)] = msg_or_data
        save_json_data(WATCHED_SCHEDULES_FILE, serializable_watched_schedules, f"Watched schedules saved to {WATCHED_SCHEDULES_FILE}")

    def save_last_warhorn_sessions_data(self):
        serializable_data = {str(k): v for k, v in self.last_warhorn_sessions_data.items()}
        save_json_data(LAST_WARHORN_SESSIONS_FILE, serializable_data, f"Last Warhorn sessions data saved to {LAST_WARHORN_SESSIONS_FILE}")

    @commands.Cog.listener()
    async def on_ready(self):
        channels_to_remove = []
        for channel_id, data_or_message in list(self.watched_schedules.items()): 
            if isinstance(data_or_message, discord.Message):
                continue 

            message_id = data_or_message.get("message_id")

            try:
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    channel = await self.bot.fetch_channel(channel_id)
                
                if channel:
                    message = await channel.fetch_message(message_id)
                    self.watched_schedules[channel_id] = message
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
            if ch_id in self.watched_schedules:
                del self.watched_schedules[ch_id]
            if ch_id in self.last_warhorn_sessions_data:
                del self.last_warhorn_sessions_data[ch_id]
        self.save_watched_schedules()
        self.save_last_warhorn_sessions_data()

    async def get_warhorn_embed_and_data(self, full: bool): 
        desc_text = "The following games are upcoming on this server, click on a link to schedule a seat.\n\n"
        pandodnd_slug = "pandodnd"
        try:
            initial_result = self.warhorn_client.get_event_sessions(pandodnd_slug)

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
                
                session_uuid = session.get("uuid")
                if session_uuid:
                    warhorn_url = f"https://warhorn.net/events/{pandodnd_slug}/schedule/sessions/{session_uuid}"
                else:
                    warhorn_url = f"https://warhorn.net/events/{pandodnd_slug}/schedule" 
                
                session_start_str = session["startsAt"]
                gm_name = session["gmSignups"][0]["user"]["name"] if session["gmSignups"] else "No GM"
                available_seats = session["availablePlayerSeats"]
                
                parsed_player_names = []
                for signup in session["playerSignups"]:
                    full_player_name = signup["user"]["name"]
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
                if session.get("playerWaitlistEntries"): 
                    for entry in session["playerWaitlistEntries"]:
                        if entry.get("user") and entry["user"].get("name"):
                            waitlist_names.append(entry["user"]["name"])

                status_line = ""
                if available_seats > 0:
                    status_line = f"* 🟢 **Status:** {available_seats} slots available!"
                elif waitlist_names: 
                    status_line = f"* 🟡 **Waitlist:** {', '.join(waitlist_names)}"
                else:
                    status_line = "* 🟡 **Status:** Full (empty waitlist) "

                utc_dt = datetime.fromisoformat(session_start_str.replace("Z", "+00:00"))
                unix_timestamp = int(utc_dt.timestamp())
                time_str = f"<t:{unix_timestamp}:F>"

                session_block = f"**[{session_name}]({warhorn_url})**  \n"
                session_block += f"* 📅 **When:** {time_str}  \n"
                session_block += f"* 🧙‍ **GM:** ️ {gm_name}  \n"
                session_block += f"* 👥 **Players:** {players_list_str}  \n"
                session_block += f"{status_line}  \n\n"
                
                desc_text += session_block 

            desc_text += ("*Join the waitlist to be next in line if there is a cancellation.*\n"
                          "*If you are on a waitlist, you may still get a spot due to cancellations.*\n"
                          "*If you still are unable to attend, I will schedule an encore session and sign you up in advance.*\n")
            embed = discord.Embed(
                title="Upcoming Warhorn Events",
                description=desc_text, 
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

    @commands.command()
    async def schedule(self, ctx, full: bool = False):
        """Pulls the most recent schedule of upcoming events from Warhorn displayed in your local time."""
        embed_to_send, _ = await self.get_warhorn_embed_and_data(full) 
        await ctx.send(embed=embed_to_send)

    @commands.command()
    async def watch(self, ctx):
        """Watches this channel for Warhorn schedule updates, ensuring the schedule message is always the most recent."""
        embed_to_send, sessions_data = await self.get_warhorn_embed_and_data(False)

        if embed_to_send.color == discord.Color.red():
            await ctx.send(embed=embed_to_send)
            return

        channel_id = ctx.channel.id
        old_message_object = self.watched_schedules.get(channel_id)
        
        if old_message_object and isinstance(old_message_object, discord.Message):
            try:
                await old_message_object.delete()
                print(f"Deleted old schedule message {old_message_object.id} in channel {ctx.channel.name} before setting new watch.")
            except discord.NotFound:
                pass
            except discord.Forbidden:
                await ctx.send("Warning: I couldn't delete the previous schedule message. Please ensure I have 'Manage Messages' permission.")
            except Exception as e:
                print(f"Error handling old message {old_message_object.id}: {e}")

        message = await ctx.send(embed=embed_to_send)
        
        self.watched_schedules[channel_id] = message
        self.last_warhorn_sessions_data[channel_id] = sessions_data 

        self.save_watched_schedules()
        self.save_last_warhorn_sessions_data()

        print(f"Set to watch channel {ctx.channel.name} ({channel_id}) with message ID {message.id}.")
        await ctx.send(f"This channel is now being watched for Warhorn schedule updates. I will keep the schedule at the bottom of the channel.")

    @commands.command()
    async def unwatch(self, ctx):
        """Stops watching this channel for Warhorn schedule updates and deletes the message."""
        channel_id = ctx.channel.id
        if channel_id in self.watched_schedules:
            message_object = self.watched_schedules.pop(channel_id)
            self.last_warhorn_sessions_data.pop(channel_id, None)

            try:
                if isinstance(message_object, discord.Message):
                    await message_object.delete()
                
                await ctx.send(f"This channel is no longer being watched for Warhorn schedule updates.")
                self.save_watched_schedules()
                self.save_last_warhorn_sessions_data()
            except discord.NotFound:
                await ctx.send(f"This channel is no longer being watched, but I couldn't find the message to delete (it might have been deleted manually).")
                self.save_watched_schedules()
                self.save_last_warhorn_sessions_data()
            except discord.Forbidden:
                await ctx.send(f"This channel is no longer being watched, but I couldn't delete the message. Please delete it manually.")
                self.save_watched_schedules()
                self.save_last_warhorn_sessions_data()
            except Exception as e:
                await ctx.send(f"An error occurred while unwatching: {e}")
        else:
            await ctx.send("This channel is not currently being watched.")

    @tasks.loop(minutes=10)
    async def update_warhorn_schedule(self):
        if not self.bot.is_ready() or not self.watched_schedules:
            print("Scheduled update skipped: Bot not ready or no channels watched.")
            return

        print("Running scheduled Warhorn schedule update check...")
        new_embed, new_sessions_data = await self.get_warhorn_embed_and_data(False) 

        if new_embed.color == discord.Color.red():
            print("Scheduled update: Error fetching new Warhorn data. Skipping update for all channels.")
            return

        try:
            new_sessions_json = json.dumps(new_sessions_data, sort_keys=True, default=str)
            new_embed_sig = json.dumps(new_embed.to_dict(), sort_keys=True, default=str)
        except Exception as e:
            print(f"Error serializing new embed/sessions for comparison: {e}")
            return

        def _chan_label(ch) -> str:
            try:
                if isinstance(ch, discord.abc.GuildChannel):
                    return f"#{ch.name}"
                if isinstance(ch, discord.DMChannel):
                    user = getattr(ch, "recipient", None)
                    return f"DM with {user}" if user else "DM"
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
        for channel_id, message_object in list(self.watched_schedules.items()):
            if not isinstance(message_object, discord.Message):
                continue

            try:
                channel = message_object.channel
                chan_label = _chan_label(channel)

                try:
                    last_message = None
                    async for m in channel.history(limit=1):
                        last_message = m
                    if last_message and last_message.id != message_object.id:
                        print(f"Schedule is not the last message in {chan_label}. Reposting at the bottom...")
                        try:
                            await message_object.delete()
                        except:
                            pass

                        new_msg = await channel.send(embed=new_embed)
                        self.watched_schedules[channel_id] = new_msg
                        self.last_warhorn_sessions_data[channel_id] = new_sessions_data
                        self.save_watched_schedules()
                        self.save_last_warhorn_sessions_data()
                        print(f"Reposted schedule as message {new_msg.id} in {chan_label}.")
                        continue
                except Exception as e:
                    print(f"Error while ensuring bottom message in {chan_label}: {e}")

                try:
                    last_sessions_json = json.dumps(
                        self.last_warhorn_sessions_data.get(channel_id, []),
                        sort_keys=True,
                        default=str
                    )
                except Exception as e:
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
                    print(f"Updating schedule message in {chan_label}")
                    try:
                        await message_object.edit(embed=new_embed)
                        self.last_warhorn_sessions_data[channel_id] = new_sessions_data
                        self.save_last_warhorn_sessions_data()
                        print(f"Edited schedule message {message_object.id} in {chan_label}.")
                    except discord.NotFound:
                        channels_to_remove.append(channel_id)
                    except discord.Forbidden:
                        channels_to_remove.append(channel_id)
                    except Exception as e:
                        print(f"Error editing schedule message in {chan_label}: {e}")
                else:
                    print(f"Warhorn schedule for {chan_label} is unchanged (sessions and embed).")

            except Exception as e:
                print(f"Unexpected error handling channel {channel_id}: {e}")

        for ch_id in channels_to_remove:
            if ch_id in self.watched_schedules:
                del self.watched_schedules[ch_id]
            if ch_id in self.last_warhorn_sessions_data:
                del self.last_warhorn_sessions_data[ch_id]
        self.save_watched_schedules()
        self.save_last_warhorn_sessions_data()

    @update_warhorn_schedule.before_loop
    async def before_update_warhorn_schedule(self):
        await self.bot.wait_until_ready()
        print("Warhorn schedule update loop ready to start.")
        await asyncio.sleep(5)
        print("Finished initial delay for cache.")

async def setup(bot):
    await bot.add_cog(Warhorn(bot))
