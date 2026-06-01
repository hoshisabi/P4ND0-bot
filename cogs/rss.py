import json
import os
import re
import asyncio
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks
import feedparser

FEEDS_CONFIG_FILE = "feeds.json"
RSS_SEEN_FILE = "rss_seen.json"
POLL_INTERVAL_MINUTES = 60
MAX_SEEN_PER_FEED = 500


class RSSFeed(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.feeds = self._load_feeds_config()
        self.seen = self._load_seen()
        self.poll_feeds.start()

    def cog_unload(self):
        self.poll_feeds.cancel()

    def _load_feeds_config(self):
        try:
            with open(FEEDS_CONFIG_FILE, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"[RSS] {FEEDS_CONFIG_FILE} not found — no feeds configured.")
            return []
        except Exception as e:
            print(f"[RSS] Error loading {FEEDS_CONFIG_FILE}: {e}")
            return []

    def _load_seen(self):
        try:
            if os.path.exists(RSS_SEEN_FILE):
                with open(RSS_SEEN_FILE, "r") as f:
                    return json.load(f)
        except Exception as e:
            print(f"[RSS] Error loading {RSS_SEEN_FILE}: {e}")
        return {}

    def _save_seen(self):
        try:
            with open(RSS_SEEN_FILE, "w") as f:
                json.dump(self.seen, f, indent=2)
        except Exception as e:
            print(f"[RSS] Error saving {RSS_SEEN_FILE}: {e}")

    def _entry_id(self, entry) -> str:
        return entry.get("id") or entry.get("link") or entry.get("title", "")

    def _strip_html(self, text: str) -> str:
        return re.sub(r"<[^>]+>", "", text).strip()

    def _make_embed(self, entry, feed_name: str) -> discord.Embed:
        title = (entry.get("title") or "No title")[:256]
        link = entry.get("link", "")

        summary = ""
        raw = entry.get("summary") or ""
        if raw:
            summary = self._strip_html(raw)
            if len(summary) > 300:
                summary = summary[:297] + "..."

        published = entry.get("published_parsed") or entry.get("updated_parsed")
        timestamp = None
        if published:
            timestamp = datetime(*published[:6], tzinfo=timezone.utc)

        embed = discord.Embed(
            title=title,
            color=discord.Color.orange(),
            timestamp=timestamp,
        )
        if link:
            embed.url = link
        if summary:
            embed.description = summary
        embed.set_footer(text=feed_name)

        return embed

    @tasks.loop(minutes=POLL_INTERVAL_MINUTES)
    async def poll_feeds(self):
        if not self.bot.is_ready() or not self.feeds:
            return

        ts = discord.utils.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] [RSS] Polling {len(self.feeds)} feed(s)...")

        loop = asyncio.get_event_loop()

        for feed_config in self.feeds:
            url = feed_config.get("url")
            channel_id = feed_config.get("channel_id")
            feed_name = feed_config.get("name", url)

            if not url or not channel_id:
                print(f"[RSS] Skipping invalid feed config: {feed_config}")
                continue

            try:
                parsed = await loop.run_in_executor(None, feedparser.parse, url)

                if parsed.bozo and not parsed.entries:
                    print(f"[RSS] Failed to parse {feed_name}: {parsed.bozo_exception}")
                    continue

                entries = parsed.entries
                is_first_run = url not in self.seen
                seen_ids = set(self.seen.get(url, []))

                current_ids = {self._entry_id(e) for e in entries}
                new_entries = [e for e in entries if self._entry_id(e) not in seen_ids]

                if is_first_run:
                    self.seen[url] = list(current_ids)
                    self._save_seen()
                    print(f"[RSS] First run for {feed_name}: marked {len(current_ids)} existing entries as seen.")
                    continue

                if not new_entries:
                    print(f"[RSS] No new entries for {feed_name}.")
                    continue

                channel = self.bot.get_channel(channel_id)
                if not channel:
                    try:
                        channel = await self.bot.fetch_channel(channel_id)
                    except Exception as e:
                        print(f"[RSS] Could not find channel {channel_id}: {e}")
                        continue

                for entry in reversed(new_entries):
                    try:
                        embed = self._make_embed(entry, feed_name)
                        await channel.send(embed=embed)
                        seen_ids.add(self._entry_id(entry))
                    except Exception as e:
                        print(f"[RSS] Error posting entry to {channel_id}: {e}")

                # Keep seen list bounded
                all_seen = list(seen_ids)
                if len(all_seen) > MAX_SEEN_PER_FEED:
                    all_seen = all_seen[-MAX_SEEN_PER_FEED:]
                self.seen[url] = all_seen
                self._save_seen()
                print(f"[RSS] Posted {len(new_entries)} new entry/entries for {feed_name}.")

            except Exception as e:
                print(f"[RSS] Unexpected error for feed {url}: {e}")

    @poll_feeds.before_loop
    async def before_poll_feeds(self):
        await self.bot.wait_until_ready()
        print("[RSS] Feed polling loop ready.")


async def setup(bot):
    await bot.add_cog(RSSFeed(bot))
