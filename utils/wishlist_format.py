from utils.warhorn_api import parse_warhorn_dt

RECENT_WARHORN_COUNT = 8


def build_wishlist_catalog(entries: list[dict]) -> list[dict]:
    """Distinct adventures requested on the wishlist, sorted alphabetically."""
    by_adventure: dict[str, list[str]] = {}
    for entry in entries:
        by_adventure.setdefault(entry["adventure"], []).append(entry["display_name"])

    catalog = []
    for adventure in sorted(by_adventure, key=str.casefold):
        requesters = sorted({name for name in by_adventure[adventure] if name}, key=str.casefold)
        catalog.append({
            "adventure": adventure,
            "requesters": requesters,
            "source": "wishlist",
            "played_at": None,
        })
    return catalog


def build_browse_catalog(
    wishlist_entries: list[dict],
    recent_sessions: list[dict],
    *,
    recent_limit: int = RECENT_WARHORN_COUNT,
) -> list[dict]:
    """Wishlist requests first, then recent Warhorn adventures not already listed."""
    catalog = build_wishlist_catalog(wishlist_entries)
    listed_names = {item["adventure"].casefold() for item in catalog}

    for session in recent_sessions[:recent_limit]:
        adventure = session["name"]
        if adventure.casefold() in listed_names:
            continue
        catalog.append({
            "adventure": adventure,
            "requesters": [],
            "source": "warhorn",
            "played_at": parse_warhorn_dt(session["startsAt"]),
        })
        listed_names.add(adventure.casefold())

    return catalog


def format_wishlist_catalog(catalog: list[dict]) -> str:
    if not catalog:
        return "*No adventures on the wishlist yet.*"

    lines = []
    for index, item in enumerate(catalog, start=1):
        names = ", ".join(item["requesters"]) if item["requesters"] else "Unknown"
        lines.append(f"**{index}.** {item['adventure']} — {names}")
    return "\n".join(lines)


def format_browse_catalog(catalog: list[dict], *, include_requesters: bool = False) -> str:
    if not catalog:
        return "*Nothing to browse yet.*"

    wishlist_lines = []
    warhorn_lines = []
    for index, item in enumerate(catalog, start=1):
        if item["source"] == "wishlist":
            if include_requesters:
                names = ", ".join(item["requesters"]) if item["requesters"] else "Unknown"
                wishlist_lines.append(f"**{index}.** {item['adventure']} — {names}")
            else:
                wishlist_lines.append(f"**{index}.** {item['adventure']}")
        else:
            played_at = int(item["played_at"].timestamp())
            warhorn_lines.append(f"**{index}.** {item['adventure']} — <t:{played_at}:D>")

    sections: list[str] = []
    if wishlist_lines:
        sections.append("**Requested by players**\n" + "\n".join(wishlist_lines))
    if warhorn_lines:
        sections.append("**Recent sessions**\n" + "\n".join(warhorn_lines))
    return "\n\n".join(sections)


def resolve_wishlist_number(catalog: list[dict], number: int) -> str | None:
    if number < 1 or number > len(catalog):
        return None
    return catalog[number - 1]["adventure"]


def match_wishlist_adventure(catalog: list[dict], name: str) -> str | None:
    """Match a session or typed title to a single wishlist adventure.

    Prefers an exact name, then case-insensitive equality, then a unique
    containment match so Warhorn titles like ``PS-DC-PUB-10 Absent without Leave``
    can resolve to ``Absent without Leave``. Returns None if missing or ambiguous.
    """
    name = (name or "").strip()
    if not name or not catalog:
        return None

    adventures = [item["adventure"] for item in catalog]
    if name in adventures:
        return name

    folded = name.casefold()
    casefold_matches = [adventure for adventure in adventures if adventure.casefold() == folded]
    if len(casefold_matches) == 1:
        return casefold_matches[0]
    if len(casefold_matches) > 1:
        return None

    contained = [
        adventure
        for adventure in adventures
        if folded in adventure.casefold() or adventure.casefold() in folded
    ]
    if len(contained) == 1:
        return contained[0]
    return None


def _display_names(entries: list[dict]) -> list[str]:
    names = []
    seen: set[str] = set()
    for entry in entries:
        name = entry.get("display_name") or f"user {entry.get('discord_user_id')}"
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names


def plan_wishlist_trim(
    entries: list[dict],
    *,
    remove_ids: list[int] | None = None,
    keep_ids: list[int] | None = None,
) -> tuple[list[int] | None, list[int], bool]:
    """Decide which wishlist user ids to delete.

    Returns ``(delete_ids, not_listed_ids, abort)``. ``delete_ids`` of ``None``
    means everyone; an empty list means delete nobody. ``abort`` is True when
    keep-mode would otherwise wipe the list because none of the keep players
    are currently listed.
    """
    listed_ids = [entry["discord_user_id"] for entry in entries]
    listed_set = set(listed_ids)

    if keep_ids is not None:
        keep_set = set(keep_ids)
        not_listed = [user_id for user_id in keep_ids if user_id not in listed_set]
        if not keep_set.intersection(listed_set):
            return [], not_listed, True
        to_remove = [user_id for user_id in listed_ids if user_id not in keep_set]
        return to_remove, not_listed, False

    if remove_ids is not None:
        not_listed = [user_id for user_id in remove_ids if user_id not in listed_set]
        to_remove = [user_id for user_id in remove_ids if user_id in listed_set]
        return to_remove, not_listed, False

    return None, [], False


def format_trim_result(
    adventure: str,
    removed: list[dict],
    *,
    targeted: bool = False,
    kept: bool = False,
    abort: bool = False,
    remaining: list[dict] | None = None,
    not_listed_names: list[str] | None = None,
) -> str:
    removed_names = _display_names(removed)
    remaining_names = _display_names(remaining or [])
    not_listed = [name for name in (not_listed_names or []) if name]

    if kept:
        if abort:
            if not_listed:
                verb = "has" if len(not_listed) == 1 else "have"
                return (
                    f"{', '.join(not_listed)} {verb} not wishlisted **{adventure}**, "
                    "so nobody was removed."
                )
            return f"Nobody has wishlisted **{adventure}**."
        if removed_names:
            parts = [
                f"Trimmed **{adventure}** from the wishlist ({', '.join(removed_names)})."
            ]
            if remaining_names:
                parts.append(f"Left on the list: {', '.join(remaining_names)}.")
            if not_listed:
                verb = "was" if len(not_listed) == 1 else "were"
                parts.append(f"{', '.join(not_listed)} {verb} not listed.")
            return " ".join(parts)
        if remaining_names:
            parts = [
                f"Nobody else was listed for **{adventure}**. "
                f"Left on the list: {', '.join(remaining_names)}."
            ]
            if not_listed:
                verb = "was" if len(not_listed) == 1 else "were"
                parts.append(f"{', '.join(not_listed)} {verb} not listed.")
            return " ".join(parts)
        return f"Nobody has wishlisted **{adventure}**."

    if not targeted:
        if not removed_names:
            return f"Nobody has wishlisted **{adventure}**."
        return f"Trimmed **{adventure}** from the wishlist ({', '.join(removed_names)})."

    parts: list[str] = []
    if removed_names:
        parts.append(
            f"Removed {', '.join(removed_names)} from the wishlist for **{adventure}**."
        )
    elif not_listed:
        verb = "has" if len(not_listed) == 1 else "have"
        parts.append(f"{', '.join(not_listed)} {verb} not wishlisted **{adventure}**.")
    else:
        parts.append(f"Nobody has wishlisted **{adventure}**.")

    if removed_names and remaining_names:
        parts.append(f"Still listed: {', '.join(remaining_names)}.")
    if removed_names and not_listed:
        verb = "was" if len(not_listed) == 1 else "were"
        parts.append(f"{', '.join(not_listed)} {verb} not listed.")
    return " ".join(parts)
