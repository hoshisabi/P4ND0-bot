# AGENTS.md — P4ND0-bot

Discord bot for the PandoDnD community: Warhorn schedule posts, adventure wishlist, characters. See `GEMINI.md` for
tooling conventions (`uv`, PowerShell, secrets in `.env`) and `TASKS.md` for the task list.

## Related repos
| Repo | Role |
|---|---|
| `hoshisabi/P4ND0-bot` (this repo) | The Discord bot |
| `hoshisabi/pandodnd-tools` (private; `~/dev/pandodnd-tools`) | Organizer CLI that creates weekly Warhorn sessions; also holds Warhorn API notes (`API_NOTES.md`) and the cross-repo plan (`TASKS.md`) |
| web app (not created yet) | Wishlist GUI and Warhorn Login, planned for Cloudflare Workers |

## Data ownership
- This repo owns the database schema in `utils/db.py`, including `adventure_wishlist` (discord_user_id, adventure,
  display_name, added_by, created_at). Other repos read it; changes to it are made here first.
- The wishlist stores Discord ids only. Linking a Discord user to a Warhorn user is deferred until the web app exists.

## Notes
- Never commit `.env`, tokens or database credentials.
