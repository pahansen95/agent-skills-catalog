"""Unit tests for session storage helpers: save/load, CURRENT, hold, lock, turns."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def test_path_helpers(coro_module, tmp_project):
    slug = "foo_100"
    assert coro_module.coro_dir(tmp_project) == tmp_project / ".cache" / "coro"
    assert coro_module.slug_dir(tmp_project, slug) == tmp_project / ".cache" / "coro" / slug
    assert coro_module.session_file(tmp_project, slug).name == "uuid"
    assert coro_module.meta_file(tmp_project, slug).name == "meta"
    assert coro_module.send_lock_path(tmp_project, slug).name == "lock"
    assert coro_module.hold_sentinel_path(tmp_project, slug).name == "hold"
    assert coro_module.turns_dir(tmp_project, slug).name == "turns"
    assert coro_module.turn_log_file(tmp_project, slug, 5).name == "005.jsonl"


# ---------------------------------------------------------------------------
# save_session / load_session / load_meta
# ---------------------------------------------------------------------------

def test_save_and_load_session(coro_module, tmp_project):
    coro_module.save_session(tmp_project, "foo_100", "uuid-abc", "sonnet")
    assert coro_module.load_session(tmp_project, "foo_100") == "uuid-abc"
    assert coro_module.load_meta(tmp_project, "foo_100") == {"model": "sonnet"}


def test_load_session_missing_raises(coro_module, tmp_project):
    with pytest.raises(coro_module.CoroError, match="no session"):
        coro_module.load_session(tmp_project, "ghost_100")


def test_load_meta_missing_returns_empty_dict(coro_module, tmp_project):
    assert coro_module.load_meta(tmp_project, "ghost_100") == {}


# ---------------------------------------------------------------------------
# Turn numbering
# ---------------------------------------------------------------------------

def test_next_turn_number_initial_is_zero(coro_module, tmp_project):
    coro_module.save_session(tmp_project, "foo_100", "u", "sonnet")
    assert coro_module.next_turn_number(tmp_project, "foo_100") == 0


def test_next_turn_number_advances(coro_module, tmp_project):
    coro_module.save_session(tmp_project, "foo_100", "u", "sonnet")
    coro_module.save_turn(tmp_project, "foo_100", 0, [{"type": "result"}])
    assert coro_module.next_turn_number(tmp_project, "foo_100") == 1

    coro_module.save_turn(tmp_project, "foo_100", 1, [{"type": "result"}])
    assert coro_module.next_turn_number(tmp_project, "foo_100") == 2


def test_last_turn_number_empty_returns_neg1(coro_module, tmp_project):
    coro_module.save_session(tmp_project, "foo_100", "u", "sonnet")
    assert coro_module.last_turn_number(tmp_project, "foo_100") == -1


def test_last_turn_number_finds_highest(coro_module, tmp_project):
    coro_module.save_session(tmp_project, "foo_100", "u", "sonnet")
    coro_module.save_turn(tmp_project, "foo_100", 0, [])
    coro_module.save_turn(tmp_project, "foo_100", 1, [])
    coro_module.save_turn(tmp_project, "foo_100", 2, [])
    assert coro_module.last_turn_number(tmp_project, "foo_100") == 2


def test_turn_log_file_zero_padded(coro_module, tmp_project):
    p = coro_module.turn_log_file(tmp_project, "foo_100", 7)
    assert p.name == "007.jsonl"
    p = coro_module.turn_log_file(tmp_project, "foo_100", 123)
    assert p.name == "123.jsonl"


def test_save_turn_creates_jsonl(coro_module, tmp_project):
    events = [
        {"type": "system", "session_id": "a"},
        {"type": "result", "total_cost_usd": 0.01},
    ]
    coro_module.save_turn(tmp_project, "foo_100", 0, events)
    path = coro_module.turn_log_file(tmp_project, "foo_100", 0)
    assert path.exists()
    lines = path.read_text().strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["type"] == "system"
    assert json.loads(lines[1])["type"] == "result"


def test_open_turn_writer_creates_dirs_and_returns_writer(coro_module, tmp_project):
    w = coro_module.open_turn_writer(tmp_project, "foo_100", 0)
    try:
        w.write(json.dumps({"type": "test"}) + "\n")
    finally:
        w.close()
    assert coro_module.turn_log_file(tmp_project, "foo_100", 0).exists()


# ---------------------------------------------------------------------------
# CURRENT stack
# ---------------------------------------------------------------------------

def test_current_top_empty(coro_module, tmp_project):
    assert coro_module.current_top(tmp_project) is None


def test_current_push_pop(coro_module, tmp_project):
    coro_module.current_push(tmp_project, "a_100")
    coro_module.current_push(tmp_project, "b_200")
    assert coro_module.current_top(tmp_project) == "b_200"
    assert coro_module.current_pop(tmp_project) == "b_200"
    assert coro_module.current_top(tmp_project) == "a_100"
    assert coro_module.current_pop(tmp_project) == "a_100"
    assert coro_module.current_pop(tmp_project) is None


def test_current_list(coro_module, tmp_project):
    coro_module.current_push(tmp_project, "a_100")
    coro_module.current_push(tmp_project, "b_200")
    coro_module.current_push(tmp_project, "c_300")
    assert coro_module.current_list(tmp_project) == ["a_100", "b_200", "c_300"]


def test_current_pop_empty_returns_none(coro_module, tmp_project):
    assert coro_module.current_pop(tmp_project) is None


# ---------------------------------------------------------------------------
# Hold sentinel
# ---------------------------------------------------------------------------

def test_hold_lifecycle(coro_module, tmp_project):
    coro_module.save_session(tmp_project, "foo_100", "u", "sonnet")
    # No hold → read_hold returns (False, "")
    assert coro_module.read_hold(tmp_project, "foo_100") == (False, "")

    # Write with reason
    coro_module.write_hold(tmp_project, "foo_100", "waiting on X")
    is_held, reason = coro_module.read_hold(tmp_project, "foo_100")
    assert is_held is True
    assert reason == "waiting on X"

    # clear_hold returns the prior reason
    prior = coro_module.clear_hold(tmp_project, "foo_100")
    assert prior == "waiting on X"
    assert coro_module.read_hold(tmp_project, "foo_100") == (False, "")


def test_hold_without_reason(coro_module, tmp_project):
    coro_module.save_session(tmp_project, "foo_100", "u", "sonnet")
    coro_module.write_hold(tmp_project, "foo_100", "")
    is_held, reason = coro_module.read_hold(tmp_project, "foo_100")
    assert is_held is True
    assert reason == ""


def test_hold_is_idempotent(coro_module, tmp_project):
    coro_module.save_session(tmp_project, "foo_100", "u", "sonnet")
    coro_module.write_hold(tmp_project, "foo_100", "first")
    coro_module.write_hold(tmp_project, "foo_100", "second")
    _, reason = coro_module.read_hold(tmp_project, "foo_100")
    assert reason == "second"


def test_clear_hold_no_sentinel_returns_none(coro_module, tmp_project):
    coro_module.save_session(tmp_project, "foo_100", "u", "sonnet")
    assert coro_module.clear_hold(tmp_project, "foo_100") is None


def test_hold_writes_iso_timestamp_on_line_2(coro_module, tmp_project):
    coro_module.save_session(tmp_project, "foo_100", "u", "sonnet")
    coro_module.write_hold(tmp_project, "foo_100", "r")
    content = coro_module.hold_sentinel_path(tmp_project, "foo_100").read_text()
    lines = content.splitlines()
    assert lines[0] == "r"
    # ISO-8601 UTC: contains a 'T' and either '+00:00' or 'Z' suffix
    assert "T" in lines[1]


# ---------------------------------------------------------------------------
# Send lock
# ---------------------------------------------------------------------------

def test_send_lock_not_held_by_default(coro_module, tmp_project):
    coro_module.save_session(tmp_project, "foo_100", "u", "sonnet")
    assert coro_module.check_send_lock(tmp_project, "foo_100") is False


def test_send_lock_exclusive_blocks_second_acquire(coro_module, tmp_project):
    coro_module.save_session(tmp_project, "foo_100", "u", "sonnet")
    fh = coro_module.acquire_send_lock(tmp_project, "foo_100")
    try:
        # Within the same process, fcntl.flock is per-fd. A second acquire
        # from another file handle should fail.
        with pytest.raises(coro_module.CoroError, match="another send"):
            coro_module.acquire_send_lock(tmp_project, "foo_100")
    finally:
        fh.close()


def test_send_lock_check_returns_true_while_held(coro_module, tmp_project):
    """check_send_lock uses a non-blocking shared lock probe; while the
    exclusive lock is held, it reports held."""
    coro_module.save_session(tmp_project, "foo_100", "u", "sonnet")
    fh = coro_module.acquire_send_lock(tmp_project, "foo_100")
    try:
        assert coro_module.check_send_lock(tmp_project, "foo_100") is True
    finally:
        fh.close()
    # After close, lock released
    assert coro_module.check_send_lock(tmp_project, "foo_100") is False


def test_send_lock_after_release_reusable(coro_module, tmp_project):
    coro_module.save_session(tmp_project, "foo_100", "u", "sonnet")
    fh1 = coro_module.acquire_send_lock(tmp_project, "foo_100")
    fh1.close()
    fh2 = coro_module.acquire_send_lock(tmp_project, "foo_100")
    fh2.close()


# ---------------------------------------------------------------------------
# session_total_cost
# ---------------------------------------------------------------------------

def test_session_total_cost_empty(coro_module, tmp_project):
    coro_module.save_session(tmp_project, "foo_100", "u", "sonnet")
    assert coro_module.session_total_cost(tmp_project, "foo_100") == 0.0


def test_session_total_cost_sums_turns(coro_module, tmp_project):
    coro_module.save_session(tmp_project, "foo_100", "u", "sonnet")
    coro_module.save_turn(tmp_project, "foo_100", 0, [{"type": "result", "total_cost_usd": 0.10}])
    coro_module.save_turn(tmp_project, "foo_100", 1, [{"type": "result", "total_cost_usd": 0.25}])
    coro_module.save_turn(tmp_project, "foo_100", 2, [{"type": "result", "total_cost_usd": 0.05}])
    assert coro_module.session_total_cost(tmp_project, "foo_100") == pytest.approx(0.40)


def test_session_total_cost_skips_missing_result(coro_module, tmp_project):
    coro_module.save_session(tmp_project, "foo_100", "u", "sonnet")
    # Turn with no result event contributes nothing
    coro_module.save_turn(tmp_project, "foo_100", 0, [{"type": "system"}])
    coro_module.save_turn(tmp_project, "foo_100", 1, [{"type": "result", "total_cost_usd": 0.10}])
    assert coro_module.session_total_cost(tmp_project, "foo_100") == pytest.approx(0.10)
