"""ponytail self-check: reminder cooldown logic in business._due_for_reminder."""
from datetime import datetime, timedelta

from business import _due_for_reminder, REMINDER_COOLDOWN_HOURS


def test_due_for_reminder():
    now = datetime.utcnow()

    assert _due_for_reminder({}, now) is True  # never reminded -> due

    fresh = {"last_reminded_at": now - timedelta(hours=1)}
    assert _due_for_reminder(fresh, now) is False  # inside cooldown -> not due

    stale = {"last_reminded_at": now - timedelta(hours=REMINDER_COOLDOWN_HOURS + 1)}
    assert _due_for_reminder(stale, now) is True  # past cooldown -> due again


if __name__ == "__main__":
    test_due_for_reminder()
    print("ok")
