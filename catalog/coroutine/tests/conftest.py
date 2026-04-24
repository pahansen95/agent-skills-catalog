"""Shared pytest fixtures for the coroutine test suite.

Tests import the coroutine module directly from src/ via a sys.path insert;
this avoids packaging and keeps the source tree unchanged.
"""
from __future__ import annotations

import argparse
import importlib.util
from collections.abc import Iterable, Iterator
from pathlib import Path

import pytest


_SRC = Path(__file__).parent.parent / "src" / "coroutine.py"

# All CORO_* and CC-related env vars that tests must start clean each run.
# Centralized here so adding a new env knob in one place cleans it up for all
# tests. Individual tests still setenv what they specifically need.
_CLEAN_ENV_VARS = (
    "CORO_MODEL",
    "CORO_EFFORT",
    "CORO_PROJECT",
    "CORO_ADD_DIRS",
    "CORO_MAX_BUDGET_USD",
    "CORO_TOKEN_WARN",
    "CORO_TOKEN_WARN_RATIO",
    "CORO_COST_WARN",
    "CLAUDE_CODE_DISABLE_1M_CONTEXT",
    "API_TIMEOUT_MS",
    "BASH_MAX_TIMEOUT_MS",
)


@pytest.fixture(autouse=True)
def _clean_coro_env(monkeypatch):
    """Autouse: scrub CORO_* and claude-env knobs before every test.

    Eliminates order-dependence from ambient developer env or test-to-test
    bleed. Tests that need a specific value call monkeypatch.setenv.
    """
    for k in _CLEAN_ENV_VARS:
        monkeypatch.delenv(k, raising=False)


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

    Captures argv, cwd, env, and stdin_payload per call so tests can assert
    on how the runner was invoked.

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
    Starts at 1_700_000_000 (Nov 2023) so slugs look realistic, and advances
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


# ---------------------------------------------------------------------------
# Event builders — importable helpers for scripted runners
# ---------------------------------------------------------------------------

def system_event(session_id: str) -> dict:
    return {"type": "system", "session_id": session_id}


def assistant_event(text: str) -> dict:
    """Assistant event with a single text block."""
    return {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": text}]},
    }


def tool_use_event(name: str, input_keys: list[str] | None = None, tool_use_id: str = "toolu_01abc") -> dict:
    """Assistant event with a single tool_use block."""
    keys = input_keys or ["pattern"]
    return {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": tool_use_id,
                    "name": name,
                    "input": {k: "x" for k in keys},
                }
            ]
        },
    }


def tool_result_event(tool_use_id: str = "toolu_01abc", content: str = "ok") -> dict:
    """User event carrying a tool_result block (claude's reply with tool output)."""
    return {
        "type": "user",
        "message": {
            "content": [
                {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}
            ]
        },
    }


def result_event(
    cost_usd: float = 0.01,
    *,
    is_error: bool = False,
    subtype: str = "success",
    input_tokens: int = 10,
    cache_read: int = 0,
    cache_creation: int = 0,
    output_tokens: int = 5,
    ctx_window: int = 200_000,
    max_output: int = 64_000,
    model_id: str = "claude-haiku-4-5-20251001",
    **extra,
) -> dict:
    """Minimal result event; defaults to success."""
    base = {
        "type": "result",
        "subtype": subtype,
        "is_error": is_error,
        "total_cost_usd": cost_usd,
        "usage": {
            "input_tokens": input_tokens,
            "cache_read_input_tokens": cache_read,
            "cache_creation_input_tokens": cache_creation,
            "output_tokens": output_tokens,
        },
        "modelUsage": {
            model_id: {"contextWindow": ctx_window, "maxOutputTokens": max_output}
        },
    }
    base.update(extra)
    return base


def budget_error_event(cost_usd: float = 0.05) -> dict:
    """Result event signalling budget overrun."""
    return {
        "type": "result",
        "subtype": "error_max_budget_usd",
        "is_error": True,
        "total_cost_usd": cost_usd,
        "usage": {},
        "modelUsage": {},
    }


# ---------------------------------------------------------------------------
# Small test helpers (formerly duplicated across multiple test files)
# ---------------------------------------------------------------------------

def script_args(**kw) -> argparse.Namespace:
    """Build an argparse.Namespace for cmd_* functions that take `args`."""
    return argparse.Namespace(**kw)


def patch_runner(coro_module, monkeypatch, runner):
    """Replace the module-level default ProcessRunner with `runner`."""
    monkeypatch.setattr(coro_module, "_default_runner", runner)
