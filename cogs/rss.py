import asyncio
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks
import feedparser

from utils import db
from utils.log import log
from utils.rss_format import build_entry_content

POLL_INTERVAL_MINUTES = 60
MAX_SEEN_PER_FEED = 500

FEED_COLORS = {
    "dmsguild": discord.Color.from_rgb(200, 16, 46),
    "d&d beyond": discord.Color.from_rgb(90, 45, 130),
    "warhorn": discord.Color.from_rgb(35, 110, 190),
    "legends of greyhawk": discord.Color.from_rgb(34, 120, 70),
}


class RSSFeed(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.poll_feeds.start()

    def cog_unload(self):
        self.poll_feeds.cancel()

    def _entry_id(self, entry) -> str:
        return db.stable_entry_id(entry)

    def _feed_color(self, feed_name: str) -> discord.Color:
        lowered = feed_name.casefold()
        for key, color in FEED_COLORS.items():
            if key in lowered:
                return color
        return discord.Color.orange()

    def _make_embed(self, entry, feed_name: str) -> discord.Embed:
        content = build_entry_content(entry)
        link = entry.get("link", "")

        published = entry.get("published_parsed") or entry.get("updated_parsed")
        timestamp = None
        if published:
            timestamp = datetime(*published[:6], tzinfo=timezone.utc)

        embed = discord.Embed(
            title=content["title"],
            description=content["description"],
            color=self._feed_color(feed_name),
            timestamp=timestamp,
        )
        if link:
            embed.url = link
        if content["author"]:
            embed.set_author(name=content["author"])
        if content["image_url"]:
            embed.set_image(url=content["image_url"])
        if content["price"]:
            embed.add_field(name="Price", value=content["price"], inline=True)
        embed.set_footer(text=feed_name)
        return embed, content["image_url"]

    async def _send_entry(self, channel, entry, feed_name: str):
        embed, image_url = self._make_embed(entry, feed_name)
        try:
            await channel.send(embed=embed)
            return
        except Exception as e:
            if not image_url:
                raise
            log(f"[RSS] Embed send failed for {feed_name} (retrying without image): {e}")
            embed.set_image(url=None)
            await channel.send(embed=embed)

    @tasks.loop(minutes=POLL_INTERVAL_MINUTES)
    async def poll_feeds(self):
        if not self.bot.is_ready():
            return

        feeds = db.load_all_feeds()
        if not feeds:
            return

        log(f"[RSS] Polling {len(feeds)} feed(s)...")

        loop = asyncio.get_event_loop()

        for feed_config in feeds:
            url = feed_config.get("url")
            channel_id = feed_config.get("channel_id")
            feed_name = feed_config.get("name", url)

            if not url or not channel_id:
                log(f"[RSS] Skipping invalid feed config: {feed_config}")
                continue

            try:
                parsed = await loop.run_in_executor(None, feedparser.parse, url)

                if parsed.bozo and not parsed.entries:
                    log(f"[RSS] Failed to parse {feed_name}: {parsed.bozo_exception}")
                    continue

                entries = parsed.entries
                seen_ids = db.get_seen_ids(url)
                is_first_run = len(seen_ids) == 0

                current_ids = {self._entry_id(e) for e in entries if self._entry_id(e)}
                new_entries = [e for e in entries if self._entry_id(e) and self._entry_id(e) not in seen_ids]

                if is_first_run:
                    db.add_seen_ids(url, current_ids)
                    log(f"[RSS] First run for {feed_name}: marked {len(current_ids)} existing entries as seen.")
                    continue

                if not new_entries:
                    newest = entries[0] if entries else None
                    if newest:
                        newest_id = self._entry_id(newest)
                        newest_title = (newest.get("title") or "")[:60]
                        log(
                            f"[RSS] No new entries for {feed_name} ({len(seen_ids)} seen, "
                            f"{len(entries)} in feed). Newest: {newest_title!r} "
                            f"(seen={newest_id in seen_ids})"
                        )
                    else:
                        log(f"[RSS] No new entries for {feed_name} ({len(seen_ids)} seen).")
                    continue

                channel = self.bot.get_channel(channel_id)
                if not channel:
                    try:
                        channel = await self.bot.fetch_channel(channel_id)
                    except Exception as e:
                        log(f"[RSS] Could not find channel {channel_id}: {e}")
                        continue

                posted_ids = []
                for entry in reversed(new_entries):
                    entry_id = self._entry_id(entry)
                    try:
                        await self._send_entry(channel, entry, feed_name)
                        seen_ids.add(entry_id)
                        posted_ids.append(entry_id)
                        try:
                            db.add_seen_id(url, entry_id)
                        except Exception as e:
                            log(f"[RSS] Failed to save seen entry for {feed_name} ({entry_id[:80]}): {e}")
                    except Exception as e:
                        log(f"[RSS] Error posting entry to {channel_id}: {e}")

                if posted_ids:
                    try:
                        db.prune_seen(url, MAX_SEEN_PER_FEED, keep_ids=current_ids)
                    except Exception as e:
                        log(f"[RSS] Failed to prune seen entries for {feed_name}: {e}")
                log(
                    f"[RSS] Posted {len(posted_ids)}/{len(new_entries)} new entry/entries "
                    f"for {feed_name} ({len(seen_ids)} seen)."
                )

            except Exception as e:
                log(f"[RSS] Unexpected error for feed {url}: {e}")

    @poll_feeds.before_loop
    async def before_poll_feeds(self):
        await self.bot.wait_until_ready()
        log("[RSS] Feed polling loop ready.")


async def setup(bot):
    await bot.add_cog(RSSFeed(bot))
