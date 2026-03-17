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

## Adventure Wishlist & Encore

### Wishlist Feature
Allow players to request adventures they'd like to play in a future session.

- [ ] **Catalog Lookup:** Locate and integrate the `al_adventure_catalog` sibling project (`../al_adventure_catalog` or similar — confirm exact path/structure).
- [ ] **Adventure Linking:** Link each wishlist entry to the corresponding `.json` in the catalog.
- [ ] **2-Hour Filter:** For now, only surface/permit 2-hour adventures.
- [ ] **Ownership Flag:** Add a config option to indicate whether the user owns a given adventure.

**Design questions:**
- Exact path and structure of `al_adventure_catalog` — needs exploration before implementation.
- How to reliably determine ownership (manual flag in catalog JSON? separate config file?).
- UI: slash command with autocomplete from catalog, or interactive prompt?

---

### Encore Feature
Allow players to request an adventure they missed (or know they'll miss) to be queued for the next time it runs.

Distinct from wishlist: *wishlist* = "I want to play this someday"; *encore* = "I want to play this specific adventure the next time it's scheduled."

- [ ] **Slash command interaction:** Ask the user whether they mean (a) "I'm going to miss an upcoming session" or (b) "I already missed a session" — resolve the timing ambiguity via prompt.
- [ ] **Session history:** Store the last 2 past adventures (in addition to future ones) so players can reference a recent missed session (~2-week lookback window).
- [ ] **Encore queue:** Surface encore requesters when the adventure is next scheduled.
- [ ] **Audit session pruning:** Identify anywhere old sessions are currently dropped and adjust for the 2-session history requirement.

**Design questions:**
- Shared data model with wishlist (flag on same record) or a separate list?
- Should encore requests get higher scheduling priority than wishlist entries?
- Does the system need to distinguish preemptive vs. retrospective, or is "next occurrence" sufficient?

---

## Future / Refactoring Tasks

- [x] **Refactor `bot.py` into Modules (Cogs):**
    - [x] Split into `cogs/warhorn.py`, `cogs/characters.py`, `cogs/logging.py`, `utils/db_manager.py`, etc.
- [~] **Better DM (Private Message) Handling:** Fix applied for `/watch` in DMs (`AttributeError` on `channel.name`). Awaiting confirmation that schedule updates are being received in DMs.
- [ ] **Centralize Configuration:** Move all hardcoded strings and IDs to a dedicated `config.py` or the Database.
- [ ] **Automated Testing:** Expand `pytest` coverage for core logic and API interactions (Started: `tests/test_persistence.py`).
- [ ] **UI/UX Polishing:**
    - [x] Improve startup logging (show channel names/timestamps instead of just IDs).
    - [ ] Provide more user-friendly error messages for API failures.

## Action Required (Dan)
- [x] **Recreate Python Environment with UV:** Delete `.venv` and run `uv sync` to fix broken executable paths.
- [ ] **Verify DM Watch Updates:** Run `/watch` in a DM with the bot, send a message in that DM to push the schedule off the bottom, wait up to 10 minutes, and confirm the bot reposts the schedule. Report back pass/fail.