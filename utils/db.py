import os
import json
import mysql.connector


def _connect():
    return mysql.connector.connect(
        host=os.getenv("DATABASE_HOST"),
        port=3306,
        user=os.getenv("DATABASE_USER"),
        password=os.getenv("DATABASE_PASS"),
        database=os.getenv("DATABASE_NAME"),
        charset="utf8mb4",
        collation="utf8mb4_unicode_ci",
    )


def init_schema():
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS characters (
                user_id BIGINT NOT NULL,
                url VARCHAR(500) NOT NULL,
                name VARCHAR(255) NOT NULL,
                avatar_url VARCHAR(1000),
                PRIMARY KEY (user_id, url)
            ) CHARACTER SET utf8mb4
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feeds (
                url VARCHAR(255) NOT NULL,
                channel_id BIGINT NOT NULL,
                name VARCHAR(255) NOT NULL,
                PRIMARY KEY (url)
            ) CHARACTER SET utf8mb4
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rss_seen (
                feed_url VARCHAR(255) NOT NULL,
                entry_id VARCHAR(255) NOT NULL,
                seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (feed_url, entry_id)
            ) CHARACTER SET utf8mb4
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watched_schedules (
                channel_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL,
                PRIMARY KEY (channel_id)
            ) CHARACTER SET utf8mb4
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS last_warhorn_sessions (
                channel_id BIGINT NOT NULL,
                sessions_data LONGTEXT NOT NULL,
                PRIMARY KEY (channel_id)
            ) CHARACTER SET utf8mb4
        """)
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def migrate_from_json():
    """One-time import of existing JSON files into the DB. Renames each file to .migrated on success."""
    _migrate_characters()
    _migrate_feeds()
    _migrate_rss_seen()
    _migrate_watched_schedules()
    _migrate_last_warhorn_sessions()


def _migrate_characters():
    if not os.path.exists("characters.json"):
        return
    try:
        with open("characters.json") as f:
            data = json.load(f)
        conn = _connect()
        try:
            cursor = conn.cursor()
            for user_id_str, chars in data.items():
                for char in chars:
                    cursor.execute(
                        "INSERT IGNORE INTO characters (user_id, url, name, avatar_url) VALUES (%s, %s, %s, %s)",
                        (int(user_id_str), char["url"], char["name"], char.get("avatar_url")),
                    )
            conn.commit()
            cursor.close()
        finally:
            conn.close()
        os.rename("characters.json", "characters.json.migrated")
        print("[DB] Migrated characters.json to database.")
    except Exception as e:
        print(f"[DB] Error migrating characters.json: {e}")


def _migrate_feeds():
    if not os.path.exists("feeds.json"):
        return
    try:
        with open("feeds.json") as f:
            feeds = json.load(f)
        conn = _connect()
        try:
            cursor = conn.cursor()
            for feed in feeds:
                cursor.execute(
                    "INSERT IGNORE INTO feeds (url, channel_id, name) VALUES (%s, %s, %s)",
                    (feed["url"][:255], feed["channel_id"], feed["name"]),
                )
            conn.commit()
            cursor.close()
        finally:
            conn.close()
        os.rename("feeds.json", "feeds.json.migrated")
        print("[DB] Migrated feeds.json to database.")
    except Exception as e:
        print(f"[DB] Error migrating feeds.json: {e}")


def _migrate_rss_seen():
    if not os.path.exists("rss_seen.json"):
        return
    try:
        with open("rss_seen.json") as f:
            seen = json.load(f)
        conn = _connect()
        try:
            cursor = conn.cursor()
            for feed_url, entry_ids in seen.items():
                for entry_id in entry_ids:
                    cursor.execute(
                        "INSERT IGNORE INTO rss_seen (feed_url, entry_id) VALUES (%s, %s)",
                        (feed_url[:255], entry_id[:255]),
                    )
            conn.commit()
            cursor.close()
        finally:
            conn.close()
        os.rename("rss_seen.json", "rss_seen.json.migrated")
        print("[DB] Migrated rss_seen.json to database.")
    except Exception as e:
        print(f"[DB] Error migrating rss_seen.json: {e}")


def _migrate_watched_schedules():
    if not os.path.exists("watched_schedules.json"):
        return
    try:
        with open("watched_schedules.json") as f:
            schedules = json.load(f)
        conn = _connect()
        try:
            cursor = conn.cursor()
            for channel_id_str, data in schedules.items():
                cursor.execute(
                    "INSERT IGNORE INTO watched_schedules (channel_id, message_id) VALUES (%s, %s)",
                    (int(channel_id_str), data["message_id"]),
                )
            conn.commit()
            cursor.close()
        finally:
            conn.close()
        os.rename("watched_schedules.json", "watched_schedules.json.migrated")
        print("[DB] Migrated watched_schedules.json to database.")
    except Exception as e:
        print(f"[DB] Error migrating watched_schedules.json: {e}")


def _migrate_last_warhorn_sessions():
    if not os.path.exists("last_warhorn_sessions.json"):
        return
    try:
        with open("last_warhorn_sessions.json") as f:
            sessions = json.load(f)
        conn = _connect()
        try:
            cursor = conn.cursor()
            for channel_id_str, sessions_data in sessions.items():
                cursor.execute(
                    "INSERT IGNORE INTO last_warhorn_sessions (channel_id, sessions_data) VALUES (%s, %s)",
                    (int(channel_id_str), json.dumps(sessions_data, default=str)),
                )
            conn.commit()
            cursor.close()
        finally:
            conn.close()
        os.rename("last_warhorn_sessions.json", "last_warhorn_sessions.json.migrated")
        print("[DB] Migrated last_warhorn_sessions.json to database.")
    except Exception as e:
        print(f"[DB] Error migrating last_warhorn_sessions.json: {e}")


# --- Characters ---

def load_all_characters() -> dict:
    conn = _connect()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT user_id, url, name, avatar_url FROM characters")
        rows = cursor.fetchall()
        cursor.close()
    finally:
        conn.close()
    result = {}
    for row in rows:
        result.setdefault(row["user_id"], []).append({
            "url": row["url"],
            "name": row["name"],
            "avatar_url": row["avatar_url"],
        })
    return result


def save_character(user_id: int, url: str, name: str, avatar_url):
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO characters (user_id, url, name, avatar_url)
               VALUES (%s, %s, %s, %s)
               ON DUPLICATE KEY UPDATE name=VALUES(name), avatar_url=VALUES(avatar_url)""",
            (user_id, url, name, avatar_url),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()


# --- Feeds ---

def load_all_feeds() -> list:
    conn = _connect()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT url, channel_id, name FROM feeds")
        rows = cursor.fetchall()
        cursor.close()
    finally:
        conn.close()
    return [{"url": r["url"], "channel_id": r["channel_id"], "name": r["name"]} for r in rows]


# --- RSS Seen ---

def get_seen_ids(feed_url: str) -> set:
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT entry_id FROM rss_seen WHERE feed_url=%s", (feed_url[:255],))
        rows = cursor.fetchall()
        cursor.close()
    finally:
        conn.close()
    return {row[0] for row in rows}


def add_seen_ids(feed_url: str, entry_ids):
    if not entry_ids:
        return
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.executemany(
            "INSERT IGNORE INTO rss_seen (feed_url, entry_id) VALUES (%s, %s)",
            [(feed_url[:255], eid[:255]) for eid in entry_ids],
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def prune_seen(feed_url: str, max_count: int):
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM rss_seen WHERE feed_url=%s", (feed_url[:255],))
        count = cursor.fetchone()[0]
        if count > max_count:
            cursor.execute(
                "DELETE FROM rss_seen WHERE feed_url=%s ORDER BY seen_at ASC LIMIT %s",
                (feed_url[:255], count - max_count),
            )
            conn.commit()
        cursor.close()
    finally:
        conn.close()


# --- Watched Schedules ---

def load_all_watched_schedules() -> dict:
    conn = _connect()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT channel_id, message_id FROM watched_schedules")
        rows = cursor.fetchall()
        cursor.close()
    finally:
        conn.close()
    return {r["channel_id"]: {"channel_id": r["channel_id"], "message_id": r["message_id"]} for r in rows}


def save_watched_schedule(channel_id: int, message_id: int):
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO watched_schedules (channel_id, message_id) VALUES (%s, %s)
               ON DUPLICATE KEY UPDATE message_id=VALUES(message_id)""",
            (channel_id, message_id),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def remove_watched_schedule(channel_id: int):
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM watched_schedules WHERE channel_id=%s", (channel_id,))
        conn.commit()
        cursor.close()
    finally:
        conn.close()


# --- Last Warhorn Sessions ---

def load_all_last_sessions() -> dict:
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT channel_id, sessions_data FROM last_warhorn_sessions")
        rows = cursor.fetchall()
        cursor.close()
    finally:
        conn.close()
    return {row[0]: json.loads(row[1]) for row in rows}


def save_last_sessions(channel_id: int, sessions_data: list):
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO last_warhorn_sessions (channel_id, sessions_data) VALUES (%s, %s)
               ON DUPLICATE KEY UPDATE sessions_data=VALUES(sessions_data)""",
            (channel_id, json.dumps(sessions_data, default=str)),
        )
        conn.commit()
        cursor.close()
    finally:
        conn.close()


def remove_last_sessions(channel_id: int):
    conn = _connect()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM last_warhorn_sessions WHERE channel_id=%s", (channel_id,))
        conn.commit()
        cursor.close()
    finally:
        conn.close()
