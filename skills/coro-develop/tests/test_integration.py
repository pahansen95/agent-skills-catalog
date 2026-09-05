"""Integration tests: end-to-end command flows with ScriptedRunner.

Each test drives cmd_* functions directly (not the CLI entry point), using
a temporary project root and a scripted process runner that returns canned
stream-json events. No real claude invocation.
"""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

import pytest


# Helpers shared across tests ------------------------------------------------

def _script_args(**kwargs) -> argparse.Namespace:
    """Build a minimal argparse.Namespace matching cmd_* signatures."""
    return argparse.Namespace(**kwargs)


def _ok_result(cost: float = 0.01, **extra) -> dict:
    base = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "total_cost_usd": cost,
        "usage": {
            "input_tokens": 10,
            "cache_read_input_tokens": 100,
            "cache_creation_input_tokens": 50,
            "output_tokens": 5,
        },
        "modelUsage": {
            "claude-haiku-4-5-20251001": {
                "contextWindow": 200_000,
                "maxOutputTokens": 64_000,
            }
        },
    }
    base.update(extra)
    return base


def _budget_error_result(cost: float = 0.05) -> dict:
    return {
        "type": "result",
        "subtype": "error_max_budget_usd",
        "is_error": True,
        "total_cost_usd": cost,
        "usage": {},
        "modelUsage": {},
    }


def _scripted_session_create(session_id: str, cost: float = 0.02) -> list[dict]:
    """Canned events for a successful create turn."""
    return [
        {"type": "system", "session_id": session_id},
        {
            "type": "assistant",
            "message": {
                "content": [{"type": "text", "text": "Acknowledged. Awaiting first instruction."}]
            },
        },
        _ok_result(cost=cost),
    ]


def _scripted_send_response(text: str, yield_signal: str, cost: float = 0.01) -> list[dict]:
    """Canned events for a send turn that produces visible text + YIELD."""
    return [
        {
            "type": "assistant",
            "message": {
                "content": [{"type": "text", "text": f"{text}\n\n{yield_signal}"}]
            },
        },
        _ok_result(cost=cost),
    ]


def _patch_runner_and_stdin(coro_module, monkeypatch, runner, stdin_content: str = ""):
    """Swap the module default runner and set up a non-tty stdin."""
    monkeypatch.setattr(coro_module, "_default_runner", runner)
    fake_stdin = io.StringIO(stdin_content)
    fake_stdin.isatty = lambda: False
    monkeypatch.setattr("sys.stdin", fake_stdin)


def _patch_runner(coro_module, monkeypatch, runner):
    monkeypatch.setattr(coro_module, "_default_runner", runner)


# ---------------------------------------------------------------------------
# Full lifecycle: create → send → status → turns
# ---------------------------------------------------------------------------

def test_full_lifecycle(coro_module, tmp_project, scripted_runner, monkeypatch, capsys):
    monkeypatch.setenv("CORO_MODEL", "haiku")
    monkeypatch.setenv("CORO_PROJECT", str(tmp_project))
    monkeypatch.delenv("CORO_MAX_BUDGET_USD", raising=False)

    # Per-turn response queue
    responses = iter([
        _scripted_session_create("uuid-fake-create"),
        _scripted_send_response("Hello world.", "YIELD: DONE | greeted", cost=0.02),
    ])

    def responder(argv, payload):
        return iter(next(responses))

    runner = scripted_runner(responder=responder)

    # --- CREATE ---
    # Fake a tty stdin so cmd_create doesn't try the deprecated inline path
    fake_tty = io.StringIO()
    fake_tty.isatty = lambda: True
    monkeypatch.setattr("sys.stdin", fake_tty)
    _patch_runner(coro_module, monkeypatch, runner)

    # Force deterministic slug via time_fn would require modifying cmd_create,
    # but we only need ONE session here so wall-clock is fine.
    coro_module.cmd_create(_script_args(name="demo"), tmp_project)

    # Slug should be captured from stdout
    captured = capsys.readouterr()
    slug_lines = [l for l in captured.out.splitlines() if l.startswith("demo_")]
    assert len(slug_lines) == 1
    slug = slug_lines[0]

    # Runner was invoked with --session-id <the-uuid-we-persisted>, NOT --resume
    create_argv = runner.calls[0]["argv"]
    assert "--session-id" in create_argv
    assert "--resume" not in create_argv
    persisted_uuid = coro_module.load_session(tmp_project, slug)
    assert create_argv[create_argv.index("--session-id") + 1] == persisted_uuid

    # CURRENT stack has the slug on top
    assert coro_module.current_top(tmp_project) == slug

    # Session files exist
    assert coro_module.session_file(tmp_project, slug).exists()
    assert coro_module.meta_file(tmp_project, slug).exists()
    assert coro_module.turn_log_file(tmp_project, slug, 0).exists()

    # --- SEND ---
    fake_in = io.StringIO("please say hello")
    fake_in.isatty = lambda: False
    monkeypatch.setattr("sys.stdin", fake_in)

    coro_module.cmd_send(tmp_project, slug)

    captured = capsys.readouterr()
    assert "Hello world." in captured.out                # assistant text streamed to stdout
    assert "YIELD: DONE | greeted" in captured.err       # yield surfaced to stderr
    assert coro_module.turn_log_file(tmp_project, slug, 1).exists()

    # Send invoked with --resume <same-uuid>, NOT --session-id. A regression to
    # create-semantics (--session-id) would spawn a fresh claude session every
    # send and silently lose conversation history.
    send_argv = runner.calls[1]["argv"]
    assert "--resume" in send_argv
    assert "--session-id" not in send_argv
    assert send_argv[send_argv.index("--resume") + 1] == persisted_uuid
    assert send_argv[send_argv.index("--resume") + 1] == coro_module.load_session(tmp_project, slug)

    # --- STATUS ---
    coro_module.cmd_status(tmp_project, slug)
    out = capsys.readouterr().out
    assert f"session:  {slug}" in out
    assert "model:    haiku" in out
    assert "hold:     no" in out
    assert "YIELD: DONE | greeted" in out

    # --- TURNS ---
    coro_module.cmd_turns(tmp_project, slug)
    out = capsys.readouterr().out
    assert f"session: {slug}" in out
    assert "turn 000" in out
    assert "turn 001" in out
    assert "YIELD: DONE | greeted" in out


# ---------------------------------------------------------------------------
# Budget overrun in send: soft-fail, session survives
# ---------------------------------------------------------------------------

def test_budget_overrun_in_send_soft_fails(coro_module, tmp_project, scripted_runner, monkeypatch, capsys):
    monkeypatch.setenv("CORO_MODEL", "haiku")
    monkeypatch.setenv("CORO_PROJECT", str(tmp_project))
    monkeypatch.setenv("CORO_MAX_BUDGET_USD", "0.01")

    responses = iter([
        _scripted_session_create("uuid-fake"),
        [
            {
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "partial content...\n\nYIELD: DONE | done"}]},
            },
            _budget_error_result(cost=0.05),
        ],
    ])
    runner = scripted_runner(responder=lambda a, p: iter(next(responses)))

    # Create
    fake_tty = io.StringIO()
    fake_tty.isatty = lambda: True
    monkeypatch.setattr("sys.stdin", fake_tty)
    _patch_runner(coro_module, monkeypatch, runner)
    coro_module.cmd_create(_script_args(name="budgeted"), tmp_project)
    slug = capsys.readouterr().out.strip().splitlines()[-1]

    # Send (should soft-fail, not raise)
    fake_in = io.StringIO("do stuff")
    fake_in.isatty = lambda: False
    monkeypatch.setattr("sys.stdin", fake_in)
    coro_module.cmd_send(tmp_project, slug)

    captured = capsys.readouterr()
    # Budget warning emitted
    assert "exceeded CORO_MAX_BUDGET_USD" in captured.err
    # Session files still intact — session remains usable
    assert coro_module.session_file(tmp_project, slug).exists()
    assert coro_module.turn_log_file(tmp_project, slug, 1).exists()

    # Status surfaces the budget row
    coro_module.cmd_status(tmp_project, slug)
    status_out = capsys.readouterr().out
    assert "budget:" in status_out
    assert "EXCEEDED" in status_out


# ---------------------------------------------------------------------------
# Budget overrun in create: hard-fail, session files removed, turn log kept
# ---------------------------------------------------------------------------

def test_budget_overrun_in_create_hard_fails(coro_module, tmp_project, scripted_runner, monkeypatch, capsys):
    monkeypatch.setenv("CORO_MODEL", "haiku")
    monkeypatch.setenv("CORO_PROJECT", str(tmp_project))
    monkeypatch.setenv("CORO_MAX_BUDGET_USD", "0.001")

    runner = scripted_runner(
        events=[
            {"type": "system", "session_id": "uuid"},
            _budget_error_result(cost=0.02),
        ]
    )

    fake_tty = io.StringIO()
    fake_tty.isatty = lambda: True
    monkeypatch.setattr("sys.stdin", fake_tty)
    _patch_runner(coro_module, monkeypatch, runner)

    with pytest.raises(coro_module.CoroError, match="budget .* exceeded"):
        coro_module.cmd_create(_script_args(name="doomed"), tmp_project)

    # Session files cleaned up
    slugs_on_disk = coro_module.list_slugs(tmp_project)
    assert slugs_on_disk == []

    # Turn log preserved for post-mortem — find the doomed_* dir
    coro_root = tmp_project / ".cache" / "coro"
    doomed_dirs = [d for d in coro_root.iterdir() if d.is_dir() and d.name.startswith("doomed_")]
    assert len(doomed_dirs) == 1
    assert (doomed_dirs[0] / "turns" / "000.jsonl").exists()


# ---------------------------------------------------------------------------
# Shorthand ambiguity: cmd_send fails fast
# ---------------------------------------------------------------------------

def test_shorthand_ambiguity_fails_fast(coro_module, tmp_project, scripted_runner, monkeypatch, capsys):
    # Two sessions with the same name
    coro_module.save_session(tmp_project, "phase-1_100", "u1", "haiku")
    coro_module.save_session(tmp_project, "phase-1_200", "u2", "haiku")

    fake_in = io.StringIO("hi")
    fake_in.isatty = lambda: False
    monkeypatch.setattr("sys.stdin", fake_in)
    _patch_runner(coro_module, monkeypatch, scripted_runner(events=[]))

    with pytest.raises(coro_module.CoroError, match="ambiguous"):
        coro_module.cmd_send(tmp_project, "phase-1")


# ---------------------------------------------------------------------------
# Dead session from is_error result: cleanup
# ---------------------------------------------------------------------------

def test_bogus_model_cleanup(coro_module, tmp_project, scripted_runner, monkeypatch):
    """When the result event signals is_error (e.g. invalid model), cmd_create
    deletes the session files."""
    monkeypatch.setenv("CORO_MODEL", "claude-bogus-99-99")
    monkeypatch.setenv("CORO_PROJECT", str(tmp_project))
    monkeypatch.delenv("CORO_MAX_BUDGET_USD", raising=False)

    runner = scripted_runner(
        events=[
            {"type": "system", "session_id": "uuid"},
            {
                "type": "result",
                "subtype": "success",
                "is_error": True,
                "result": "There's an issue with the selected model (claude-bogus-99-99).",
                "total_cost_usd": 0,
            },
        ]
    )

    fake_tty = io.StringIO()
    fake_tty.isatty = lambda: True
    monkeypatch.setattr("sys.stdin", fake_tty)
    _patch_runner(coro_module, monkeypatch, runner)

    with pytest.raises(coro_module.CoroError, match="session creation failed"):
        coro_module.cmd_create(_script_args(name="bogus"), tmp_project)

    # Session uuid/meta files removed — list_slugs skips incomplete dirs
    assert coro_module.list_slugs(tmp_project) == []


# ---------------------------------------------------------------------------
# Slug-shaped name rejection
# ---------------------------------------------------------------------------

def test_create_rejects_slug_shaped_name(coro_module, tmp_project, monkeypatch):
    monkeypatch.setenv("CORO_PROJECT", str(tmp_project))
    fake_tty = io.StringIO()
    fake_tty.isatty = lambda: True
    monkeypatch.setattr("sys.stdin", fake_tty)

    with pytest.raises(coro_module.CoroError, match="slug-shaped"):
        coro_module.cmd_create(_script_args(name="trap_1234567890"), tmp_project)


# ---------------------------------------------------------------------------
# Progressive jsonl writes: turn log grows during the run
# ---------------------------------------------------------------------------

def test_progressive_jsonl_writes(coro_module, tmp_project, scripted_runner, monkeypatch):
    """As each event is yielded by the runner, it should be written to the
    turn jsonl file immediately (not batched at end)."""
    monkeypatch.setenv("CORO_MODEL", "haiku")
    monkeypatch.setenv("CORO_PROJECT", str(tmp_project))
    monkeypatch.delenv("CORO_MAX_BUDGET_USD", raising=False)

    fake_tty = io.StringIO()
    fake_tty.isatty = lambda: True
    monkeypatch.setattr("sys.stdin", fake_tty)

    # Inspect the jsonl during streaming by having the responder check disk
    # state between yields
    observed_sizes = []

    def responder(argv, payload):
        events = _scripted_session_create("uuid-prog")
        for e in events:
            yield e
            # After each yield, check how many lines are on disk
            # (can't know slug yet, so scan the coro dir)
            coro_root = tmp_project / ".cache" / "coro"
            if coro_root.exists():
                jsonls = list(coro_root.rglob("*.jsonl"))
                if jsonls:
                    lines = jsonls[0].read_text().strip().split("\n") if jsonls[0].read_text().strip() else []
                    observed_sizes.append(len(lines))

    runner = scripted_runner(responder=responder)
    _patch_runner(coro_module, monkeypatch, runner)

    coro_module.cmd_create(_script_args(name="progressive"), tmp_project)

    # Observed sizes should be monotonically non-decreasing
    assert observed_sizes == sorted(observed_sizes)
    # And should include intermediate values, not just the final count
    assert len(set(observed_sizes)) > 1


# ---------------------------------------------------------------------------
# Hold / send auto-clears hold
# ---------------------------------------------------------------------------

def test_hold_then_send_auto_clears(coro_module, tmp_project, scripted_runner, monkeypatch, capsys):
    coro_module.save_session(tmp_project, "foo_100", "uuid", "haiku")
    coro_module.current_push(tmp_project, "foo_100")

    # Hold the session
    coro_module.cmd_hold(_script_args(name="foo", reason=["needs", "decision"]), tmp_project)
    assert coro_module.read_hold(tmp_project, "foo_100") == (True, "needs decision")

    # Now send — should auto-clear
    fake_in = io.StringIO("resume")
    fake_in.isatty = lambda: False
    monkeypatch.setattr("sys.stdin", fake_in)
    runner = scripted_runner(events=_scripted_send_response("resumed", "YIELD: DONE | ok"))
    _patch_runner(coro_module, monkeypatch, runner)

    coro_module.cmd_send(tmp_project, "foo")

    captured = capsys.readouterr()
    assert "cleared hold" in captured.err
    assert coro_module.read_hold(tmp_project, "foo_100") == (False, "")


# ---------------------------------------------------------------------------
# Concurrent send: second send dies immediately via fcntl
# ---------------------------------------------------------------------------

def test_concurrent_send_blocks_second(coro_module, tmp_project, scripted_runner, monkeypatch):
    """If a send lock is held, a second acquire attempt dies immediately."""
    coro_module.save_session(tmp_project, "foo_100", "uuid", "haiku")

    # Manually acquire the lock (simulating an in-flight send from another process)
    fh = coro_module.acquire_send_lock(tmp_project, "foo_100")
    try:
        fake_in = io.StringIO("msg")
        fake_in.isatty = lambda: False
        monkeypatch.setattr("sys.stdin", fake_in)
        _patch_runner(coro_module, monkeypatch, scripted_runner(events=[]))

        with pytest.raises(coro_module.CoroError, match="another send"):
            coro_module.cmd_send(tmp_project, "foo_100")
    finally:
        fh.close()


# ---------------------------------------------------------------------------
# cmd_list shows slugs
# ---------------------------------------------------------------------------

def test_cmd_list_shows_stack(coro_module, tmp_project, capsys):
    coro_module.save_session(tmp_project, "a_100", "u1", "haiku")
    coro_module.save_session(tmp_project, "b_200", "u2", "haiku")
    coro_module.current_push(tmp_project, "a_100")
    coro_module.current_push(tmp_project, "b_200")

    coro_module.cmd_list_sessions(tmp_project)
    out = capsys.readouterr().out.strip().splitlines()
    # list prints top-to-bottom (reversed stack): b first, a second
    assert out == ["b_200", "a_100"]


# ---------------------------------------------------------------------------
# cmd_new_phase scaffolds files
# ---------------------------------------------------------------------------

def test_cmd_new_phase_creates_files(coro_module, tmp_project):
    coro_module.cmd_new_phase(_script_args(slug="my-phase", force=False), tmp_project)
    todo = tmp_project / ".cache" / "TODO"
    assert (todo / "phase-my-phase.md").exists()
    assert (todo / "phase-my-phase-kickoff.md").exists()


def test_cmd_new_phase_refuses_overwrite(coro_module, tmp_project):
    coro_module.cmd_new_phase(_script_args(slug="x", force=False), tmp_project)
    with pytest.raises(coro_module.CoroError, match="already exist"):
        coro_module.cmd_new_phase(_script_args(slug="x", force=False), tmp_project)


def test_cmd_new_phase_force_overwrites(coro_module, tmp_project):
    coro_module.cmd_new_phase(_script_args(slug="x", force=False), tmp_project)
    # Should not raise
    coro_module.cmd_new_phase(_script_args(slug="x", force=True), tmp_project)
