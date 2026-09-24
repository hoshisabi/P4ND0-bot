from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from utils.warhorn_api import select_recent_past_sessions
from utils.wishlist_format import (
    RECENT_WARHORN_COUNT,
    build_browse_catalog,
    build_player_wishlists,
    build_wishlist_catalog,
    format_browse_catalog,
    format_player_wishlists,
    format_trim_result,
    match_wishlist_adventure,
    plan_wishlist_trim,
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

    assert [(item["adventure"], item["source"]) for item in catalog] == [
        ("Absent without Leave", "wishlist"),
        ("Absent without Leave", "warhorn"),
        ("Dragon of Icespire Peak", "warhorn"),
    ]


def test_build_browse_catalog_recent_sessions_not_crowded_out_by_wishlist():
    wishlist = [_entry(f"Wishlisted {n}", "Alice") for n in range(3)]
    recent = [
        _session(f"Wishlisted {n}", datetime(2026, 9, 16 - 7 * n, 19, 0, tzinfo=EASTERN))
        for n in range(3)
    ] + [_session("Only run", datetime(2026, 8, 19, 19, 0, tzinfo=EASTERN))]

    catalog = build_browse_catalog(wishlist, recent, recent_limit=2)
    recent_items = [item for item in catalog if item["source"] == "warhorn"]

    assert [item["adventure"] for item in recent_items] == ["Wishlisted 0", "Wishlisted 1"]
    assert resolve_wishlist_number(catalog, 4) == "Wishlisted 0"


def test_build_player_wishlists_groups_by_user_with_newest_name():
    entries = [
        {"discord_user_id": 2, "adventure": "Spider Hunt", "display_name": "Ken (Keno)",
         "created_at": datetime(2026, 9, 1)},
        {"discord_user_id": 1, "adventure": "Endless Glory", "display_name": "Michael",
         "created_at": datetime(2026, 8, 1)},
        {"discord_user_id": 2, "adventure": "Endless Revel", "display_name": "Ken (Poweye)",
         "created_at": datetime(2026, 7, 1)},
    ]

    players = build_player_wishlists(entries)

    assert [(p["display_name"], p["adventures"]) for p in players] == [
        ("Ken (Keno)", ["Endless Revel", "Spider Hunt"]),
        ("Michael", ["Endless Glory"]),
    ]
    text = format_player_wishlists(players)
    assert text == "**Ken (Keno)**\n• Endless Revel\n• Spider Hunt\n\n**Michael**\n• Endless Glory"
    assert format_player_wishlists([]) == "*No wishlist entries yet.*"


def test_format_browse_catalog_uses_continuous_numbering():
    wishlist = [_entry("Absent without Leave", "Alice")]
    recent = [
        _session("Dragon of Icespire Peak", datetime(2026, 6, 3, 19, 0, tzinfo=EASTERN)),
    ]
    catalog = build_browse_catalog(wishlist, recent)

    admin_text = format_browse_catalog(catalog, include_requesters=True)
    player_text = format_browse_catalog(catalog, include_requesters=False)

    assert "**Requested by players**" in admin_text
    assert "**1.** Absent without Leave — Alice" in admin_text
    assert "**Recent sessions**" in admin_text
    assert "**2.** Dragon of Icespire Peak — <t:" in admin_text

    assert "**Requested by players**" in player_text
    assert "**1.** Absent without Leave" in player_text
    assert "Alice" not in player_text
    assert "**Recent sessions**" in player_text
    assert "**2.** Dragon of Icespire Peak — <t:" in player_text


def test_resolve_wishlist_number_returns_adventure_name():
    catalog = build_browse_catalog(
        [_entry("Absent without Leave", "Alice")],
        [_session("Dragon of Icespire Peak", datetime(2026, 6, 3, 19, 0, tzinfo=EASTERN))],
    )

    assert resolve_wishlist_number(catalog, 1) == "Absent without Leave"
    assert resolve_wishlist_number(catalog, 2) == "Dragon of Icespire Peak"
    assert resolve_wishlist_number(catalog, 0) is None
    assert resolve_wishlist_number(catalog, 3) is None


def test_match_wishlist_adventure_exact_and_session_title():
    catalog = build_wishlist_catalog([
        _entry("Absent without Leave", "Alice"),
        _entry("Dragon of Icespire Peak", "Bob"),
    ])

    assert match_wishlist_adventure(catalog, "Absent without Leave") == "Absent without Leave"
    assert match_wishlist_adventure(catalog, "absent without leave") == "Absent without Leave"
    assert match_wishlist_adventure(catalog, "PS-DC-PUB-10 Absent without Leave") == "Absent without Leave"
    assert match_wishlist_adventure(catalog, "Unknown") is None
    assert match_wishlist_adventure(catalog, "") is None


def test_match_wishlist_adventure_ambiguous_containment_returns_none():
    catalog = build_wishlist_catalog([
        _entry("Leave", "Alice"),
        _entry("Absent without Leave", "Bob"),
    ])

    assert match_wishlist_adventure(catalog, "PS Absent without Leave") is None
    assert match_wishlist_adventure(catalog, "Leave") == "Leave"


def test_format_trim_result_clears_whole_adventure():
    removed = [
        {"display_name": "Alice", "discord_user_id": 1},
        {"display_name": "Bob", "discord_user_id": 2},
    ]

    assert format_trim_result("Absent without Leave", removed) == (
        "Trimmed **Absent without Leave** from the wishlist (Alice, Bob)."
    )
    assert format_trim_result("Absent without Leave", []) == (
        "Nobody has wishlisted **Absent without Leave**."
    )


def test_format_trim_result_removes_selected_players():
    removed = [{"display_name": "Alice", "discord_user_id": 1}]
    remaining = [{"display_name": "Charlie", "discord_user_id": 3}]

    assert format_trim_result(
        "Absent without Leave",
        removed,
        targeted=True,
        remaining=remaining,
        not_listed_names=["Bob"],
    ) == (
        "Removed Alice from the wishlist for **Absent without Leave**. "
        "Still listed: Charlie. Bob was not listed."
    )
    assert format_trim_result(
        "Absent without Leave",
        [],
        targeted=True,
        not_listed_names=["Alice", "Bob"],
    ) == "Alice, Bob have not wishlisted **Absent without Leave**."


def test_plan_wishlist_trim_keep_leaves_named_players():
    entries = [
        {"discord_user_id": 1, "display_name": "Alice"},
        {"discord_user_id": 2, "display_name": "Bob"},
        {"discord_user_id": 3, "display_name": "Charlie"},
    ]

    delete_ids, not_listed, abort = plan_wishlist_trim(entries, keep_ids=[3])
    assert delete_ids == [1, 2]
    assert not_listed == []
    assert abort is False

    delete_ids, not_listed, abort = plan_wishlist_trim(entries, keep_ids=[3, 99])
    assert delete_ids == [1, 2]
    assert not_listed == [99]
    assert abort is False

    delete_ids, not_listed, abort = plan_wishlist_trim(entries, keep_ids=[99])
    assert delete_ids == []
    assert not_listed == [99]
    assert abort is True


def test_plan_wishlist_trim_remove_and_clear():
    entries = [
        {"discord_user_id": 1, "display_name": "Alice"},
        {"discord_user_id": 2, "display_name": "Bob"},
    ]

    delete_ids, not_listed, abort = plan_wishlist_trim(entries, remove_ids=[1, 99])
    assert delete_ids == [1]
    assert not_listed == [99]
    assert abort is False

    delete_ids, not_listed, abort = plan_wishlist_trim(entries)
    assert delete_ids is None
    assert not_listed == []
    assert abort is False


def test_format_trim_result_keeps_selected_players():
    removed = [
        {"display_name": "Alice", "discord_user_id": 1},
        {"display_name": "Bob", "discord_user_id": 2},
    ]
    remaining = [{"display_name": "Charlie", "discord_user_id": 3}]

    assert format_trim_result(
        "Absent without Leave",
        removed,
        kept=True,
        remaining=remaining,
    ) == (
        "Trimmed **Absent without Leave** from the wishlist (Alice, Bob). "
        "Left on the list: Charlie."
    )
    assert format_trim_result(
        "Absent without Leave",
        [],
        kept=True,
        remaining=remaining,
    ) == (
        "Nobody else was listed for **Absent without Leave**. Left on the list: Charlie."
    )
    assert format_trim_result(
        "Absent without Leave",
        [],
        kept=True,
        abort=True,
        not_listed_names=["Charlie"],
    ) == (
        "Charlie has not wishlisted **Absent without Leave**, so nobody was removed."
    )


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
