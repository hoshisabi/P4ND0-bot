import json
import re
from pathlib import Path

import requests

CATALOG_URL = "https://hoshisabi.com/al_adventure_catalog/assets/data/catalog.json"
PREPPED_PATH = Path(__file__).resolve().parent.parent / "prepped_adventures.json"
SUGGESTED_HOURS = "2"
AUTOCOMPLETE_LIMIT = 25
CHOICE_MAX_LEN = 100

_ARTICLES = {"a", "an", "the"}
_LEADING_ZEROS = re.compile(r"(?<![0-9])0+(?=[0-9])")
_COPY_SUFFIX = re.compile(r"\s*\(\d+[a-z]?\)$", re.IGNORECASE)
_catalog: list[dict] = []


def fetch_catalog(url: str = CATALOG_URL, timeout: float = 30) -> list[dict]:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return parse_catalog(response.json())


def parse_catalog(data: dict) -> list[dict]:
    """Convert the minified al_adventure_catalog JSON into bot-friendly entries.

    Each adventure is named ``CODE Title`` to match how Warhorn sessions are
    titled, e.g. ``PS-DC-PUB-15 Spider Hunt``.
    """
    entries = []
    seen: set[str] = set()
    for item in data.get("adventures", []):
        title = (item.get("n") or "").strip()
        code = (item.get("c") or "").strip()
        if not title:
            continue
        name = f"{code} {title}" if code else title
        if name.casefold() in seen:
            continue
        seen.add(name.casefold())
        entries.append({
            "name": name,
            "product_id": str(item.get("i") or ""),
            "code": code,
            "title": title,
            "hours": (item.get("h") or "").strip(),
            "tier": item.get("t"),
            "date": item.get("d") or "",
            "keys": {
                "name": normalize(name),
                "code": normalize(code),
                "title": normalize(title),
                "search": normalize(name, strip_zeros=False),
            },
        })
    return entries


def load_prepped_names(path: Path = PREPPED_PATH) -> list[str]:
    """Adventures Dan has already prepped for Foundry, from the checked-in JSON."""
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [item["name"] for item in data.get("adventures", [])]


def mark_prepped(catalog: list[dict], prepped_names: list[str]) -> int:
    """Flag catalog entries that have been prepped. Returns how many matched."""
    keys = {normalize(name) for name in prepped_names}
    for entry in catalog:
        entry["prepped"] = entry["keys"]["name"] in keys
    return sum(entry["prepped"] for entry in catalog)


def match_prepped_file(stem: str, catalog: list[dict]) -> str | None:
    """Catalog name for a Foundry Transfer zip like ``DDAL4-02 The Beast``.

    Tries the whole name, then the leading code and the remaining title on
    their own. Returns None when nothing matches or the parts disagree.
    """
    stem = _COPY_SUFFIX.sub("", stem.strip())
    whole = canonical_catalog_name(stem, catalog)
    if whole:
        return whole

    code, _, title = stem.partition(" ")
    by_code = canonical_catalog_name(code, catalog) if title else None
    by_title = canonical_catalog_name(title, catalog) if title else None
    if by_code and by_title and by_code != by_title:
        return None
    return by_code or by_title


def catalog_names_for_product(product_id: str, catalog: list[dict]) -> list[str]:
    """Catalog names for a DMsGuild product, including each part of a bundle.

    The catalog lists bundle components as ``<id>-01``, ``<id>-02``, ...
    """
    return [
        entry["name"]
        for entry in catalog
        if entry["product_id"] == product_id or entry["product_id"].startswith(f"{product_id}-")
    ]


def get_catalog() -> list[dict]:
    return _catalog


def set_catalog(entries: list[dict]) -> None:
    global _catalog
    _catalog = entries


def normalize(text: str, *, strip_zeros: bool = True) -> str:
    """Comparison key that ignores case, punctuation, articles, and leading zeros.

    ``FR-DC-LOOSE-001`` and ``FR-DC-LOOSE-01`` compare equal (so do ``DDAL4``
    and ``DDAL04``), as do
    ``dish best served cold`` and ``A Dish Best Served Cold``. Autocomplete
    keeps the zeros so a half-typed ``DDAL07-0`` still prefixes ``DDAL07-01``.
    """
    text = re.sub(r"['’]", "", (text or "").casefold())
    tokens = re.split(r"[^0-9a-z]+", text)
    normalized = []
    for token in tokens:
        if not token or token in _ARTICLES:
            continue
        if strip_zeros:
            token = _LEADING_ZEROS.sub("", token)
        normalized.append(token)
    return " ".join(normalized)


def _unique(matches: list[str]) -> str | None:
    distinct = {match.casefold(): match for match in matches}
    return next(iter(distinct.values())) if len(distinct) == 1 else None


def canonical_catalog_name(text: str, catalog: list[dict]) -> str | None:
    """Catalog name for typed text, matched by full name, code, or title.

    Returns None when nothing matches or the match is ambiguous.
    """
    key = normalize(text)
    if not key:
        return None
    for field in ("name", "code", "title"):
        match = _unique([entry["name"] for entry in catalog if entry["keys"][field] == key])
        if match:
            return match
    return None


def resolve_adventure_name(text: str, known_names: list[str], catalog: list[dict]) -> str:
    """Tidy a typed adventure into the name it should be stored under.

    An existing wishlist or recent-session name wins when it is the same
    adventure spelled differently (e.g. Warhorn's ``FR-DC-LOOSE-001`` vs the
    catalog's ``FR-DC-LOOSE-01``), so requests don't split across two lines.
    Otherwise the catalog's ``CODE Title`` form, otherwise the text as typed.
    """
    text = (text or "").strip()
    canonical = canonical_catalog_name(text, catalog)
    key = normalize(canonical or text)
    known = _unique([name for name in known_names if key and normalize(name) == key])
    return known or canonical or text


def find_matching_name(text: str, names: list[str], catalog: list[dict]) -> str | None:
    """Find which of ``names`` (e.g. one player's wishlist) the typed text means."""
    text = (text or "").strip()
    if text in names:
        return text

    def keys_for(value: str) -> set[str]:
        keys = {normalize(value)}
        canonical = canonical_catalog_name(value, catalog)
        if canonical:
            keys.add(normalize(canonical))
        keys.discard("")
        return keys

    wanted = keys_for(text)
    return _unique([name for name in names if keys_for(name) & wanted])


def _prefix_match(query_tokens: list[str], key: str) -> bool:
    tokens = key.split()
    return all(any(token.startswith(query) for token in tokens) for query in query_tokens)


def _query_matches(query: tuple[list[str], list[str]], raw_key: str, key: str) -> bool:
    raw_tokens, tokens = query
    return _prefix_match(raw_tokens, raw_key) or _prefix_match(tokens, key)


def _choice_label(name: str, suffix: str) -> str:
    suffix = f" ({suffix})" if suffix else ""
    room = CHOICE_MAX_LEN - len(suffix)
    if len(name) > room:
        name = name[: room - 1] + "…"
    return f"{name}{suffix}"


def suggest_adventures(
    query: str,
    *,
    wishlist_names: list[str],
    recent: list[tuple[str, str]],
    catalog: list[dict],
    wishlist_label: str = "requested",
    limit: int = AUTOCOMPLETE_LIMIT,
) -> list[tuple[str, str]]:
    """Autocomplete suggestions as ``(label, value)`` pairs.

    Existing wishlist requests come first so players join them rather than
    creating near-duplicates, then recent sessions, then 2-hour catalog
    adventures (already-prepped first, then newest). An empty query only lists
    the wishlist and recent sessions. ``recent`` is ``(name, date label)`` pairs.
    """
    query_tokens = normalize(query).split()
    query_forms = (normalize(query, strip_zeros=False).split(), query_tokens)
    suggestions: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(name: str, suffix: str) -> bool:
        key = normalize(name) or name.casefold()
        if key in seen:
            return len(suggestions) < limit
        seen.add(key)
        suggestions.append((_choice_label(name, suffix), name[:CHOICE_MAX_LEN]))
        return len(suggestions) < limit

    for name in wishlist_names:
        if _query_matches(query_forms, normalize(name, strip_zeros=False), normalize(name)) and not add(
            name, wishlist_label
        ):
            return suggestions
    for name, date_label in recent:
        if _query_matches(query_forms, normalize(name, strip_zeros=False), normalize(name)) and not add(
            name, f"ran {date_label}"
        ):
            return suggestions
    if not query_tokens:
        return suggestions

    query_key = " ".join(query_tokens)
    matches = [
        entry
        for entry in catalog
        if entry["hours"] == SUGGESTED_HOURS
        and _query_matches(query_forms, entry["keys"]["search"], entry["keys"]["name"])
    ]
    matches.sort(key=lambda entry: entry["date"], reverse=True)
    matches.sort(key=lambda entry: (entry["keys"]["code"] != query_key, not entry.get("prepped")))
    for entry in matches:
        details = [f"{entry['hours']}h", f"T{entry['tier']}" if entry["tier"] else ""]
        if entry.get("prepped"):
            details.append("prepped")
        if not add(entry["name"], ", ".join(detail for detail in details if detail)):
            break
    return suggestions
