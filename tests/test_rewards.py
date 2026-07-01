from datetime import datetime
from zoneinfo import ZoneInfo

from cogs.sessions import Sessions
from utils.db import select_rewards_session

EASTERN = ZoneInfo("America/New_York")


def _session_row(
    session_id: int,
    name: str,
    starts_at: datetime,
    updated_at: datetime,
) -> dict:
    return {
        "id": session_id,
        "session_name": name,
        "session_starts_at": starts_at,
        "updated_at": updated_at,
    }


def test_select_rewards_session_prefers_todays_game_over_next_week():
    now = datetime(2026, 6, 10, 21, 0, tzinfo=EASTERN)
    rows = [
        _session_row(
            1,
            "Next week's adventure",
            datetime(2026, 6, 17, 19, 0, tzinfo=EASTERN),
            datetime(2026, 6, 3, 19, 0, tzinfo=EASTERN),
        ),
        _session_row(
            2,
            "Tonight's adventure",
            datetime(2026, 6, 10, 19, 0, tzinfo=EASTERN),
            datetime(2026, 6, 10, 19, 5, tzinfo=EASTERN),
        ),
    ]

    picked = select_rewards_session(rows, now=now)
    assert picked["session_name"] == "Tonight's adventure"


def test_select_rewards_session_uses_session_logged_today_before_start():
    now = datetime(2026, 6, 10, 17, 0, tzinfo=EASTERN)
    rows = [
        _session_row(
            1,
            "Tonight's adventure",
            datetime(2026, 6, 10, 19, 0, tzinfo=EASTERN),
            datetime(2026, 6, 10, 17, 0, tzinfo=EASTERN),
        ),
    ]

    picked = select_rewards_session(rows, now=now)
    assert picked["session_name"] == "Tonight's adventure"


def test_select_rewards_session_includes_yesterday_after_midnight():
    now = datetime(2026, 6, 11, 1, 0, tzinfo=EASTERN)
    rows = [
        _session_row(
            1,
            "Last night's adventure",
            datetime(2026, 6, 10, 19, 0, tzinfo=EASTERN),
            datetime(2026, 6, 10, 19, 5, tzinfo=EASTERN),
        ),
        _session_row(
            2,
            "Next week's adventure",
            datetime(2026, 6, 17, 19, 0, tzinfo=EASTERN),
            datetime(2026, 6, 3, 19, 0, tzinfo=EASTERN),
        ),
    ]

    picked = select_rewards_session(rows, now=now)
    assert picked["session_name"] == "Last night's adventure"


def test_format_rewards_message_includes_participant_mentions():
    message = Sessions._format_rewards_message(
        "116.67gp each",
        "The Lost Mine",
        "2 hours streaming",
        participant_ids=[111, 222],
    )
    assert message.startswith("The Lost Mine, 10 downtime, level if you want it, 2 hours streaming, 116.67gp each")
    assert message.endswith("<@111> <@222>")


def test_format_rewards_message_omits_mentions_when_no_players():
    message = Sessions._format_rewards_message(
        "116.67gp each",
        "The Lost Mine",
        "2 hours streaming",
        participant_ids=[],
    )
    assert "\n" not in message
    assert "<@" not in message


def test_format_rewards_message_adds_mentions_to_full_message():
    full = "Custom adventure, 10 downtime, level if you want it, 2 hours streaming, loot"
    message = Sessions._format_rewards_message(
        full,
        None,
        "2 hours streaming",
        participant_ids=[999],
    )
    assert message == f"{full}\n<@999>"
