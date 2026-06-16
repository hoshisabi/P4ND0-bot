import discord

from utils.warhorn_api import format_obs_copy, parse_warhorn_dt


def format_player_lines(players: list[dict]) -> tuple[list[str], list[str]]:
    unknown = []
    lines = []
    for player in players:
        if player["character_url"]:
            lines.append(
                f"• {player['display_name']} → [{player['character_name']}]({player['character_url']})"
            )
        else:
            lines.append(f"• {player['display_name']} → Unknown")
            unknown.append(player["display_name"])
    return lines, unknown


def build_gotime_embed(
    session: dict,
    player_data: list[dict],
    *,
    preview: bool,
) -> discord.Embed:
    starts_at = parse_warhorn_dt(session["startsAt"])
    unix_ts = int(starts_at.timestamp())
    title_prefix = "Go-time preview" if preview else "Session logged"
    embed = discord.Embed(
        title=f"{title_prefix}: {session['name']}",
        color=discord.Color.blue() if preview else discord.Color.green(),
    )
    embed.add_field(name="When", value=f"<t:{unix_ts}:F>", inline=False)

    lines, unknown = format_player_lines(player_data)
    embed.add_field(name=f"Players ({len(player_data)})", value="\n".join(lines), inline=False)

    obs_copy = format_obs_copy(session)
    embed.add_field(
        name="OBS (copy/paste)",
        value=f"```\n{obs_copy}\n```",
        inline=False,
    )

    if preview:
        embed.set_footer(text="Preview only — nothing was saved and character selections were not cleared.")
    elif unknown:
        embed.set_footer(text=f"No character set: {', '.join(unknown)} — use /character play to set yours!")

    return embed
