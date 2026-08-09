import discord


def log(message: str) -> None:
    ts = discord.utils.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {message}")
