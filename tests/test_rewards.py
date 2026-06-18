from cogs.sessions import Sessions


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
