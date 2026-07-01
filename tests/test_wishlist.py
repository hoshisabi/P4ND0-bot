from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from utils.warhorn_api import select_recent_past_sessions
from utils.wishlist_format import (
    RECENT_WARHORN_COUNT,
    build_browse_catalog,
    build_wishlist_catalog,
    format_browse_catalog,
    resolve_wishlist_number,
)

EASTERN = ZoneInfo("America/New_York")


def _entry(adventure: str, display_name: str) -> dict:
    return {"adventure": adventure, "display_name": display_name}


def _session(name: str, start: datetime) -> dict:
    return {
        "name": name,
        "startsAt": start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def test_build_wishlist_catalog_groups_and_sorts_adventures():
    entries = [
        _entry("Dragon of Icespire Peak", "Bob"),
        _entry("Absent without Leave", "Alice"),
        _entry("Absent without Leave", "Charlie"),
        _entry("Dragon of Icespire Peak", "Bob"),
    ]

    catalog = build_wishlist_catalog(entries)

    assert [item["adventure"] for item in catalog] == [
        "Absent without Leave",
        "Dragon of Icespire Peak",
    ]
    assert catalog[0]["requesters"] == ["Alice", "Charlie"]
    assert catalog[1]["requesters"] == ["Bob"]
    assert all(item["source"] == "wishlist" for item in catalog)


def test_build_browse_catalog_appends_recent_warhorn_sessions():
    wishlist = [_entry("Absent without Leave", "Alice")]
    recent = [
        _session("Absent without Leave", datetime(2026, 6, 10, 19, 0, tzinfo=EASTERN)),
        _session("Dragon of Icespire Peak", datetime(2026, 6, 3, 19, 0, tzinfo=EASTERN)),
    ]

    catalog = build_browse_catalog(wishlist, recent)

    assert len(catalog) == 2
    assert catalog[0]["source"] == "wishlist"
    assert catalog[1]["adventure"] == "Dragon of Icespire Peak"
    assert catalog[1]["source"] == "warhorn"


def test_format_browse_catalog_uses_continuous_numbering():
    wishlist = [_entry("Absent without Leave", "Alice")]
    recent = [
        _session("Dragon of Icespire Peak", datetime(2026, 6, 3, 19, 0, tzinfo=EASTERN)),
    ]
    catalog = build_browse_catalog(wishlist, recent)

    text = format_browse_catalog(catalog)

    assert "**Requested by players**" in text
    assert "**1.** Absent without Leave — Alice" in text
    assert "**Recent sessions**" in text
    assert "**2.** Dragon of Icespire Peak — <t:" in text


def test_resolve_wishlist_number_returns_adventure_name():
    catalog = build_browse_catalog(
        [_entry("Absent without Leave", "Alice")],
        [_session("Dragon of Icespire Peak", datetime(2026, 6, 3, 19, 0, tzinfo=EASTERN))],
    )

    assert resolve_wishlist_number(catalog, 1) == "Absent without Leave"
    assert resolve_wishlist_number(catalog, 2) == "Dragon of Icespire Peak"
    assert resolve_wishlist_number(catalog, 0) is None
    assert resolve_wishlist_number(catalog, 3) is None


def test_select_recent_past_sessions_limits_and_dedupes():
    now = datetime(2026, 6, 17, 12, 0, tzinfo=EASTERN).astimezone(timezone.utc)
    nodes = [
        _session("Older duplicate", datetime(2026, 5, 1, 19, 0, tzinfo=EASTERN)),
        _session("Older duplicate", datetime(2026, 5, 8, 19, 0, tzinfo=EASTERN)),
        _session("Recent A", datetime(2026, 6, 10, 19, 0, tzinfo=EASTERN)),
        _session("Recent B", datetime(2026, 6, 3, 19, 0, tzinfo=EASTERN)),
        _session("Upcoming", datetime(2026, 6, 24, 19, 0, tzinfo=EASTERN)),
    ]

    recent = select_recent_past_sessions(nodes, limit=RECENT_WARHORN_COUNT, now=now)

    assert [session["name"] for session in recent] == ["Recent A", "Recent B", "Older duplicate"]
