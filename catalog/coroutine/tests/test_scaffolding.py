"""Sanity checks for the test scaffolding itself."""
from __future__ import annotations

from pathlib import Path


def test_coro_module_loads(coro_module):
    """The coroutine module loads and exposes expected symbols."""
    assert hasattr(coro_module, "CoroError")
    assert hasattr(coro_module, "ProcessRunner")
    assert hasattr(coro_module, "SubprocessRunner")
    assert hasattr(coro_module, "resolve")
    assert hasattr(coro_module, "make_slug")
    assert hasattr(coro_module, "run_claude")


def test_tmp_project_fixture(tmp_project: Path):
    """tmp_project provides a .cache/coro/ scaffold."""
    assert tmp_project.exists()
    assert (tmp_project / ".cache" / "coro").is_dir()


def test_scripted_runner_records_calls(coro_module, scripted_runner):
    """ScriptedRunner captures argv, cwd, env, stdin_payload."""
    runner = scripted_runner(events=[{"type": "system", "session_id": "abc"}])
    resolved = coro_module.resolve("haiku")
    events = coro_module.run_claude(
        Path("/tmp"), "payload", resolved, session_id="abc", runner=runner
    )
    assert len(events) == 1
    assert events[0]["session_id"] == "abc"
    assert runner.last_call["stdin_payload"] == "payload"
    assert "--session-id" in runner.last_call["argv"]


def test_fake_clock_monotonic(fake_clock):
    """fake_clock advances by 1 second per call."""
    t0 = fake_clock()
    t1 = fake_clock()
    t2 = fake_clock()
    assert t1 == t0 + 1.0
    assert t2 == t0 + 2.0


def test_make_slug_with_fake_clock(coro_module, fake_clock):
    """make_slug uses the injected clock."""
    slug = coro_module.make_slug("foo", time_fn=fake_clock)
    assert slug == "foo_1700000000"


def test_die_raises_coro_error(coro_module):
    """die() raises CoroError, does not call sys.exit."""
    import pytest
    with pytest.raises(coro_module.CoroError, match="test failure"):
        coro_module.die("test failure")
