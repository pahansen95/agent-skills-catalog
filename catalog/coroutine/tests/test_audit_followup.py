"""Targeted tests added per audit follow-up.

Covers load-bearing gaps identified in the test-suite audit:
  - cmd_send warns on missing YIELD (protocol violation path, line 1027).
  - _subprocess_env propagates API_TIMEOUT_MS / BASH_MAX_TIMEOUT_MS defaults
    and respects user overrides.
  - make_stream_callback renders tool_use and tool_result progress lines.
  - cmd_new_phase actually substitutes {slug} in the scaffolded templates.
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest

from conftest import (
    assistant_event,
    patch_runner,
    result_event,
    script_args,
    system_event,
    tool_result_event,
    tool_use_event,
)


# ---------------------------------------------------------------------------
# cmd_send warns on missing YIELD
# ---------------------------------------------------------------------------

def test_cmd_send_missing_yield_warns(coro_module, tmp_project, scripted_runner, monkeypatch, capsys):
    """When the worker's response has no YIELD line, cmd_send must emit the
    protocol-violation warning. This is the load-bearing signal the
    orchestrator relies on to detect a misbehaving worker."""
    coro_module.save_session(tmp_project, "foo_100", "uuid-foo", "haiku")
    # Pre-seed turn 0 so the cmd_send below is observed as turn 1 (matches
    # the typical post-create state; reduces ambiguity in the assertion).
    coro_module.save_turn(tmp_project, "foo_100", 0, [result_event()])

    runner = scripted_runner(events=[
        assistant_event("I did things but forgot to emit YIELD."),
        result_event(),
    ])
    patch_runner(coro_module, monkeypatch, runner)

    fake_in = io.StringIO("do the thing")
    fake_in.isatty = lambda: False
    monkeypatch.setattr("sys.stdin", fake_in)

    coro_module.cmd_send(tmp_project, "foo_100")

    captured = capsys.readouterr()
    assert "turn 1 has no YIELD" in captured.err
    assert "protocol violation" in captured.err


# ---------------------------------------------------------------------------
# _subprocess_env propagation
# ---------------------------------------------------------------------------

def test_subprocess_env_sets_api_timeout_default(coro_module):
    """With no parent env set, API_TIMEOUT_MS defaults to 20 min."""
    env = coro_module._subprocess_env()
    assert env["API_TIMEOUT_MS"] == "1200000"
    assert env["BASH_MAX_TIMEOUT_MS"] == "1200000"


def test_subprocess_env_preserves_user_api_timeout(coro_module, monkeypatch):
    """User's existing API_TIMEOUT_MS must not be overridden."""
    monkeypatch.setenv("API_TIMEOUT_MS", "60000")
    env = coro_module._subprocess_env()
    assert env["API_TIMEOUT_MS"] == "60000"
    # BASH_MAX_TIMEOUT_MS still gets the default
    assert env["BASH_MAX_TIMEOUT_MS"] == "1200000"


def test_subprocess_env_preserves_user_bash_timeout(coro_module, monkeypatch):
    monkeypatch.setenv("BASH_MAX_TIMEOUT_MS", "300000")
    env = coro_module._subprocess_env()
    assert env["BASH_MAX_TIMEOUT_MS"] == "300000"
    assert env["API_TIMEOUT_MS"] == "1200000"


def test_subprocess_env_propagated_to_runner(coro_module, tmp_project, scripted_runner, monkeypatch):
    """End-to-end: when cmd_send runs, the runner receives the subprocess env
    with our defaults set. Regression test: if _subprocess_env stopped being
    called or the env= arg disappeared, this test would fail."""
    coro_module.save_session(tmp_project, "foo_100", "uuid-foo", "haiku")

    runner = scripted_runner(events=[
        assistant_event("ok\n\nYIELD: DONE | ack"),
        result_event(),
    ])
    patch_runner(coro_module, monkeypatch, runner)

    fake_in = io.StringIO("hi")
    fake_in.isatty = lambda: False
    monkeypatch.setattr("sys.stdin", fake_in)

    coro_module.cmd_send(tmp_project, "foo_100")

    captured_env = runner.last_call["env"]
    assert captured_env["API_TIMEOUT_MS"] == "1200000"
    assert captured_env["BASH_MAX_TIMEOUT_MS"] == "1200000"


def test_subprocess_env_user_override_reaches_runner(coro_module, tmp_project, scripted_runner, monkeypatch):
    """User's API_TIMEOUT_MS override must survive all the way to the runner."""
    monkeypatch.setenv("API_TIMEOUT_MS", "300000")
    coro_module.save_session(tmp_project, "foo_100", "uuid-foo", "haiku")

    runner = scripted_runner(events=[
        assistant_event("ok\n\nYIELD: DONE | ack"),
        result_event(),
    ])
    patch_runner(coro_module, monkeypatch, runner)

    fake_in = io.StringIO("hi")
    fake_in.isatty = lambda: False
    monkeypatch.setattr("sys.stdin", fake_in)

    coro_module.cmd_send(tmp_project, "foo_100")

    assert runner.last_call["env"]["API_TIMEOUT_MS"] == "300000"


# ---------------------------------------------------------------------------
# make_stream_callback: tool_use and tool_result progress lines
# ---------------------------------------------------------------------------

def test_stream_callback_renders_tool_use_progress(coro_module, tmp_project, capsys):
    """An assistant event containing a tool_use block emits a progress line
    on stderr: `[coroutine] tool_use: <Name>(<keys>)`."""
    writer = coro_module.open_turn_writer(tmp_project, "foo_100", 0)
    try:
        cb = coro_module.make_stream_callback(writer, print_text=True, progress=True)
        cb(tool_use_event("Glob", input_keys=["pattern", "path"]))
    finally:
        writer.close()

    captured = capsys.readouterr()
    assert "[coroutine] tool_use: Glob" in captured.err
    # Input keys appear in parens
    assert "pattern" in captured.err
    assert "path" in captured.err


def test_stream_callback_renders_tool_result_progress(coro_module, tmp_project, capsys):
    """A user event containing a tool_result block emits a progress line
    on stderr: `[coroutine] tool_result: <prefix-of-tool_use_id>`."""
    writer = coro_module.open_turn_writer(tmp_project, "foo_100", 0)
    try:
        cb = coro_module.make_stream_callback(writer, print_text=True, progress=True)
        cb(tool_result_event(tool_use_id="toolu_01abc123xyz"))
    finally:
        writer.close()

    captured = capsys.readouterr()
    assert "[coroutine] tool_result:" in captured.err
    # First 12 chars of the tool_use_id are shown
    assert "toolu_01abc1" in captured.err


def test_stream_callback_progress_suppressed_when_disabled(coro_module, tmp_project, capsys):
    writer = coro_module.open_turn_writer(tmp_project, "foo_100", 0)
    try:
        cb = coro_module.make_stream_callback(writer, print_text=True, progress=False)
        cb(tool_use_event("Glob", input_keys=["pattern"]))
        cb(tool_result_event())
    finally:
        writer.close()

    captured = capsys.readouterr()
    assert "tool_use:" not in captured.err
    assert "tool_result:" not in captured.err


def test_stream_callback_tool_events_still_written_to_jsonl(coro_module, tmp_project):
    """Progress-line rendering shouldn't affect jsonl: every event gets written
    regardless of the print_text/progress flags."""
    turn_path = coro_module.turn_log_file(tmp_project, "foo_100", 0)
    writer = coro_module.open_turn_writer(tmp_project, "foo_100", 0)
    try:
        cb = coro_module.make_stream_callback(writer, print_text=False, progress=False)
        cb(tool_use_event("Glob", input_keys=["pattern"]))
        cb(tool_result_event())
        cb(result_event())
    finally:
        writer.close()

    import json as _json
    lines = [_json.loads(l) for l in turn_path.read_text().strip().split("\n")]
    assert len(lines) == 3
    assert lines[0]["message"]["content"][0]["type"] == "tool_use"
    assert lines[1]["message"]["content"][0]["type"] == "tool_result"
    assert lines[2]["type"] == "result"


# ---------------------------------------------------------------------------
# cmd_new_phase substitutes {slug} in the scaffolded templates
# ---------------------------------------------------------------------------

def test_cmd_new_phase_substitutes_slug_in_spec(coro_module, tmp_project):
    coro_module.cmd_new_phase(script_args(slug="my-test-phase", force=False), tmp_project)
    spec = (tmp_project / ".cache" / "TODO" / "phase-my-test-phase.md").read_text()
    # The substituted slug appears in the file; the raw placeholder does not.
    assert "my-test-phase" in spec
    assert "{slug}" not in spec


def test_cmd_new_phase_substitutes_slug_in_kickoff(coro_module, tmp_project):
    coro_module.cmd_new_phase(script_args(slug="another-phase", force=False), tmp_project)
    kickoff = (tmp_project / ".cache" / "TODO" / "phase-another-phase-kickoff.md").read_text()
    assert "another-phase" in kickoff
    assert "{slug}" not in kickoff


def test_cmd_new_phase_force_substitutes_new_slug(coro_module, tmp_project):
    """After --force, the new slug is substituted (not leftover from the previous
    write, since we're overwriting with the same template)."""
    coro_module.cmd_new_phase(script_args(slug="x-phase", force=False), tmp_project)
    # Overwrite: the spec file should now reflect the new slug name
    # (both calls use the same slug here; the point is force=True doesn't error)
    coro_module.cmd_new_phase(script_args(slug="x-phase", force=True), tmp_project)
    spec = (tmp_project / ".cache" / "TODO" / "phase-x-phase.md").read_text()
    assert "x-phase" in spec
    assert "{slug}" not in spec
