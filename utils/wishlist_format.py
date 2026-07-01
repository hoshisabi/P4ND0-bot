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
