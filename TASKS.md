# P4ND0 Bot - Tasks & Roadmap

## Immediate / High Priority

### 1. Pin the Message
- [ ] Pin the Warhorn schedule message in its channel, ensuring it remains at the bottom of the history if possible (auto-repost logic).

### 2. Database Migration (MySQL)
- [ ] **Migrate JSON Persistence to MySQL:** Move `watched_schedules.json`, `last_warhorn_sessions.json`, and `characters.json` to the Sparkedhost MySQL DB (`db-ash-04`).
    - Note: Verified `DATABASE_` credentials in `.env`.
    - Note: Use `collation='utf8mb4_unicode_ci'`.
- [ ] **Guild Configuration Table:** Create a table to store server-specific settings (e.g., `#session-logs` and `#dan-text` channel IDs) instead of hardcoding them.

### 3. Session Tracking & DM Logging
- [ ] **Implement SessionTracker:** Compare current heartbeat with the last one to detect games "starting" (start time between heartbeats).
- [ ] **Game Starting Announcement:** Post a "starting" message in the channel using the Warhorn scenario image.
- [ ] **Automated Reward Generation:**
    - [ ] Create `/logsession` slash command with parameters: `adventure_name`, `gold_reward`, `streaming_hours`, `items_received`.
    - [ ] **Player Scraping:** Automatically pull list of players from the current channel (Discord member list).
    - [ ] **Formatting:** Generate a markdown reward message including tags for all detected players.
    - [ ] **Automation:** Post to `#session_logs`, get ID, and post a link in the general/text channel.
    - Note: Complex magic item descriptions can remain manual (DM can use Avrae `!item`).

## Functional Enhancements

### Character Import Feature
- [ ] **Character Import Requests:**
    - [ ] Add an "Import Needed" option to `/character add`.
    - [ ] (Optional) Monitor channel messages for D&D Beyond links to trigger "Import Needed" status.
- [ ] **DM Permission Integration:** Automatically grant "DM permissions" for a session to the Discord user matching the Warhorn GM's name (`gmSignups`).
- [ ] **Import Tracking:** Allow GMs to mark requested characters as "Imported."

### Warhorn & API Improvements
- [ ] **Scenario Image Re-evaluation:**
    - [ ] Investigate alternative GraphQL fields or separate queries for scenario images.
    - [ ] Reintegrate images into Discord embeds.
- [ ] **Waitlist Logic Refinement:** Ensure waitlist data is fully integrated into the schedule display (currently partially implemented).
- [ ] (LOW PRIORITY) **Multi-Slug Support:** Allow `$watch` (or `/watch`) to take a slug or URL to support multiple Warhorn events.

## Future / Refactoring Tasks

- [x] **Refactor `bot.py` into Modules (Cogs):**
    - [x] Split into `cogs/warhorn.py`, `cogs/characters.py`, `cogs/logging.py`, `utils/db_manager.py`, etc.
- [ ] **Better DM (Private Message) Handling:** Improve how the bot responds to commands within DMs.
- [ ] **Centralize Configuration:** Move all hardcoded strings and IDs to a dedicated `config.py` or the Database.
- [ ] **Automated Testing:** Introduce `pytest` for core logic and API interactions.
- [ ] **UI/UX Polishing:**
    - [ ] Improve startup logging (show channel names/timestamps instead of just IDs).
    - [ ] Provide more user-friendly error messages for API failures.

## Action Required (Dan)
- [x] **Recreate Python Environment with UV:** Delete `.venv` and run `uv sync` to fix broken executable paths.