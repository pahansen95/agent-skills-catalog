"""Tests for command-function branches not covered by integration happy-paths.

Targets:
  cmd_status — legacy USER_HOLD, missing YIELD, token warning, cost warning,
               runtime-max-output warning, hold-display branch, no-turns.
  cmd_log    — happy (explicit + default), missing-turn, no-turns.
  cmd_pop    — empty stack error.
  cmd_list_sessions — empty stack.
  cmd_use    — bad arg propagates resolve_slug error.
  cmd_unhold — not-held branch.
  cmd_create — deprecated inline-send path.
  read_stdin_or_die — empty-stdin error.
"""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

import pytest


def _script_args(**kw) -> argparse.Namespace:
    return argparse.Namespace(**kw)


def _patch_runner(coro_module, monkeypatch, runner):
    monkeypatch.setattr(coro_module, "_default_runner", runner)


# ---------------------------------------------------------------------------
# Helpers to seed a session with canned turn jsonl
# ---------------------------------------------------------------------------

def _seed_session(coro_module, tmp_project, slug: str, model: str = "haiku"):
    """Create an empty session on disk (uuid + meta written, no turns yet)."""
    coro_module.save_session(tmp_project, slug, f"uuid-{slug}", model)


def _seed_turn(coro_module, tmp_project, slug: str, turn: int, events: list[dict]):
    coro_module.save_turn(tmp_project, slug, turn, events)


def _assistant_text_event(text: str) -> dict:
    return {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": text}]},
    }


def _result_event(
    *,
    cost: float = 0.01,
    input_tokens: int = 10,
    cache_read: int = 0,
    cache_creation: int = 0,
    output_tokens: int = 5,
    ctx_window: int = 200_000,
    max_output: int = 64_000,
    model_id: str = "claude-haiku-4-5-20251001",
    subtype: str = "success",
    is_error: bool = False,
    **extra,
) -> dict:
    return {
        "type": "result",
        "subtype": subtype,
        "is_error": is_error,
        "total_cost_usd": cost,
        "usage": {
            "input_tokens": input_tokens,
            "cache_read_input_tokens": cache_read,
            "cache_creation_input_tokens": cache_creation,
            "output_tokens": output_tokens,
        },
        "modelUsage": {
            model_id: {"contextWindow": ctx_window, "maxOutputTokens": max_output}
        },
        **extra,
    }


# ---------------------------------------------------------------------------
# cmd_status branches
# ---------------------------------------------------------------------------

def test_status_no_turns_errors(coro_module, tmp_project):
    _seed_session(coro_module, tmp_project, "foo_100")
    with pytest.raises(coro_module.CoroError, match="no turns found"):
        coro_module.cmd_status(tmp_project, "foo_100")


def test_status_shows_hold_yes_with_reason(coro_module, tmp_project, capsys):
    _seed_session(coro_module, tmp_project, "foo_100")
    _seed_turn(coro_module, tmp_project, "foo_100", 0, [
        _assistant_text_event("YIELD: DONE | ok"),
        _result_event(),
    ])
    coro_module.write_hold(tmp_project, "foo_100", "waiting on X")

    coro_module.cmd_status(tmp_project, "foo_100")
    out = capsys.readouterr().out
    assert "hold:     yes — waiting on X" in out


def test_status_legacy_user_hold_rewritten(coro_module, tmp_project, capsys):
    _seed_session(coro_module, tmp_project, "foo_100")
    _seed_turn(coro_module, tmp_project, "foo_100", 0, [
        _assistant_text_event("YIELD: USER_HOLD | need input"),
        _result_event(),
    ])

    coro_module.cmd_status(tmp_project, "foo_100")
    captured = capsys.readouterr()
    # Warning fires
    assert "legacy USER_HOLD" in captured.err
    # Yield displayed as rewritten BLOCKED with legacy marker
    assert "BLOCKED" in captured.out
    assert "legacy USER_HOLD" in captured.out


def test_status_no_yield_signal_shows_last_line_fallback(coro_module, tmp_project, capsys):
    _seed_session(coro_module, tmp_project, "foo_100")
    _seed_turn(coro_module, tmp_project, "foo_100", 0, [
        _assistant_text_event("some text but no yield"),
        _result_event(),
    ])

    coro_module.cmd_status(tmp_project, "foo_100")
    out = capsys.readouterr().out
    assert "(no YIELD signal in turn 0)" in out
    assert "some text but no yield" in out


def test_status_no_yield_empty_text_shows_placeholder(coro_module, tmp_project, capsys):
    _seed_session(coro_module, tmp_project, "foo_100")
    _seed_turn(coro_module, tmp_project, "foo_100", 0, [
        _result_event(),                                # no assistant event
    ])

    coro_module.cmd_status(tmp_project, "foo_100")
    out = capsys.readouterr().out
    assert "(no output)" in out


def test_status_token_warning_fires_above_threshold(coro_module, tmp_project, capsys, monkeypatch):
    monkeypatch.delenv("CORO_TOKEN_WARN", raising=False)
    monkeypatch.delenv("CORO_TOKEN_WARN_RATIO", raising=False)
    _seed_session(coro_module, tmp_project, "big_100", model="haiku")
    # Haiku base ctx=200k, 80% threshold = 160k. Use 180k input → warning fires.
    _seed_turn(coro_module, tmp_project, "big_100", 0, [
        _assistant_text_event("YIELD: DONE | ok"),
        _result_event(input_tokens=180_000, ctx_window=200_000),
    ])

    coro_module.cmd_status(tmp_project, "big_100")
    captured = capsys.readouterr()
    assert "used 180000 input tokens" in captured.err
    assert "% of haiku context" in captured.err


def test_status_token_warning_silent_below_threshold(coro_module, tmp_project, capsys, monkeypatch):
    monkeypatch.delenv("CORO_TOKEN_WARN", raising=False)
    monkeypatch.delenv("CORO_TOKEN_WARN_RATIO", raising=False)
    _seed_session(coro_module, tmp_project, "small_100", model="haiku")
    _seed_turn(coro_module, tmp_project, "small_100", 0, [
        _assistant_text_event("YIELD: DONE | ok"),
        _result_event(input_tokens=1000),
    ])

    coro_module.cmd_status(tmp_project, "small_100")
    captured = capsys.readouterr()
    assert "input tokens" not in captured.err


def test_status_runtime_max_output_cap_warning(coro_module, tmp_project, capsys, monkeypatch):
    """Opus's documented max is 128k; if runtime cap < 128k/2 = 64k, warn."""
    monkeypatch.delenv("CORO_TOKEN_WARN", raising=False)
    _seed_session(coro_module, tmp_project, "o_100", model="opus")
    _seed_turn(coro_module, tmp_project, "o_100", 0, [
        _assistant_text_event("YIELD: DONE | ok"),
        _result_event(model_id="claude-opus-4-7", max_output=32_000, ctx_window=1_000_000),
    ])

    coro_module.cmd_status(tmp_project, "o_100")
    captured = capsys.readouterr()
    assert "runtime max-output cap is 32000" in captured.err
    assert "claude-opus-4-7 can produce up to 128000" in captured.err


def test_status_runtime_cap_no_warning_when_near_full(coro_module, tmp_project, capsys, monkeypatch):
    monkeypatch.delenv("CORO_TOKEN_WARN", raising=False)
    _seed_session(coro_module, tmp_project, "o_100", model="opus")
    _seed_turn(coro_module, tmp_project, "o_100", 0, [
        _assistant_text_event("YIELD: DONE | ok"),
        _result_event(model_id="claude-opus-4-7", max_output=128_000, ctx_window=1_000_000),
    ])

    coro_module.cmd_status(tmp_project, "o_100")
    captured = capsys.readouterr()
    assert "runtime max-output cap" not in captured.err


def test_status_cost_warning_fires(coro_module, tmp_project, capsys, monkeypatch):
    """Haiku's default cost threshold is $10; spend >$10 to trigger warning."""
    monkeypatch.delenv("CORO_COST_WARN", raising=False)
    monkeypatch.delenv("CORO_TOKEN_WARN", raising=False)
    monkeypatch.delenv("CORO_TOKEN_WARN_RATIO", raising=False)
    _seed_session(coro_module, tmp_project, "expensive_100", model="haiku")
    # 2 turns at $6 each = $12 total, > $10 threshold
    _seed_turn(coro_module, tmp_project, "expensive_100", 0, [
        _assistant_text_event("YIELD: DONE | ok"),
        _result_event(cost=6.00),
    ])
    _seed_turn(coro_module, tmp_project, "expensive_100", 1, [
        _assistant_text_event("YIELD: DONE | ok"),
        _result_event(cost=6.00),
    ])

    coro_module.cmd_status(tmp_project, "expensive_100")
    captured = capsys.readouterr()
    assert "session cost $12.00 exceeds threshold $10.00" in captured.err


def test_status_cost_warning_respects_env_override(coro_module, tmp_project, capsys, monkeypatch):
    monkeypatch.setenv("CORO_COST_WARN", "0.005")
    monkeypatch.delenv("CORO_TOKEN_WARN", raising=False)
    monkeypatch.delenv("CORO_TOKEN_WARN_RATIO", raising=False)
    _seed_session(coro_module, tmp_project, "s_100", model="haiku")
    _seed_turn(coro_module, tmp_project, "s_100", 0, [
        _assistant_text_event("YIELD: DONE | ok"),
        _result_event(cost=0.01),
    ])

    coro_module.cmd_status(tmp_project, "s_100")
    captured = capsys.readouterr()
    assert "exceeds threshold" in captured.err


# ---------------------------------------------------------------------------
# cmd_log
# ---------------------------------------------------------------------------

def test_log_explicit_turn(coro_module, tmp_project, capsys):
    _seed_session(coro_module, tmp_project, "foo_100")
    _seed_turn(coro_module, tmp_project, "foo_100", 0, [{"type": "system", "session_id": "a"}])
    _seed_turn(coro_module, tmp_project, "foo_100", 1, [{"type": "system", "session_id": "b"}])

    coro_module.cmd_log(tmp_project, "foo_100", 1)
    out = capsys.readouterr().out
    events = [json.loads(l) for l in out.strip().split("\n")]
    assert events[0]["session_id"] == "b"


def test_log_defaults_to_last_turn(coro_module, tmp_project, capsys):
    _seed_session(coro_module, tmp_project, "foo_100")
    _seed_turn(coro_module, tmp_project, "foo_100", 0, [{"type": "system", "session_id": "first"}])
    _seed_turn(coro_module, tmp_project, "foo_100", 1, [{"type": "system", "session_id": "second"}])
    _seed_turn(coro_module, tmp_project, "foo_100", 2, [{"type": "system", "session_id": "last"}])

    coro_module.cmd_log(tmp_project, "foo_100", None)
    out = capsys.readouterr().out
    events = [json.loads(l) for l in out.strip().split("\n")]
    assert events[0]["session_id"] == "last"


def test_log_no_turns_errors(coro_module, tmp_project):
    _seed_session(coro_module, tmp_project, "foo_100")
    with pytest.raises(coro_module.CoroError, match="no turns found"):
        coro_module.cmd_log(tmp_project, "foo_100", None)


def test_log_missing_turn_errors(coro_module, tmp_project):
    _seed_session(coro_module, tmp_project, "foo_100")
    _seed_turn(coro_module, tmp_project, "foo_100", 0, [{"type": "system"}])
    with pytest.raises(coro_module.CoroError, match="no log for turn 99"):
        coro_module.cmd_log(tmp_project, "foo_100", 99)


# ---------------------------------------------------------------------------
# cmd_pop, cmd_list_sessions
# ---------------------------------------------------------------------------

def test_cmd_pop_empty_stack_errors(coro_module, tmp_project):
    with pytest.raises(coro_module.CoroError, match="CURRENT stack is empty"):
        coro_module.cmd_pop(tmp_project)


def test_cmd_list_sessions_empty_prints_placeholder(coro_module, tmp_project, capsys):
    coro_module.cmd_list_sessions(tmp_project)
    out = capsys.readouterr().out.strip()
    assert out == "(empty)"


# ---------------------------------------------------------------------------
# cmd_use
# ---------------------------------------------------------------------------

def test_cmd_use_unknown_errors(coro_module, tmp_project):
    with pytest.raises(coro_module.CoroError, match="no session matches"):
        coro_module.cmd_use(tmp_project, "ghost")


def test_cmd_use_with_slug(coro_module, tmp_project, capsys):
    _seed_session(coro_module, tmp_project, "real_100")
    coro_module.cmd_use(tmp_project, "real_100")
    captured = capsys.readouterr()
    assert "pushed real_100" in captured.err
    assert coro_module.current_top(tmp_project) == "real_100"


# ---------------------------------------------------------------------------
# cmd_unhold
# ---------------------------------------------------------------------------

def test_cmd_unhold_not_held_reports(coro_module, tmp_project, capsys):
    _seed_session(coro_module, tmp_project, "foo_100")
    rc = coro_module.cmd_unhold(_script_args(name="foo_100"), tmp_project)
    assert rc == 0
    out = capsys.readouterr().out
    assert "was not held" in out


def test_cmd_unhold_was_held_with_reason(coro_module, tmp_project, capsys):
    _seed_session(coro_module, tmp_project, "foo_100")
    coro_module.write_hold(tmp_project, "foo_100", "paused")
    coro_module.cmd_unhold(_script_args(name="foo_100"), tmp_project)
    out = capsys.readouterr().out
    assert "unheld session foo_100" in out
    assert "(was: paused)" in out


# ---------------------------------------------------------------------------
# cmd_hold
# ---------------------------------------------------------------------------

def test_cmd_hold_without_reason(coro_module, tmp_project, capsys):
    _seed_session(coro_module, tmp_project, "foo_100")
    rc = coro_module.cmd_hold(_script_args(name="foo_100", reason=[]), tmp_project)
    assert rc == 0
    out = capsys.readouterr().out
    assert out.strip() == "held session foo_100"
    is_held, reason = coro_module.read_hold(tmp_project, "foo_100")
    assert is_held and reason == ""


def test_cmd_hold_with_whitespace_reason_tokens(coro_module, tmp_project, capsys):
    _seed_session(coro_module, tmp_project, "foo_100")
    coro_module.cmd_hold(_script_args(name="foo_100", reason=["  ", "actual", ""]), tmp_project)
    is_held, reason = coro_module.read_hold(tmp_project, "foo_100")
    assert is_held and reason == "actual"


# ---------------------------------------------------------------------------
# cmd_create deprecated inline-send path
# ---------------------------------------------------------------------------

def test_create_inline_send_emits_deprecation_warning(coro_module, tmp_project, scripted_runner, monkeypatch, capsys):
    """Non-tty stdin with content triggers the deprecated inline-send path."""
    monkeypatch.setenv("CORO_MODEL", "haiku")
    monkeypatch.setenv("CORO_PROJECT", str(tmp_project))
    monkeypatch.delenv("CORO_MAX_BUDGET_USD", raising=False)

    responses = iter([
        # Turn 0: preamble
        [
            {"type": "system", "session_id": "u1"},
            _assistant_text_event("Acknowledged."),
            _result_event(cost=0.01),
        ],
        # Turn 1: inline-send payload
        [
            _assistant_text_event("Got it.\n\nYIELD: DONE | ok"),
            _result_event(cost=0.02),
        ],
    ])
    runner = scripted_runner(responder=lambda a, p: iter(next(responses)))
    _patch_runner(coro_module, monkeypatch, runner)

    # Non-tty stdin with content
    fake_in = io.StringIO("turn 1 content")
    fake_in.isatty = lambda: False
    monkeypatch.setattr("sys.stdin", fake_in)

    coro_module.cmd_create(_script_args(name="inline"), tmp_project)

    captured = capsys.readouterr()
    assert "deprecated" in captured.err
    # Both turns should be on disk
    slugs = coro_module.list_slugs(tmp_project)
    assert len(slugs) == 1
    slug = slugs[0]
    assert coro_module.turn_log_file(tmp_project, slug, 0).exists()
    assert coro_module.turn_log_file(tmp_project, slug, 1).exists()


def test_create_inline_send_empty_stdin_does_not_send(coro_module, tmp_project, scripted_runner, monkeypatch, capsys):
    """Non-tty stdin that's empty triggers only the deprecation warning, not a turn 1."""
    monkeypatch.setenv("CORO_MODEL", "haiku")
    monkeypatch.setenv("CORO_PROJECT", str(tmp_project))
    monkeypatch.delenv("CORO_MAX_BUDGET_USD", raising=False)

    runner = scripted_runner(events=[
        {"type": "system", "session_id": "u1"},
        _assistant_text_event("Acknowledged."),
        _result_event(),
    ])
    _patch_runner(coro_module, monkeypatch, runner)

    fake_in = io.StringIO("   \n  \n")
    fake_in.isatty = lambda: False
    monkeypatch.setattr("sys.stdin", fake_in)

    coro_module.cmd_create(_script_args(name="empty-inline"), tmp_project)

    captured = capsys.readouterr()
    assert "deprecated" in captured.err
    # Only turn 0 written
    slug = coro_module.list_slugs(tmp_project)[0]
    assert coro_module.turn_log_file(tmp_project, slug, 0).exists()
    assert not coro_module.turn_log_file(tmp_project, slug, 1).exists()


def test_create_uuid_mismatch_warns(coro_module, tmp_project, scripted_runner, monkeypatch, capsys):
    """If claude reports a session_id different from what we assigned, warn."""
    monkeypatch.setenv("CORO_MODEL", "haiku")
    monkeypatch.setenv("CORO_PROJECT", str(tmp_project))
    monkeypatch.delenv("CORO_MAX_BUDGET_USD", raising=False)

    runner = scripted_runner(events=[
        {"type": "system", "session_id": "different-uuid-from-what-we-set"},
        _assistant_text_event("Acknowledged."),
        _result_event(),
    ])
    _patch_runner(coro_module, monkeypatch, runner)

    fake_tty = io.StringIO()
    fake_tty.isatty = lambda: True
    monkeypatch.setattr("sys.stdin", fake_tty)

    coro_module.cmd_create(_script_args(name="mismatch"), tmp_project)

    captured = capsys.readouterr()
    assert "but we assigned" in captured.err


# ---------------------------------------------------------------------------
# read_stdin_or_die
# ---------------------------------------------------------------------------

def test_read_stdin_or_die_tty_errors(coro_module, monkeypatch):
    fake = io.StringIO()
    fake.isatty = lambda: True
    monkeypatch.setattr("sys.stdin", fake)
    with pytest.raises(coro_module.CoroError, match="stdin is a terminal"):
        coro_module.read_stdin_or_die()


def test_read_stdin_or_die_empty_errors(coro_module, monkeypatch):
    fake = io.StringIO("   \n  \n")
    fake.isatty = lambda: False
    monkeypatch.setattr("sys.stdin", fake)
    with pytest.raises(coro_module.CoroError, match="stdin is empty"):
        coro_module.read_stdin_or_die()


def test_read_stdin_or_die_happy(coro_module, monkeypatch):
    fake = io.StringIO("some content\n")
    fake.isatty = lambda: False
    monkeypatch.setattr("sys.stdin", fake)
    assert coro_module.read_stdin_or_die() == "some content"
