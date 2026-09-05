"""Misc edge-case tests: callback exceptions, inline-send missing-yield, and
other defensive paths worth explicit coverage."""
from __future__ import annotations

import argparse
import io

import pytest


def _script_args(**kw) -> argparse.Namespace:
    return argparse.Namespace(**kw)


def _patch_runner(coro_module, monkeypatch, runner):
    monkeypatch.setattr(coro_module, "_default_runner", runner)


# ---------------------------------------------------------------------------
# run_claude: on_event callback raising an exception does not break the stream
# ---------------------------------------------------------------------------

def test_on_event_exception_recovers_and_continues(coro_module, scripted_runner, capsys):
    """If on_event raises, the stream loop should warn and keep consuming."""
    from pathlib import Path

    events = [
        {"type": "system", "session_id": "a"},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "hi"}]}},
        {"type": "result", "total_cost_usd": 0.01},
    ]
    runner = scripted_runner(events=events)

    call_count = [0]
    def bad_cb(e):
        call_count[0] += 1
        if call_count[0] == 2:                     # raise on the middle event
            raise RuntimeError("boom")

    resolved = coro_module.resolve("haiku")
    collected = coro_module.run_claude(
        Path("/tmp"), "payload", resolved,
        session_id="abc", on_event=bad_cb, runner=runner,
    )

    # All events still returned despite the callback exception
    assert len(collected) == 3
    # Warning fired on stderr
    captured = capsys.readouterr()
    assert "on_event callback raised" in captured.err
    assert "boom" in captured.err


# ---------------------------------------------------------------------------
# cmd_create: inline-send path that ends without a YIELD line
# ---------------------------------------------------------------------------

def test_create_inline_send_missing_yield_warns(coro_module, tmp_project, scripted_runner, monkeypatch, capsys):
    """Inline-send path where the worker forgets to emit YIELD on turn 1.

    The deprecated path should still call warn_missing_yield for the turn.
    """
    monkeypatch.setenv("CORO_MODEL", "haiku")
    monkeypatch.setenv("CORO_PROJECT", str(tmp_project))
    monkeypatch.delenv("CORO_MAX_BUDGET_USD", raising=False)

    responses = iter([
        # Turn 0: preamble
        [
            {"type": "system", "session_id": "u1"},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "Ack."}]}},
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "total_cost_usd": 0.01,
                "usage": {"input_tokens": 10, "cache_read_input_tokens": 0,
                          "cache_creation_input_tokens": 0, "output_tokens": 5},
                "modelUsage": {"claude-haiku-4-5-20251001": {
                    "contextWindow": 200_000, "maxOutputTokens": 64_000}},
            },
        ],
        # Turn 1: NO YIELD in text
        [
            {"type": "assistant", "message": {"content": [
                {"type": "text", "text": "I did things but forgot to emit YIELD."}
            ]}},
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "total_cost_usd": 0.01,
                "usage": {"input_tokens": 10, "cache_read_input_tokens": 0,
                          "cache_creation_input_tokens": 0, "output_tokens": 5},
                "modelUsage": {"claude-haiku-4-5-20251001": {
                    "contextWindow": 200_000, "maxOutputTokens": 64_000}},
            },
        ],
    ])
    runner = scripted_runner(responder=lambda a, p: iter(next(responses)))
    _patch_runner(coro_module, monkeypatch, runner)

    fake_in = io.StringIO("turn 1 content")
    fake_in.isatty = lambda: False
    monkeypatch.setattr("sys.stdin", fake_in)

    coro_module.cmd_create(_script_args(name="missyield"), tmp_project)

    captured = capsys.readouterr()
    # Deprecation warning
    assert "deprecated" in captured.err
    # Missing-YIELD warning for turn 1
    assert "turn 1 has no YIELD" in captured.err


# ---------------------------------------------------------------------------
# cmd_turns: no turns found
# ---------------------------------------------------------------------------

def test_cmd_turns_no_turns_errors(coro_module, tmp_project):
    coro_module.save_session(tmp_project, "foo_100", "u", "haiku")
    with pytest.raises(coro_module.CoroError, match="no turns found"):
        coro_module.cmd_turns(tmp_project, "foo_100")


# ---------------------------------------------------------------------------
# cmd_pop prints the popped slug to stdout (not stderr)
# ---------------------------------------------------------------------------

def test_cmd_pop_prints_slug_to_stdout(coro_module, tmp_project, capsys):
    coro_module.save_session(tmp_project, "a_100", "u", "haiku")
    coro_module.current_push(tmp_project, "a_100")
    coro_module.cmd_pop(tmp_project)
    captured = capsys.readouterr()
    assert captured.out.strip() == "a_100"


