# Wait-Time Estimation Logic
#
# Rule-based, as the assignment allows: position x expected duration.
# Kept separate from queues.py so it can be unit tested on its own and
# imported by the queue module:
#
#     from app.wait_time import estimate_wait_minutes
#     wait = estimate_wait_minutes(position, service["expected_duration"])

# How close to the front a user must be before they are "almost ready".
# Used by the notification module to decide when to warn someone.
ALMOST_READY_POSITION = 3


def estimate_wait_minutes(position, expected_duration):
    """Estimate minutes until a user at `position` is served.

    position is 1-based: position 1 is the person being served next, so
    they wait 0 minutes. Position 3 waits for the 2 people ahead of them.

    Raises ValueError on nonsensical input so callers fail loudly instead
    of silently returning a wrong estimate.
    """
    if isinstance(position, bool) or not isinstance(position, int):
        raise ValueError("Position must be a whole number")
    if position < 1:
        raise ValueError("Position must be 1 or greater")

    if isinstance(expected_duration, bool) or not isinstance(expected_duration, int):
        raise ValueError("Expected duration must be a whole number of minutes")
    if expected_duration < 0:
        raise ValueError("Expected duration cannot be negative")

    return (position - 1) * expected_duration


def estimate_queue_wait(entries, expected_duration):
    """Return a wait estimate for every entry in an ordered queue.

    `entries` is the already-ordered list from the queue module (arrival
    order with priority applied). Returns a list of dicts so the front end
    can render position and wait together.
    """
    results = []
    for index, entry in enumerate(entries, start=1):
        results.append({
            "entry": entry,
            "position": index,
            "estimated_wait_minutes": estimate_wait_minutes(index, expected_duration),
            "almost_ready": is_almost_ready(index),
        })
    return results


def is_almost_ready(position):
    """True when a user is close enough to the front to be notified."""
    if isinstance(position, bool) or not isinstance(position, int):
        raise ValueError("Position must be a whole number")
    if position < 1:
        raise ValueError("Position must be 1 or greater")
    return position <= ALMOST_READY_POSITION


def format_wait(minutes):
    """Human-readable wait, matching the '~24 min' style used in the A2 UI."""
    if isinstance(minutes, bool) or not isinstance(minutes, int):
        raise ValueError("Minutes must be a whole number")
    if minutes < 0:
        raise ValueError("Minutes cannot be negative")
    if minutes == 0:
        return "You're next"
    if minutes < 60:
        return f"~{minutes} min"

    hours, remainder = divmod(minutes, 60)
    if remainder == 0:
        return f"~{hours} hr"
    return f"~{hours} hr {remainder} min"
