# P4ND0 Bot - Remaining Tasks & Future Enhinements

## Immediate/Verification Tasks (Post-Fixes)
  - [ ] **Verify Warhorn API Fetch:** Confirm that `warhorn_api.py` (with `coverImageUrl` removed from the query) successfully fetches event sessions and waitlist data without any `KeyError` or other API-related errors.
  - [ ] **Verify Bot Schedule Display:** Confirm that `bot.py` (with `coverImageUrl` display logic removed) correctly sends and updates the Warhorn schedule messages in Discord, without any errors related to missing image URLs.
  - [ ] **Waitlist Logic** We should be able to gather the waitlist with an additional command within the warhorn_api and provide that data back to the bot.py
  - [ ] **Pin the Message** We should pin the message that is made, even if we are keeping it at the bottom

## Functional Enhancements (To be addressed)
  - [ ] **Warhorn Scenario Image Re-evaluation:**
    * Investigate alternative ways to retrieve scenario images from Warhorn. This might involve:
        * Re-examining the GraphQL schema for other image-related fields on `Scenario` or `EventSession`.
        * Potentially making a separate GraphQL query specifically for `Scenario` details if it reveals a working image field.
        * Considering using Warhorn's public website scraping if API access is not feasible (last resort, as it's less reliable).
    * Reintegrate scenario images into the Discord embed if a reliable source is found.

## Future/Refactoring Tasks
- [ ] **Slash Commands** Use proper slash commands instead of looking for $watch and
                         similar dollar sign text to signify bot commands.
- [ ] **DM Handling**    Bot handles DMs just fine, but some commands such as watch do
                         weird things when you run it from within a DM. We should better handle that, 
                         as well as better inform the user that they can send private messages to the bot.
- [ ] **Refactor `bot.py` into Modules:**
    * Break down the large `bot.py` file into smaller, specialized modules (e.g., `cogs/warhorn.py`, `cogs/characters.py`, `utils/persistence.py`, `utils/embed_generator.py`).
    * Organize commands and tasks into Discord.py `cogs` for better organization and management.
- [ ] **Centralize Configuration:**
    * Improve the handling of configurable values (e.g., `pandodnd` slug, API endpoints) to avoid hardcoding and make them easily changeable. Consider a dedicated `config.py` file or a more robust environment variable setup.
- [ ] **Enhance Error Handling & Logging:**
    * Implement more detailed and consistent error logging for debugging (e.g., using Python's `logging` module).
    * Provide more user-friendly error messages in Discord for common issues (e.g., API failures, invalid command arguments).
- [ ] **Robust Persistence (Optional, for Scale):**
    * While JSON files work for now, consider migrating persistence for `watched_schedules`, `last_warhorn_sessions_data`, and `characters` to a simple database (e.g., MySql -- which is available through Sparkedhost server) for better performance and data integrity as the bot scales or data complexity increases.
- [ ] **Improved Startup/Shutdown Resilience:**
    * Further enhance the bot's ability to recover gracefully on startup (e.g., better handling of deleted messages/channels when loading `watched_schedules`).
    * Ensure all data is saved reliably upon bot shutdown.
- [ ] This message on startup should probably print better info, not just the numeric info.  (Channel name at least, perhaps also a date time stamp?)
    >  Successfully fetched watched message 1396746335851515996 in channel 1016232161264807987.
    > Successfully fetched watched message 1396746546216828991 in channel 688166777347506272.
- [ ] We could watch other warhorn sites with this if we pass in the slug, perhaps $watch (slug) could be used.  Should also
      be able to derive the slug from the URL, if the user passes in the URL