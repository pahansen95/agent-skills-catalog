"""Unit tests for build_claude_argv (pure function)."""
from __future__ import annotations

import pytest


def test_argv_minimal_create(coro_module):
    r = coro_module.resolve("haiku")
    argv = coro_module.build_claude_argv(
        r, session_id="abc-123", resume_uuid=None, max_budget_usd=None
    )
    assert argv[0] == "claude"
    assert "--print" in argv
    assert "--model" in argv
    assert "haiku" in argv
    assert "--session-id" in argv
    assert "abc-123" in argv
    assert "--resume" not in argv
    assert "--max-budget-usd" not in argv


def test_argv_resume(coro_module):
    r = coro_module.resolve("haiku")
    argv = coro_module.build_claude_argv(
        r, session_id=None, resume_uuid="uuid-456", max_budget_usd=None
    )
    assert "--resume" in argv
    assert "uuid-456" in argv
    assert "--session-id" not in argv


def test_argv_with_budget(coro_module):
    r = coro_module.resolve("haiku")
    argv = coro_module.build_claude_argv(
        r, session_id="abc", resume_uuid=None, max_budget_usd="5.00"
    )
    assert "--max-budget-usd" in argv
    assert "5.00" in argv


def test_argv_includes_effort_when_spec_has_default(coro_module):
    r = coro_module.resolve("opus")
    argv = coro_module.build_claude_argv(r, session_id="a", resume_uuid=None, max_budget_usd=None)
    assert "--effort" in argv
    assert "xhigh" in argv


def test_argv_omits_effort_for_haiku(coro_module):
    r = coro_module.resolve("haiku")
    argv = coro_module.build_claude_argv(r, session_id="a", resume_uuid=None, max_budget_usd=None)
    assert "--effort" not in argv


def test_argv_preserves_1m_suffix(coro_module):
    r = coro_module.resolve("sonnet[1m]")
    argv = coro_module.build_claude_argv(r, session_id="a", resume_uuid=None, max_budget_usd=None)
    assert "sonnet[1m]" in argv                    # verbatim pass-through


def test_argv_rejects_both_session_id_and_resume(coro_module):
    r = coro_module.resolve("haiku")
    with pytest.raises(coro_module.CoroError, match="exactly one"):
        coro_module.build_claude_argv(
            r, session_id="a", resume_uuid="b", max_budget_usd=None
        )


def test_argv_rejects_neither(coro_module):
    r = coro_module.resolve("haiku")
    with pytest.raises(coro_module.CoroError, match="exactly one"):
        coro_module.build_claude_argv(
            r, session_id=None, resume_uuid=None, max_budget_usd=None
        )


def test_argv_includes_stream_json_flags(coro_module):
    r = coro_module.resolve("haiku")
    argv = coro_module.build_claude_argv(r, session_id="a", resume_uuid=None, max_budget_usd=None)
    assert "--output-format" in argv
    idx = argv.index("--output-format")
    assert argv[idx + 1] == "stream-json"
    assert "--input-format" in argv
    assert "--verbose" in argv
    assert "--dangerously-skip-permissions" in argv


def test_argv_add_dirs_env(coro_module, monkeypatch):
    """CORO_ADD_DIRS env emits --add-dir flags."""
    monkeypatch.setenv("CORO_ADD_DIRS", "/a:/b:/c")
    r = coro_module.resolve("haiku")
    argv = coro_module.build_claude_argv(r, session_id="x", resume_uuid=None, max_budget_usd=None)
    # Each --add-dir has its path immediately after
    pairs = [(argv[i], argv[i+1]) for i, x in enumerate(argv[:-1]) if x == "--add-dir"]
    assert pairs == [("--add-dir", "/a"), ("--add-dir", "/b"), ("--add-dir", "/c")]


def test_argv_add_dirs_empty_entries_skipped(coro_module, monkeypatch):
    monkeypatch.setenv("CORO_ADD_DIRS", "/a::/b::")
    r = coro_module.resolve("haiku")
    argv = coro_module.build_claude_argv(r, session_id="x", resume_uuid=None, max_budget_usd=None)
    dirs = [argv[i+1] for i, x in enumerate(argv[:-1]) if x == "--add-dir"]
    assert dirs == ["/a", "/b"]
