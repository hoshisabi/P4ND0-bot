# P4ND0 Bot - Remaining Tasks & Future Enhinements

## Immediate/Verification Tasks (Post-Fixes)
  - [x] **Verify Warhorn API Fetch:** Confirm that `warhorn_api.py` (with `coverImageUrl` removed from the query) successfully fetches event sessions and waitlist data without any `KeyError` or other API-related errors.
  - [x] **Verify Bot Schedule Display:** Confirm that `bot.py` (with `coverImageUrl` display logic removed) correctly sends and updates the Warhorn schedule messages in Discord, without any errors related to missing image URLs.
  - [x] **Waitlist Logic** We should be able to gather the waitlist with an additional command within the warhorn_api and provide that data back to the bot.py
  - [ ] **Pin the Message** We should pin the message that is made, even if we are keeping it at the bottom

## Functional Enhancements (To be addressed)
  - [ ] **Warhorn Scenario Image Re-evaluation:**
    * Investigate alternative ways to retrieve scenario images from Warhorn. This might involve:
        * Re-examining the GraphQL schema for other image-related fields on `Scenario` or `EventSession`.
        * Potentially making a separate GraphQL query specifically for `Scenario` details if it reveals a working image field.
        * Considering using Warhorn's public website scraping if API access is not feasible (last resort, as it's less reliable).
    * Reintegrate scenario images into the Discord embed if a reliable source is found.
  - [ ] **Auto-Scan D&D Beyond Links:**
    * Plan and implement a feature to monitor specific channels (like `#dan-text`) for shared D&D Beyond character links and automatically add them to the character list.
## Future/Refactoring Tasks
- [x] **Slash Commands** Use proper slash commands instead of looking for $watch and
                         similar dollar sign text to signify bot commands.
- [ ] **DM Handling**    Bot handles DMs just fine, but some commands such as watch do
                         weird things when you run it from within a DM. We should better handle that, 
                         as well as better inform the user that they can send private messages to the bot.
- [ ] **Refactor `bot.py` into Modules (Move Commands to Cogs):**
    * Break down the large `bot.py` file into smaller, specialized modules (e.g., `cogs/warhorn.py`, `cogs/characters.py`, `utils/persistence.py`, `utils/embed_generator.py`).
    * Organize commands and tasks into Discord.py `cogs` for better organization and management.
- [x] **Abstract the Repetitive JSON I/O Logic:**
    * Create a unified helper function for loading/saving JSON state files to cut down boilerplate.
- [ ] **Decouple API Fetching from Embed Formatting:**
    * Separate the Warhorn API data fetching from the complex embed generation logic in `get_warhorn_embed_and_data`.
- [ ] **Encapsulate Global State:**
    * Group global variables like `watched_schedules` or `characters` into a class or DataManager to avoid state pollution.
- [ ] **Centralize Configuration:**
    * Improve the handling of configurable values (e.g., `pandodnd` slug, API endpoints) to avoid hardcoding and make them easily changeable. Consider a dedicated `config.py` file or a more robust environment variable setup.
- [ ] **Enhance Error Handling & Logging:**
    * Implement more detailed and consistent error logging for debugging (e.g., using Python's `logging` module).
    * Provide more user-friendly error messages in Discord for common issues (e.g., API failures, invalid command arguments).
- [ ] **Robust Persistence (Database Implementation):**
    * The `utils/persistence.py` JSON files (`watched_schedules.json`, `last_warhorn_sessions.json`, and `characters.json`) work for now, but should be migrated to the Sparkedhost MySQL DB for reliability as the bot scales.
    * **Note:** We have successfully verified the `DATABASE_` credentials in `.env` connect to the `db-ash-04` host.
    * Ensure the connector passes `collation='utf8mb4_unicode_ci'` to prevent MariaDB collation errors when we implement this logic.
- [ ] **Improved Startup/Shutdown Resilience:**
    * Further enhance the bot's ability to recover gracefully on startup (e.g., better handling of deleted messages/channels when loading `watched_schedules`).
    * Ensure all data is saved reliably upon bot shutdown.
- [ ] This message on startup should probably print better info, not just the numeric info.  (Channel name at least, perhaps also a date time stamp?)
    > Successfully fetched watched message 1396746335851515996 in channel 1016232161264807987.  
    > Successfully fetched watched message 1396746546216828991 in channel 688166777347506272.
- [ ] We could watch other warhorn sites with this if we pass in the slug, perhaps $watch (slug) could be used.  Should also
      be able to derive the slug from the URL, if the user passes in the URL
- [ ] **Automate Session Log Generation:** Implement a new parameterized slash command (e.g., `/logsession`) within the Discord bot to create and post session logs.
    * **Parameters:** `adventure_name`, `gold_reward`, `streaming_hours`, `items_received`.
    * **Message Format:**
        * `[Adventure Name], [Gold Reward]gp each, [Streaming Hours] hours streaming, level if you want it, 10 downtime days, [Items Received]`
    * **Actions:**
        1.  Send the formatted message to the `#session_logs` channel.
        2.  Retrieve the Message ID of the sent log.
        3.  Send a link to that message in the `#dan_text` channel.
- [ ] **Add Automated Testing:** 
    * Introduce a testing framework (like `pytest`) to ensure `bot.py` and its new cogs can be reliably updated in the future without manual ad-hoc testing.
- [x] **Action Required (Dan): Recreate Python Environment with UV**
    * The `.venv` currently has broken executable paths. You need to recreate the environment using `uv`.
    * Please delete `.venv` and run `uv sync` in your PowerShell terminal to reinstall dependencies cleanly.      