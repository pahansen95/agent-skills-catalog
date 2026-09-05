"""Regression tests for clear_hold semantics.

Bug: clear_hold conflated "held with no reason" and "not held" — both
returned None. This caused cmd_unhold to print "was not held" for
sessions that were actually held (without a reason), and silenced the
'note: cleared hold' output in cmd_send for the same case.

Fix: clear_hold returns "" (empty string) when the sentinel existed with
no reason, and None only when no sentinel existed.
"""
from __future__ import annotations

import argparse
import io

import pytest


def _script_args(**kw) -> argparse.Namespace:
    return argparse.Namespace(**kw)


def _patch_runner(coro_module, monkeypatch, runner):
    monkeypatch.setattr(coro_module, "_default_runner", runner)


def test_clear_hold_distinguishes_empty_reason_from_unheld(coro_module, tmp_project):
    """clear_hold returns "" when held-without-reason, None when not held."""
    coro_module.save_session(tmp_project, "foo_100", "u", "haiku")

    # Not held: None
    assert coro_module.clear_hold(tmp_project, "foo_100") is None

    # Held with empty reason: empty string (not None)
    coro_module.write_hold(tmp_project, "foo_100", "")
    result = coro_module.clear_hold(tmp_project, "foo_100")
    assert result == ""
    assert result is not None                      # the distinguishing property

    # Held with reason: the reason
    coro_module.write_hold(tmp_project, "foo_100", "because")
    assert coro_module.clear_hold(tmp_project, "foo_100") == "because"


def test_cmd_unhold_reports_unheld_for_held_no_reason(coro_module, tmp_project, capsys):
    """cmd_unhold should say 'unheld session' when held without a reason,
    not 'was not held'."""
    coro_module.save_session(tmp_project, "foo_100", "u", "haiku")
    coro_module.write_hold(tmp_project, "foo_100", "")

    coro_module.cmd_unhold(_script_args(name="foo_100"), tmp_project)
    out = capsys.readouterr().out
    assert "unheld session foo_100" in out
    assert "was not held" not in out


def test_cmd_send_auto_clear_hold_without_reason_still_notes(
    coro_module, tmp_project, scripted_runner, monkeypatch, capsys
):
    """cmd_send should emit 'cleared hold' note when the hold had no reason."""
    coro_module.save_session(tmp_project, "foo_100", "u", "haiku")
    coro_module.write_hold(tmp_project, "foo_100", "")             # empty reason

    runner = scripted_runner(events=[
        {"type": "assistant", "message": {"content": [
            {"type": "text", "text": "YIELD: DONE | ok"}
        ]}},
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "total_cost_usd": 0.01,
            "usage": {
                "input_tokens": 10, "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0, "output_tokens": 5,
            },
            "modelUsage": {"claude-haiku-4-5-20251001": {
                "contextWindow": 200_000, "maxOutputTokens": 64_000,
            }},
        },
    ])
    _patch_runner(coro_module, monkeypatch, runner)

    fake_in = io.StringIO("resume")
    fake_in.isatty = lambda: False
    monkeypatch.setattr("sys.stdin", fake_in)

    coro_module.cmd_send(tmp_project, "foo_100")
    captured = capsys.readouterr()
    assert "cleared hold on session 'foo_100'" in captured.err
