"""One-off RSS diagnostic — compare feed entries to seen-id logic."""
import json
from datetime import datetime, timezone
from pathlib import Path

import feedparser

from utils import db
from utils.rss_format import build_entry_content

FEEDS_PATH = Path(__file__).resolve().parent.parent / "feeds.json"
FEEDS = [(f["name"], f["url"]) for f in json.loads(FEEDS_PATH.read_text())]

for name, url in FEEDS:
    feed_url = db.normalize_feed_url(url)
    parsed = feedparser.parse(url)
    print(f"\n=== {name} ({len(parsed.entries)} entries, bozo={parsed.bozo}) ===")
    for i, e in enumerate(parsed.entries[:8]):
        content = build_entry_content(e)
        eid = db.stable_entry_id(e)
        pub = e.get("published_parsed") or e.get("updated_parsed")
        pub_s = datetime(*pub[:6], tzinfo=timezone.utc).strftime("%Y-%m-%d") if pub else "n/a"
        print(f"[{i}] {content['title'][:60]} ({pub_s})")
        print(f"  id: {eid}")
        print(f"  image: {content['image_url']}")
        link_id = db.normalize_entry_id(e.get("link") or "")
        if e.get("id") and e.get("link") and eid != link_id:
            print(f"  link-id differs: {link_id}")
        if content["description"]:
            print(f"  desc: {content['description'][:100]}...")
