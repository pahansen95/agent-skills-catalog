"""Shared pytest fixtures for the coroutine test suite.

Tests import the coroutine module directly from src/ via a sys.path insert;
this avoids packaging and keeps the source tree unchanged.
"""
from __future__ import annotations

import importlib.util
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

import pytest


_SRC = Path(__file__).parent.parent / "src" / "coroutine.py"


@pytest.fixture(scope="session")
def coro_module():
    """Load the coroutine module once per session by file path."""
    spec = importlib.util.spec_from_file_location("coroutine", _SRC)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """A freshly-initialized project root with .cache/coro/ ready."""
    (tmp_path / ".cache" / "coro").mkdir(parents=True, exist_ok=True)
    return tmp_path


class ScriptedRunner:
    """Test ProcessRunner that yields canned stream-json events.

    Captures argv, cwd, env, and stdin_payload from the last call so tests can
    assert on how the runner was invoked.

    Accepts either:
      - a static list of events (same response every call), or
      - a callable(argv, payload) -> Iterable[dict] for dynamic responses.
    """

    def __init__(
        self,
        events: Iterable[dict] | None = None,
        *,
        responder=None,
    ):
        if events is None and responder is None:
            events = []
        self._events = list(events) if events is not None else None
        self._responder = responder
        self.calls: list[dict] = []

    def run_stream_json(
        self,
        argv: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        stdin_payload: str,
    ) -> Iterator[dict]:
        self.calls.append(
            {"argv": argv, "cwd": cwd, "env": env, "stdin_payload": stdin_payload}
        )
        if self._responder is not None:
            yield from self._responder(argv, stdin_payload)
            return
        assert self._events is not None
        yield from self._events

    @property
    def last_call(self) -> dict:
        assert self.calls, "ScriptedRunner was never invoked"
        return self.calls[-1]


@pytest.fixture
def scripted_runner():
    """Factory fixture for ScriptedRunner. Call with events or responder."""
    def _make(events=None, *, responder=None) -> ScriptedRunner:
        return ScriptedRunner(events, responder=responder)
    return _make


@pytest.fixture
def fake_clock():
    """A monotonically-advancing clock for deterministic slug generation.

    Returns a callable compatible with time.time (returns float seconds).
    Start at 1_700_000_000 (Nov 2023) so slugs look realistic, and advance
    by 1 second per call.
    """
    class _Clock:
        def __init__(self, start: float = 1_700_000_000.0):
            self.t = start

        def __call__(self) -> float:
            v = self.t
            self.t += 1.0
            return v

    return _Clock()


def ok_result_event(cost_usd: float = 0.01, **extra) -> dict:
    """Build a minimal successful result event for test canned responses."""
    base = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "total_cost_usd": cost_usd,
        "usage": {
            "input_tokens": 10,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
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


def assistant_event(text: str) -> dict:
    """Build an assistant event with a single text block."""
    return {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": text}]},
    }


def system_event(session_id: str) -> dict:
    return {"type": "system", "session_id": session_id}
