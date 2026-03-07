## Gemini Added Memories

- This project is a Python-based Discord bot.
- Its purpose is to connect to a Discord server, with a new feature to integrate with Warhorn for D&D sign-ups.
- Key technologies include Python, Discord.py, and the Warhorn GraphQL API.
- Warhorn API authentication uses `WARHORN_CLIENT_ID`, `WARHORN_CLIENT_SECRET`, and `WARHORN_APPLICATION_TOKEN` from
  environment variables.
- The project uses `uv` for virtualization and dependency management.
- The user's operating system is Windows (win32), and the preferred shell is PowerShell. Shell commands should use
  PowerShell syntax (e.g., `Remove-Item`, `Get-ChildItem`, `$env:VAR`, etc.). Validate any Python environments using
  `uv run` or ensuring `.venv` is correct.

## UV Cheatsheet & Documentation

Since the project relies on Astral's `uv` instead of traditional `pip` or `pipenv` tools:

- **Run a script**: `uv run bot.py` (*No need to manually activate the virtual environment!*)
- **Add a dependency**: `uv add <package-name>` (*Updates pyproject.toml and installs*)
- **Remove a package**: `uv remove <package-name>`
- **Sync dependencies**: `uv sync` (*Installs everything listed in `pyproject.toml`*)
- **Docs**: [https://docs.astral.sh/uv/](https://docs.astral.sh/uv/)

## Project Conventions

- **Secrets Management**: All secrets or configuration details (Tokens, MySQL credentials, Warhorn tokens) are kept
  exclusively in the `.env` file and loaded using `python-dotenv`.
- **Modularity**: Currently migrating from a single `bot.py` monolithic script to a modular `cogs/` directory
  architecture (Discord.py standard practice).
