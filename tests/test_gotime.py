from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from utils.session_format import build_gotime_embed, format_player_lines
from utils.warhorn_api import find_current_session, format_obs_copy, OBS_TITLE_PREFIX

EASTERN = ZoneInfo("America/New_York")


def _session(name: str, start: datetime, end: datetime | None = None) -> dict:
    payload = {
        "id": name,
        "name": name,
        "startsAt": start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    if end is not None:
        payload["endsAt"] = end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return payload


def test_find_current_session_prefers_in_progress_over_upcoming():
    now = datetime(2026, 6, 10, 20, 0, tzinfo=EASTERN).astimezone(timezone.utc)
    current = _session(
        "Tonight",
        datetime(2026, 6, 10, 19, 0, tzinfo=EASTERN),
        datetime(2026, 6, 10, 23, 0, tzinfo=EASTERN),
    )
    upcoming = _session(
        "Next week",
        datetime(2026, 6, 17, 19, 0, tzinfo=EASTERN),
        datetime(2026, 6, 17, 23, 0, tzinfo=EASTERN),
    )

    picked = find_current_session([upcoming, current], now=now)
    assert picked["name"] == "Tonight"


def test_find_current_session_uses_todays_started_session_not_next_week():
    now = datetime(2026, 6, 10, 21, 0, tzinfo=EASTERN).astimezone(timezone.utc)
    tonight = _session(
        "PS-DC-PUB-10 Absent without Leave",
        datetime(2026, 6, 10, 19, 0, tzinfo=EASTERN),
        datetime(2026, 6, 10, 23, 0, tzinfo=EASTERN),
    )
    next_week = _session(
        "Future adventure",
        datetime(2026, 6, 17, 19, 0, tzinfo=EASTERN),
        datetime(2026, 6, 17, 23, 0, tzinfo=EASTERN),
    )

    picked = find_current_session([next_week, tonight], now=now)
    assert picked["name"] == "PS-DC-PUB-10 Absent without Leave"


def test_find_current_session_before_start_picks_todays_upcoming():
    now = datetime(2026, 6, 10, 17, 0, tzinfo=EASTERN).astimezone(timezone.utc)
    tonight = _session(
        "Tonight",
        datetime(2026, 6, 10, 19, 0, tzinfo=EASTERN),
        datetime(2026, 6, 10, 23, 0, tzinfo=EASTERN),
    )
    next_week = _session(
        "Next week",
        datetime(2026, 6, 17, 19, 0, tzinfo=EASTERN),
        datetime(2026, 6, 17, 23, 0, tzinfo=EASTERN),
    )

    picked = find_current_session([next_week, tonight], now=now)
    assert picked["name"] == "Tonight"


def test_format_obs_copy_includes_title_and_url():
    session = {
        "name": "PS-DC-PUB-10 Absent without Leave",
        "scenario": {
            "externalUrl": "https://www.dmsguild.com/en/product/531687?affiliate_id=171040",
        },
    }
    text = format_obs_copy(session)
    title = f"{OBS_TITLE_PREFIX}PS-DC-PUB-10 Absent without Leave"
    assert f"Title for OBS: {title}" in text
    assert f'"Go Live Notification": {title}' in text
    assert "https://www.dmsguild.com/en/product/531687?affiliate_id=171040" in text


def test_build_gotime_embed_includes_wishlisted_players():
    session = {
        "id": "session-1",
        "name": "Tonight's Game",
        "startsAt": datetime(2026, 6, 10, 19, 0, tzinfo=EASTERN).astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "scenario": {"externalUrl": "https://example.com/adventure"},
    }
    players = [
        {
            "user_id": 1,
            "display_name": "Alice",
            "character_url": "https://www.dndbeyond.com/characters/1",
            "character_name": "Alera",
        }
    ]
    wishlist = [
        {
            "user_id": 2,
            "display_name": "Bob",
            "character_url": None,
            "character_name": None,
        }
    ]

    embed = build_gotime_embed(session, players, preview=True, wishlist_data=wishlist)

    assert embed.title == "Go-time preview: Tonight's Game"
    player_field = next(field for field in embed.fields if field.name.startswith("Players"))
    wishlist_field = next(field for field in embed.fields if field.name.startswith("Wishlisted"))
    assert "Alice" in player_field.value
    assert "Bob" in wishlist_field.value
    assert embed.footer.text.startswith("Preview only")


def test_format_player_lines_marks_unknown_characters():
    players = [
        {
            "display_name": "Bob",
            "character_url": None,
            "character_name": None,
        }
    ]

    lines, unknown = format_player_lines(players)

    assert lines == ["• Bob → Unknown"]
    assert unknown == ["Bob"]
