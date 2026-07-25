import pytest

from app.wait_time import (
    ALMOST_READY_POSITION,
    estimate_queue_wait,
    estimate_wait_minutes,
    format_wait,
    is_almost_ready,
)


# ---- estimate_wait_minutes ----


def test_first_in_line_waits_zero():
    assert estimate_wait_minutes(1, 25) == 0


def test_wait_scales_with_position():
    assert estimate_wait_minutes(2, 25) == 25
    assert estimate_wait_minutes(4, 25) == 75


def test_matches_a2_screenshot_numbers():
    # A2 Join Queue showed "8 people waiting - ~24 min" for a 3-minute service.
    assert estimate_wait_minutes(9, 3) == 24


def test_zero_duration_service():
    assert estimate_wait_minutes(5, 0) == 0


def test_position_must_be_at_least_one():
    with pytest.raises(ValueError):
        estimate_wait_minutes(0, 25)
    with pytest.raises(ValueError):
        estimate_wait_minutes(-3, 25)


def test_position_must_be_integer():
    with pytest.raises(ValueError):
        estimate_wait_minutes(2.5, 25)
    with pytest.raises(ValueError):
        estimate_wait_minutes("2", 25)


def test_position_rejects_boolean():
    with pytest.raises(ValueError):
        estimate_wait_minutes(True, 25)


def test_duration_must_be_non_negative_integer():
    with pytest.raises(ValueError):
        estimate_wait_minutes(2, -5)
    with pytest.raises(ValueError):
        estimate_wait_minutes(2, "25")


# ---- is_almost_ready ----


def test_almost_ready_near_front():
    assert is_almost_ready(1) is True
    assert is_almost_ready(ALMOST_READY_POSITION) is True


def test_not_almost_ready_further_back():
    assert is_almost_ready(ALMOST_READY_POSITION + 1) is False
    assert is_almost_ready(20) is False


def test_almost_ready_rejects_bad_position():
    with pytest.raises(ValueError):
        is_almost_ready(0)
    with pytest.raises(ValueError):
        is_almost_ready("1")


# ---- estimate_queue_wait ----


def test_queue_wait_assigns_positions_in_order():
    entries = [{"user_id": "a"}, {"user_id": "b"}, {"user_id": "c"}]
    results = estimate_queue_wait(entries, 10)

    assert [r["position"] for r in results] == [1, 2, 3]
    assert [r["estimated_wait_minutes"] for r in results] == [0, 10, 20]
    assert results[0]["entry"]["user_id"] == "a"


def test_queue_wait_flags_almost_ready():
    entries = [{"user_id": str(i)} for i in range(5)]
    results = estimate_queue_wait(entries, 10)

    assert [r["almost_ready"] for r in results] == [True, True, True, False, False]


def test_empty_queue_returns_empty_list():
    assert estimate_queue_wait([], 10) == []


# ---- format_wait ----


def test_format_zero_is_youre_next():
    assert format_wait(0) == "You're next"


def test_format_minutes():
    assert format_wait(24) == "~24 min"
    assert format_wait(59) == "~59 min"


def test_format_exact_hours():
    assert format_wait(60) == "~1 hr"
    assert format_wait(120) == "~2 hr"


def test_format_hours_and_minutes():
    assert format_wait(75) == "~1 hr 15 min"
    assert format_wait(145) == "~2 hr 25 min"


def test_format_rejects_negative():
    with pytest.raises(ValueError):
        format_wait(-1)


def test_format_rejects_non_integer():
    with pytest.raises(ValueError):
        format_wait("24")
