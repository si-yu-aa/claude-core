from claude_core.agents.mailbox import Mailbox


def test_mailbox_routes_to_specific_recipient():
    mailbox = Mailbox()

    mailbox.send("agent-a", "agent-b", {"msg": "for b"})
    mailbox.send("agent-a", "agent-c", {"msg": "for c"})

    first = mailbox.receive("agent-b")
    second = mailbox.receive("agent-c")

    assert first is not None
    assert first.recipient_id == "agent-b"
    assert first.content == {"msg": "for b"}

    assert second is not None
    assert second.recipient_id == "agent-c"
    assert second.content == {"msg": "for c"}


def test_mailbox_keeps_other_recipients_messages():
    mailbox = Mailbox()

    mailbox.send("agent-a", "agent-c", "keep me")

    assert mailbox.receive("agent-b") is None
    assert mailbox.receive("agent-c").content == "keep me"
