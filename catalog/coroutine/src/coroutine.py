#!/usr/bin/env python3
"""
coroutine — stateful Claude session manager

Usage:
  coroutine create <name>            # create session; prints generated slug to stdout
  coroutine send [<name-or-slug>]    # reads prompt from stdin (bare = CURRENT top)
  coroutine status [<name-or-slug>]  # last YIELD signal
  coroutine turns [<name-or-slug>]   # list turns with cost summary
  coroutine log [<name-or-slug>] [<N>]  # raw jsonl for turn N (default: last)
  coroutine new-phase <phase-slug>   # scaffold .cache/TODO/phase-<phase-slug>.md + kickoff

Session arguments accept either a slug (e.g. phase-1_1745123456) or a
shorthand name (e.g. phase-1). Names resolve to a slug at command time;
ambiguous names fail fast. See protocol.md §Name resolution.

Environment:
  CORO_MODEL      Claude model: alias (opus|sonnet|haiku|best), canonical id
                  (claude-opus-4-7), or either with [1m] suffix. Unknown slugs
                  pass through with a warning. Default: sonnet.
  CORO_EFFORT     Effort level (low|medium|high|xhigh|max). If unset, the
                  model's spec default is used (never ambient env).
  CORO_PROJECT    Project root path (default: auto-discover from cwd)
  CORO_ADD_DIRS   Colon-separated list of extra --add-dir paths for claude
  CORO_MAX_BUDGET_USD    Per-turn budget cap in USD. When exceeded: soft-fail
                         in send, hard-fail in create. Unset = no cap.
  CORO_TOKEN_WARN_RATIO  Ratio of context window to trigger token warning (default 0.80)
  CORO_TOKEN_WARN        Absolute token count override (takes precedence over ratio)
  CORO_COST_WARN         Session cost warning threshold in USD (overrides per-model default)

Subprocess env (set when unset in parent env):
  API_TIMEOUT_MS = 1200000      (20 min) — long phase turns
  BASH_MAX_TIMEOUT_MS = 1200000 (20 min) — long builds/tests in worker

Sessions stored in: <project>/.cache/coro/<slug>/
Turn logs stored in: <project>/.cache/coro/<slug>/turns/
Slug format:        <name>_<unix-seconds> (generated at `coro create`)
"""

import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import IO, Protocol


# ---------------------------------------------------------------------------
# Errors & process-runner seam
#
# CoroError: raised by logic functions to signal an operator-facing failure.
# CLI entry point catches it and exits 1. Keeps die()-style semantics out of
# testable code paths.
#
# ProcessRunner: the seam for subprocess invocation. Prod impl wraps Popen;
# tests inject a scripted runner that yields canned stream-json events.
# ---------------------------------------------------------------------------


class CoroError(Exception):
    """Operator-facing failure. CLI prints msg to stderr and exits 1."""


class ProcessRunner(Protocol):
    """Protocol for spawning `claude` and iterating its stream-json output."""

    def run_stream_json(
        self,
        argv: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        stdin_payload: str,
    ) -> Iterator[dict]:
        """Spawn argv, write stdin_payload, yield parsed JSON events as they arrive.

        Implementations control process lifecycle, streaming cadence, and
        encoding. Non-JSON lines are skipped. Implementations must report
        non-zero exits via stderr to the caller's logger (the prod impl calls
        _warn; tests may choose differently).
        """
        ...


class SubprocessRunner:
    """Production ProcessRunner: real Popen, line-buffered utf-8 read loop."""

    def run_stream_json(
        self,
        argv: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        stdin_payload: str,
    ) -> Iterator[dict]:
        proc = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=env,
            text=True,
            encoding="utf-8",
        )
        assert proc.stdin is not None and proc.stdout is not None
        proc.stdin.write(stdin_payload)
        proc.stdin.close()

        try:
            for line in proc.stdout:
                line = line.rstrip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
        finally:
            proc.wait()
            if proc.returncode != 0 and proc.stderr is not None:
                err = proc.stderr.read()
                if err.strip():
                    _warn(f"claude exited with code {proc.returncode}: {err.strip()[:500]}")


# Module-level default runner. Tests override by passing a scripted runner to
# run_claude directly.
_default_runner: ProcessRunner = SubprocessRunner()


# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "sonnet"


class Effort(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"
    MAX = "max"


@dataclass(frozen=True)
class ModelSpec:
    id: str                                  # canonical claude id, e.g. "claude-opus-4-7"
    aliases: tuple[str, ...]                 # ("opus", "best", ...)
    context_window: int                      # default context (tokens)
    extended_context: int | None             # context when [1m] suffix used, else None
    max_output: int                          # documented max output tokens (Messages API)
    effort_levels: frozenset[Effort]         # empty = no effort support
    default_effort: Effort | None            # None when effort unsupported
    cost_warn_usd: float                     # per-session $ threshold


REGISTRY: tuple[ModelSpec, ...] = (
    # Context windows below reflect the API default (200k). Both Opus and Sonnet
    # support 1M via the [1m] suffix. Max/Team/Enterprise plans auto-upgrade Opus
    # to 1M without the suffix; coro discovers this from result.modelUsage when
    # a turn has run.
    ModelSpec(
        id="claude-opus-4-7",
        aliases=("opus", "best"),
        context_window=200_000,
        extended_context=1_000_000,
        max_output=128_000,
        effort_levels=frozenset({Effort.LOW, Effort.MEDIUM, Effort.HIGH, Effort.XHIGH, Effort.MAX}),
        default_effort=Effort.XHIGH,
        cost_warn_usd=50.00,
    ),
    ModelSpec(
        id="claude-sonnet-4-6",
        aliases=("sonnet",),
        context_window=200_000,
        extended_context=1_000_000,
        max_output=64_000,
        effort_levels=frozenset({Effort.LOW, Effort.MEDIUM, Effort.HIGH, Effort.MAX}),
        default_effort=Effort.HIGH,
        cost_warn_usd=25.00,
    ),
    ModelSpec(
        id="claude-haiku-4-5",
        aliases=("haiku",),
        context_window=200_000,
        extended_context=None,
        max_output=64_000,
        effort_levels=frozenset(),
        default_effort=None,
        cost_warn_usd=10.00,
    ),
)


@dataclass(frozen=True)
class ResolvedModel:
    claude_arg: str                          # verbatim value passed to `claude --model`
    spec: ModelSpec | None                   # None if slug not in registry
    extended: bool                           # [1m] suffix present
    effort: Effort | None                    # flag to emit; None = omit --effort
    warnings: tuple[str, ...] = ()


def _match_spec(slug: str) -> ModelSpec | None:
    for s in REGISTRY:
        if slug == s.id or slug in s.aliases:
            return s
    for s in REGISTRY:
        if s.id in slug:                     # dated snapshot, e.g. claude-opus-4-7-20260101
            return s
    return None


def _strip_1m(slug: str) -> tuple[str, bool]:
    if slug.endswith("[1m]"):
        return slug[:-4], True
    return slug, False


def resolve(model_input: str, effort_input: str | None = None) -> ResolvedModel:
    """Resolve a user (model, effort) pair. Never rewrites claude_arg.

    Effort rules (no fallback to ambient Claude Code env):
      - Valid CORO_EFFORT + spec supports it    → emit as-is
      - Valid CORO_EFFORT + spec lacks support  → drop (no flag), warn
      - Valid CORO_EFFORT + not in spec's set   → pass through, warn (claude downgrades silently)
      - Invalid / empty / unset CORO_EFFORT     → spec.default_effort (or None for haiku)
    """
    warnings: list[str] = []

    base, extended = _strip_1m(model_input)
    spec = _match_spec(base)

    if spec is None:
        warnings.append(
            f"unknown model '{model_input}'; passing through to claude "
            f"(warnings may be inaccurate)"
        )

    if extended and os.environ.get("CLAUDE_CODE_DISABLE_1M_CONTEXT", "").strip() == "1":
        warnings.append(
            "CLAUDE_CODE_DISABLE_1M_CONTEXT=1 in env; [1m] suffix will fail at claude"
        )

    # Effort resolution
    effort: Effort | None = None
    requested: Effort | None = None
    if effort_input is not None and effort_input.strip():
        try:
            requested = Effort(effort_input.strip().lower())
        except ValueError:
            warnings.append(f"invalid CORO_EFFORT '{effort_input}'; using spec default")
            requested = None

    if requested is not None:
        if spec is None:
            effort = requested                                  # can't validate, pass through
        elif not spec.effort_levels:
            warnings.append(f"{spec.id} does not support --effort; dropping '{requested}'")
            effort = None
        elif requested not in spec.effort_levels:
            legal = sorted(e.value for e in spec.effort_levels)
            warnings.append(
                f"{spec.id} does not support effort '{requested}' "
                f"(supported: {', '.join(legal)}); claude will downgrade silently"
            )
            effort = requested
        else:
            effort = requested
    elif spec is not None:
        effort = spec.default_effort                            # None for haiku; else registry default

    return ResolvedModel(
        claude_arg=model_input,
        spec=spec,
        extended=extended,
        effort=effort,
        warnings=tuple(warnings),
    )


def resolved_context_window(resolved: ResolvedModel) -> int:
    if resolved.spec is None:
        return 200_000
    if resolved.extended and resolved.spec.extended_context:
        return resolved.spec.extended_context
    return resolved.spec.context_window


# ---------------------------------------------------------------------------
# Config — environment reads
# ---------------------------------------------------------------------------

def _model() -> str:
    return os.environ.get("CORO_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def _effort_input() -> str | None:
    v = os.environ.get("CORO_EFFORT", "").strip()
    return v or None


def _project_override() -> str | None:
    return os.environ.get("CORO_PROJECT", "").strip() or None


def token_warn_threshold(resolved: ResolvedModel, ctx_window: int | None = None) -> int:
    abs_override = os.environ.get("CORO_TOKEN_WARN", "").strip()
    if abs_override:
        return int(abs_override)
    ratio = float(os.environ.get("CORO_TOKEN_WARN_RATIO", "0.80"))
    if ctx_window is None:
        ctx_window = resolved_context_window(resolved)
    return int(ctx_window * ratio)


def cost_warn_threshold(resolved: ResolvedModel) -> float:
    override = os.environ.get("CORO_COST_WARN", "").strip()
    if override:
        return float(override)
    if resolved.spec is None:
        return 25.00
    return resolved.spec.cost_warn_usd


def _claude_flags(resolved: ResolvedModel) -> list[str]:
    flags = [
        "--output-format", "stream-json",
        "--input-format", "stream-json",
        "--verbose",
        "--dangerously-skip-permissions",
    ]
    if resolved.effort is not None:
        flags += ["--effort", resolved.effort.value]
    add_dirs = os.environ.get("CORO_ADD_DIRS", "")
    for d in add_dirs.split(":"):
        d = d.strip()
        if d:
            flags += ["--add-dir", d]
    return flags


def _emit_warnings(resolved: ResolvedModel) -> None:
    for w in resolved.warnings:
        _warn(w)


def _load_preamble() -> str:
    """Load role/worker.md — the self-contained worker role spec.

    The worker receives its role doc only; it does not see the full protocol
    spec (that is orchestrator-side knowledge). See role/worker.md and
    protocol.md §Architecture for the three-layer separation.
    """
    worker_role = Path(__file__).parent.parent / "role" / "worker.md"
    if not worker_role.exists():
        die(f"role/worker.md not found at {worker_role}")
    return f"/salience on\n\n{worker_role.read_text().strip()}\n\nAcknowledge this role and wait for your first instruction."


# ---------------------------------------------------------------------------
# Project root discovery
# ---------------------------------------------------------------------------

def find_project_root() -> Path:
    override = _project_override()
    if override:
        root = Path(override).resolve()
        if not root.exists():
            die(f"CORO_PROJECT path does not exist: {root}")
        return root
    current = Path.cwd()
    while True:
        if (current / ".cache" / "coro").exists():
            return current
        parent = current.parent
        if parent == current:
            return Path.cwd()
        current = parent


# ---------------------------------------------------------------------------
# Session storage — slug-keyed layout
#
# Sessions are resources. The slug `<name>_<unix-seconds>` is the identity;
# <name> is a human-friendly label resolved to a slug at command time
# (see resolve_slug). See protocol.md §Session storage.
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"^(?P<name>.+)_(?P<ts>\d+)$")


def coro_dir(root: Path) -> Path:
    return root / ".cache" / "coro"

def slug_dir(root: Path, slug: str) -> Path:
    return coro_dir(root) / slug

def session_file(root: Path, slug: str) -> Path:
    return slug_dir(root, slug) / "uuid"

def meta_file(root: Path, slug: str) -> Path:
    return slug_dir(root, slug) / "meta"

def send_lock_path(root: Path, slug: str) -> Path:
    return slug_dir(root, slug) / "lock"

def hold_sentinel_path(root: Path, slug: str) -> Path:
    return slug_dir(root, slug) / "hold"

def turns_dir(root: Path, slug: str) -> Path:
    return slug_dir(root, slug) / "turns"

def turn_log_file(root: Path, slug: str, turn: int) -> Path:
    return turns_dir(root, slug) / f"{turn:03d}.jsonl"

def current_stack_path(root: Path) -> Path:
    return coro_dir(root) / "CURRENT"


def make_slug(name: str, time_fn: Callable[[], float] = time.time) -> str:
    """Generate a fresh slug for `name` at the current wall-clock unix time.

    time_fn is injectable for tests; default reads the real clock. Note: must
    return wall-clock seconds, not perf_counter/monotonic (slugs need to be
    meaningful across process runs).
    """
    return f"{name}_{int(time_fn())}"


def parse_slug(slug: str) -> tuple[str, int] | None:
    """Split a slug into (name, unix-seconds). Returns None if not slug-shaped."""
    m = _SLUG_RE.match(slug)
    if not m:
        return None
    return (m.group("name"), int(m.group("ts")))


def list_slugs(root: Path) -> list[str]:
    """All on-disk session slugs (directories under .cache/coro/ containing a uuid file)."""
    base = coro_dir(root)
    if not base.exists():
        return []
    out = []
    for child in base.iterdir():
        if child.is_dir() and (child / "uuid").exists():
            out.append(child.name)
    return sorted(out)


def resolve_slug(root: Path, arg: str) -> str:
    """Resolve a user argument (slug or name) to a canonical slug.

    Rules (in order):
      1. Exact slug match — directory exists and has a uuid file → use it.
      2. Name match — slugs whose <name> part == arg:
         - zero → error
         - one → use it
         - multiple → fail fast, list candidates
    """
    if slug_dir(root, arg).is_dir() and session_file(root, arg).exists():
        return arg

    matches = []
    for slug in list_slugs(root):
        parsed = parse_slug(slug)
        if parsed and parsed[0] == arg:
            matches.append(slug)

    if not matches:
        die(f"no session matches '{arg}' — run 'coro list' or 'coro create {arg}'")
    if len(matches) == 1:
        return matches[0]
    candidates = "\n  ".join(sorted(matches))
    die(
        f"'{arg}' is ambiguous — matches {len(matches)} sessions:\n  {candidates}\n"
        f"specify the full slug to disambiguate"
    )


def resolve_session_arg(root: Path, arg: str | None) -> str:
    """Resolve an optional session argument (slug or name) to a slug.

    If arg is None, use the top of CURRENT. If arg is given, resolve via
    resolve_slug.
    """
    if arg is not None:
        return resolve_slug(root, arg)
    top = current_top(root)
    if top is None:
        die("no session specified and CURRENT stack is empty; run 'coro use <name-or-slug>' first")
    return top


def acquire_send_lock(root: Path, slug: str) -> IO:
    path = send_lock_path(root, slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)
    fh = path.open("w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fh
    except BlockingIOError:
        fh.close()
        die(f"another send is in flight for session '{slug}'")


def check_send_lock(root: Path, slug: str) -> bool:
    path = send_lock_path(root, slug)
    if not path.exists():
        return False
    fh = path.open("r")
    try:
        fcntl.flock(fh, fcntl.LOCK_SH | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    finally:
        fh.close()
    return False


def write_hold(root: Path, slug: str, reason: str) -> None:
    p = hold_sentinel_path(root, slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    p.write_text(f"{reason}\n{ts}\n" if reason else f"\n{ts}\n")


def clear_hold(root: Path, slug: str) -> str | None:
    """Remove sentinel; return prior reason if any (for logging)."""
    p = hold_sentinel_path(root, slug)
    if not p.exists():
        return None
    text = p.read_text()
    p.unlink()
    lines = text.splitlines()
    return lines[0] if lines and lines[0].strip() else None


def read_hold(root: Path, slug: str) -> tuple[bool, str]:
    p = hold_sentinel_path(root, slug)
    if not p.exists():
        return (False, "")
    lines = p.read_text().splitlines()
    return (True, lines[0] if lines and lines[0].strip() else "")


def current_top(root: Path) -> str | None:
    p = current_stack_path(root)
    if not p.exists():
        return None
    lines = [l for l in p.read_text().splitlines() if l.strip()]
    return lines[-1] if lines else None


def current_push(root: Path, slug: str) -> None:
    p = current_stack_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = p.read_text().splitlines() if p.exists() else []
    existing = [l for l in existing if l.strip()]
    existing.append(slug)
    p.write_text("\n".join(existing) + "\n")


def current_pop(root: Path) -> str | None:
    p = current_stack_path(root)
    if not p.exists():
        return None
    existing = [l for l in p.read_text().splitlines() if l.strip()]
    if not existing:
        return None
    top = existing.pop()
    p.write_text("\n".join(existing) + ("\n" if existing else ""))
    return top


def current_list(root: Path) -> list[str]:
    p = current_stack_path(root)
    if not p.exists():
        return []
    return [l for l in p.read_text().splitlines() if l.strip()]


def load_session(root: Path, slug: str) -> str:
    """Read the persisted claude session UUID for `slug`."""
    path = session_file(root, slug)
    if not path.exists():
        die(f"no session '{slug}' on disk")
    return path.read_text().strip()


def load_meta(root: Path, slug: str) -> dict:
    path = meta_file(root, slug)
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_session(root: Path, slug: str, uuid: str, model: str):
    slug_dir(root, slug).mkdir(parents=True, exist_ok=True)
    session_file(root, slug).write_text(uuid + "\n")
    meta_file(root, slug).write_text(json.dumps({"model": model}) + "\n")


def next_turn_number(root: Path, slug: str) -> int:
    turns_dir(root, slug).mkdir(parents=True, exist_ok=True)
    existing = sorted(turns_dir(root, slug).glob("*.jsonl"))
    if not existing:
        return 0
    return int(existing[-1].stem) + 1


def last_turn_number(root: Path, slug: str) -> int:
    d = turns_dir(root, slug)
    if not d.exists():
        return -1
    existing = sorted(d.glob("*.jsonl"))
    if not existing:
        return -1
    return int(existing[-1].stem)


# ---------------------------------------------------------------------------
# Claude invocation
# ---------------------------------------------------------------------------

def make_payload(content: str) -> str:
    return json.dumps({
        "type": "user",
        "message": {"role": "user", "content": content}
    })

def _subprocess_env() -> dict[str, str]:
    """Build env for the claude subprocess. Set long-phase defaults unless user has them."""
    env = os.environ.copy()
    env.setdefault("API_TIMEOUT_MS", "1200000")                 # 20 min
    env.setdefault("BASH_MAX_TIMEOUT_MS", "1200000")            # 20 min
    return env


def _max_budget_usd() -> str | None:
    v = os.environ.get("CORO_MAX_BUDGET_USD", "").strip()
    return v or None


def build_claude_argv(
    resolved: ResolvedModel,
    *,
    session_id: str | None,
    resume_uuid: str | None,
    max_budget_usd: str | None,
) -> list[str]:
    """Pure: assemble the `claude` argv for a turn. Testable in isolation."""
    if (session_id is None) == (resume_uuid is None):
        raise CoroError("build_claude_argv requires exactly one of session_id or resume_uuid")

    argv = ["claude", "--print", "--model", resolved.claude_arg] + _claude_flags(resolved)
    if session_id:
        argv += ["--session-id", session_id]
    else:
        argv += ["--resume", resume_uuid]
    if max_budget_usd:
        argv += ["--max-budget-usd", max_budget_usd]
    return argv


def run_claude(
    root: Path,
    payload: str,
    resolved: ResolvedModel,
    *,
    session_id: str | None = None,
    resume_uuid: str | None = None,
    on_event: Callable[[dict], None] | None = None,
    runner: ProcessRunner | None = None,
) -> list[dict]:
    """Invoke claude for one turn via the supplied ProcessRunner (prod default).

    Exactly one of session_id (create) or resume_uuid (resume) must be given —
    they are mutually exclusive at the claude CLI level.

    on_event is called for each parsed event as it arrives. Use it to
    progressively write the turn jsonl, print assistant text, etc.

    Returns the accumulated list of events.
    """
    argv = build_claude_argv(
        resolved,
        session_id=session_id,
        resume_uuid=resume_uuid,
        max_budget_usd=_max_budget_usd(),
    )

    r = runner if runner is not None else _default_runner
    events: list[dict] = []
    for e in r.run_stream_json(
        argv, cwd=root, env=_subprocess_env(), stdin_payload=payload
    ):
        events.append(e)
        if on_event is not None:
            try:
                on_event(e)
            except Exception as ex:                              # don't let a callback break the read loop
                _warn(f"on_event callback raised: {ex}")
    return events

def extract_session_id(events: list[dict]) -> str | None:
    for e in events:
        if e.get("type") == "system":
            return e.get("session_id")
    return None

def extract_text(events: list[dict]) -> str:
    parts = []
    for e in events:
        if e.get("type") == "assistant":
            for block in e["message"].get("content", []):
                if block.get("type") == "text":
                    parts.append(block["text"])
    return "".join(parts)

def extract_yield(text: str) -> str | None:
    for line in reversed(text.strip().splitlines()):
        line = line.strip()
        if line.upper().startswith("YIELD:"):
            return line
    return None

def warn_missing_yield(turn: int) -> None:
    _warn(f"warning: turn {turn} has no YIELD line; protocol violation")

def _warn(msg: str) -> None:
    if sys.stderr.isatty():
        msg = f"\033[33m{msg}\033[0m"
    print(msg, file=sys.stderr)

def extract_result(events: list[dict]) -> dict | None:
    for e in events:
        if e.get("type") == "result":
            return e
    return None

def budget_exceeded(result: dict | None) -> bool:
    return bool(result) and result.get("subtype") == "error_max_budget_usd"

def result_tokens(result: dict) -> tuple[int, int, int, int]:
    """Returns (input, cache_read, cache_creation, output). Sum of first three = total context tokens."""
    u = result.get("usage", {})
    return (
        u.get("input_tokens", 0),
        u.get("cache_read_input_tokens", 0),
        u.get("cache_creation_input_tokens", 0),
        u.get("output_tokens", 0),
    )

def extract_context_window(result: dict) -> int | None:
    """Read the actual context window the model used from result.modelUsage."""
    mu = result.get("modelUsage") or {}
    for entry in mu.values():
        cw = entry.get("contextWindow")
        if cw:
            return int(cw)
    return None

def extract_max_output(result: dict) -> int | None:
    """Read the actual max-output cap applied for the turn from result.modelUsage."""
    mu = result.get("modelUsage") or {}
    for entry in mu.values():
        mo = entry.get("maxOutputTokens")
        if mo:
            return int(mo)
    return None

def session_total_cost(root: Path, slug: str) -> float:
    total = 0.0
    d = turns_dir(root, slug)
    if not d.exists():
        return 0.0
    for path in sorted(d.glob("*.jsonl")):
        events = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        r = extract_result(events)
        if r:
            total += r.get("total_cost_usd", 0.0)
    return total

def save_turn(root: Path, slug: str, turn: int, events: list[dict]):
    """Write turn jsonl in a single pass (used for retroactive/error-path saves)."""
    turns_dir(root, slug).mkdir(parents=True, exist_ok=True)
    path = turn_log_file(root, slug, turn)
    with path.open("w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")


def open_turn_writer(root: Path, slug: str, turn: int) -> IO:
    """Open the turn jsonl for progressive writes. Caller must close."""
    turns_dir(root, slug).mkdir(parents=True, exist_ok=True)
    path = turn_log_file(root, slug, turn)
    return path.open("w")


def make_stream_callback(
    writer: IO,
    *,
    print_text: bool = True,
    progress: bool = True,
) -> Callable[[dict], None]:
    """Return an on_event callback that writes jsonl progressively and streams visible output.

    print_text: when True, assistant text blocks print to stdout as they arrive.
    progress:   when True, tool_use / tool_result events print one-line notes to stderr.
    """
    def cb(e: dict) -> None:
        writer.write(json.dumps(e) + "\n")
        writer.flush()

        t = e.get("type")
        if t == "assistant" and print_text:
            for b in e.get("message", {}).get("content", []) or []:
                if b.get("type") == "text":
                    sys.stdout.write(b.get("text", ""))
                    sys.stdout.flush()
                elif b.get("type") == "tool_use" and progress:
                    name = b.get("name", "?")
                    keys = list((b.get("input") or {}).keys())
                    _progress(f"[coroutine] tool_use: {name}({', '.join(keys)})")
        elif t == "user" and progress:
            for b in e.get("message", {}).get("content", []) or []:
                if b.get("type") == "tool_result":
                    tid = (b.get("tool_use_id") or "")[:12]
                    _progress(f"[coroutine] tool_result: {tid}")
    return cb


def _progress(msg: str) -> None:
    """Progress line to stderr, dim in a tty so it doesn't compete with the stdout stream."""
    if sys.stderr.isatty():
        msg = f"\033[2m{msg}\033[0m"
    print(msg, file=sys.stderr)

def read_stdin_or_die() -> str:
    if sys.stdin.isatty():
        die("stdin is a terminal — use: coro send <name> <<< 'message'")
    content = sys.stdin.read().strip()
    if not content:
        die("stdin is empty")
    return content


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def _delete_session_files(root: Path, slug: str) -> None:
    """Remove on-disk session bookkeeping. Used when create fails irrecoverably.

    Turn jsonl files are intentionally preserved for post-mortem debugging.
    """
    # Remove bookkeeping files; leave turns/ subdir intact.
    for p in (session_file(root, slug), meta_file(root, slug),
              hold_sentinel_path(root, slug), send_lock_path(root, slug)):
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass
    # Pop from CURRENT stack if we put it there
    stack = current_list(root)
    if stack and stack[-1] == slug:
        current_pop(root)


def cmd_create(args, root: Path):
    name = args.name
    if "_" in name and parse_slug(name):
        die(f"refusing to create session with slug-shaped name '{name}' — pick a name without a trailing _<digits>")

    slug = make_slug(name)
    # Extremely unlikely (same-second collision), but handle it anyway.
    if slug_dir(root, slug).exists():
        die(f"slug '{slug}' already exists — wait a second and retry")

    model = _model()
    resolved = resolve(model, _effort_input())
    _emit_warnings(resolved)
    preamble = _load_preamble()

    # Pre-assign UUID and persist before invoking claude, so a crash mid-create
    # leaves a recoverable record. Uses --session-id (PoC 1 confirmed).
    session_uuid = str(uuid.uuid4())
    save_session(root, slug, session_uuid, model)
    current_push(root, slug)

    turn = next_turn_number(root, slug)
    effort_str = f" effort={resolved.effort.value}" if resolved.effort else ""
    print(f"[coroutine] creating session slug={slug} (model={model}{effort_str}) id={session_uuid[:8]}..",
          file=sys.stderr)

    writer = open_turn_writer(root, slug, turn)
    try:
        # Preamble turn: don't stream preamble-ack text to stdout (low signal, high noise).
        on_event = make_stream_callback(writer, print_text=False, progress=False)
        events = run_claude(root, make_payload(preamble), resolved,
                            session_id=session_uuid, on_event=on_event)
    finally:
        writer.close()

    result = extract_result(events)
    if result and result.get("is_error"):
        if budget_exceeded(result):
            cost = result.get("total_cost_usd", 0)
            _delete_session_files(root, slug)
            die(f"session creation aborted: budget of ${_max_budget_usd()} exceeded (spent ${cost:.4f})")
        msg = result.get("result", "unknown error")
        _delete_session_files(root, slug)
        die(f"session creation failed: {msg}")

    reported = extract_session_id(events)
    if reported and reported != session_uuid:
        _warn(f"warning: claude reported session_id {reported[:8]}.. but we assigned {session_uuid[:8]}..")

    text = extract_text(events)
    cost = result["total_cost_usd"] if result else 0
    print(f"[coroutine] session={session_uuid} turn={turn} cost=${cost:.4f}", file=sys.stderr)
    print(f"[coroutine] {extract_yield(text) or '(acknowledged)'}", file=sys.stderr)
    # Print the slug on stdout so shell callers can capture it.
    print(slug)

    # Turn 1 (optional, deprecated): if stdin has content, send immediately.
    if not sys.stdin.isatty():
        _warn("warning: 'coro create <name> < file' is deprecated; "
              "use 'coro send <name> < file' for turn 1")

        extra = sys.stdin.read().strip()
        if extra:
            turn = next_turn_number(root, slug)
            print(f"[coroutine] sending initial content turn={turn}...", file=sys.stderr)

            writer = open_turn_writer(root, slug, turn)
            try:
                on_event = make_stream_callback(writer, print_text=True, progress=True)
                events = run_claude(root, make_payload(extra), resolved,
                                    resume_uuid=session_uuid, on_event=on_event)
            finally:
                writer.close()

            text = extract_text(events)
            result = extract_result(events)
            signal = extract_yield(text)

            cost = result["total_cost_usd"] if result else 0
            print(f"\n[coroutine] turn={turn} cost=${cost:.4f}", file=sys.stderr)
            if budget_exceeded(result):
                _warn(f"warning: turn exceeded CORO_MAX_BUDGET_USD=${_max_budget_usd()} "
                      f"(spent ${cost:.4f}); session remains usable")
            if signal:
                print(f"[coroutine] {signal}", file=sys.stderr)
            else:
                warn_missing_yield(turn)


def cmd_send(root: Path, arg: str | None):
    slug = resolve_session_arg(root, arg)
    session_uuid = load_session(root, slug)
    meta = load_meta(root, slug)
    model = meta.get("model", _model())
    resolved = resolve(model, _effort_input())
    _emit_warnings(resolved)

    content = read_stdin_or_die()

    prior_hold = clear_hold(root, slug)
    if prior_hold is not None:
        msg = f"note: cleared hold on session '{slug}'"
        if prior_hold:
            msg += f" (reason: {prior_hold})"
        print(msg, file=sys.stderr)

    lock_fh = acquire_send_lock(root, slug)
    try:
        turn = next_turn_number(root, slug)

        effort_str = f" effort={resolved.effort.value}" if resolved.effort else ""
        print(f"[coroutine] resuming {slug} turn={turn} model={model}{effort_str}...", file=sys.stderr)

        writer = open_turn_writer(root, slug, turn)
        try:
            on_event = make_stream_callback(writer, print_text=True, progress=True)
            events = run_claude(root, make_payload(content), resolved,
                                resume_uuid=session_uuid, on_event=on_event)
        finally:
            writer.close()

        text = extract_text(events)
        result = extract_result(events)
        signal = extract_yield(text)

        cost = result["total_cost_usd"] if result else 0
        print(f"\n[coroutine] turn={turn} cost=${cost:.4f}", file=sys.stderr)
        if budget_exceeded(result):
            _warn(f"warning: turn exceeded CORO_MAX_BUDGET_USD=${_max_budget_usd()} "
                  f"(spent ${cost:.4f}); session remains usable — raise cap or continue smaller")
        if signal:
            print(f"[coroutine] {signal}", file=sys.stderr)
        else:
            warn_missing_yield(turn)
    finally:
        lock_fh.close()


def cmd_status(root: Path, arg: str | None):
    slug = resolve_session_arg(root, arg)
    meta = load_meta(root, slug)
    model = meta.get("model", DEFAULT_MODEL)
    resolved = resolve(model)                                   # status does not honor CORO_EFFORT
    held = check_send_lock(root, slug)
    turn = last_turn_number(root, slug)
    if turn < 0:
        die(f"no turns found for session '{slug}'")
    path = turn_log_file(root, slug, turn)
    events = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    text = extract_text(events)
    result = extract_result(events)
    signal = extract_yield(text)

    if result:
        inp, cr, cc, out = result_tokens(result)
        total_ctx = inp + cr + cc
        runtime_max_out = extract_max_output(result)
        if runtime_max_out:
            tokens_str = f"{total_ctx} in / {out} out (cap {runtime_max_out})  (last turn)"
        else:
            tokens_str = f"{total_ctx} in / {out} out  (last turn)"
    else:
        tokens_str = "-"
        runtime_max_out = None

    total_cost = session_total_cost(root, slug)

    is_held, hold_reason = read_hold(root, slug)
    if is_held:
        hold_str = f"yes — {hold_reason}" if hold_reason else "yes"
    else:
        hold_str = "no"

    if signal:
        status_token = signal.split("|")[0].replace("YIELD:", "").strip()
        if status_token.upper() == "USER_HOLD":
            _warn("warning: legacy USER_HOLD status observed; this signal is deprecated. Use 'coro hold' instead.")
            signal = "YIELD: BLOCKED |" + (signal.split("|", 1)[1] if "|" in signal else "") + " (legacy USER_HOLD)"
        yield_str = signal
    else:
        last_line = text.strip().splitlines()[-1] if text.strip() else "(no output)"
        yield_str = f"(no YIELD signal in turn {turn}) last: {last_line}"

    W = 10  # label column width
    print(f"{'session:':{W}}{slug}")
    print(f"{'model:':{W}}{model}")
    print(f"{'sending:':{W}}{'yes' if held else 'no'}")
    print(f"{'hold:':{W}}{hold_str}")
    print(f"{'tokens:':{W}}{tokens_str}")
    print(f"{'cost:':{W}}${total_cost:.4f} total")
    if budget_exceeded(result):
        last_cost = result.get("total_cost_usd", 0) if result else 0
        cap = _max_budget_usd() or "?"
        print(f"{'budget:':{W}}EXCEEDED — last turn spent ${last_cost:.4f} of ${cap} cap")
    print(f"{'yield:':{W}}{yield_str}")

    if not signal:
        warn_missing_yield(turn)

    if result:
        ctx_window = extract_context_window(result) or resolved_context_window(resolved)
        warn_threshold = token_warn_threshold(resolved, ctx_window)
        if total_ctx > warn_threshold:
            pct = int(total_ctx / ctx_window * 100)
            _warn(f"warning: last turn used {total_ctx} input tokens — {pct}% of {model} context ({ctx_window})")

        # Warn if runtime cap is well below model's documented max (e.g. CLAUDE_CODE_MAX_OUTPUT_TOKENS clamp)
        if resolved.spec and runtime_max_out and runtime_max_out < resolved.spec.max_output // 2:
            _warn(
                f"note: runtime max-output cap is {runtime_max_out} tokens "
                f"({resolved.spec.id} can produce up to {resolved.spec.max_output}); "
                f"check CLAUDE_CODE_MAX_OUTPUT_TOKENS / ANTHROPIC_MAX_OUTPUT_TOKENS"
            )

    cost_threshold = cost_warn_threshold(resolved)
    if total_cost > cost_threshold:
        _warn(f"warning: session cost ${total_cost:.2f} exceeds threshold ${cost_threshold:.2f}")


def cmd_turns(root: Path, arg: str | None):
    slug = resolve_session_arg(root, arg)
    d = turns_dir(root, slug)
    logs = sorted(d.glob("*.jsonl")) if d.exists() else []
    if not logs:
        die(f"no turns found for session '{slug}'")
    meta = load_meta(root, slug)
    model = meta.get("model", "?")
    print(f"session: {slug}  model: {model}")
    for path in logs:
        turn = int(path.stem)
        events = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        result = extract_result(events)
        text = extract_text(events)
        cost = f"${result['total_cost_usd']:.4f}" if result else "?"
        if turn == 0:
            summary = "(preamble)"
        else:
            summary = extract_yield(text) or f"(no yield) {text.strip().splitlines()[-1][:60] if text.strip() else ''}"
        print(f"  turn {turn:03d}  cost={cost}  {summary}")
    total = session_total_cost(root, slug)
    print(f"  total        ${total:.4f}")


def cmd_log(root: Path, arg: str | None, turn: int | None):
    slug = resolve_session_arg(root, arg)
    if turn is None:
        turn = last_turn_number(root, slug)
        if turn < 0:
            die(f"no turns found for session '{slug}'")
    path = turn_log_file(root, slug, turn)
    if not path.exists():
        die(f"no log for turn {turn} of session '{slug}'")
    print(path.read_text(), end="")


def cmd_use(root: Path, arg: str):
    slug = resolve_slug(root, arg)
    current_push(root, slug)
    print(f"pushed {slug}", file=sys.stderr)


def cmd_pop(root: Path):
    top = current_pop(root)
    if top is None:
        die("CURRENT stack is empty")
    print(top)


def cmd_list_sessions(root: Path):
    stack = current_list(root)
    if not stack:
        print("(empty)")
        return
    for slug in reversed(stack):
        print(slug)


def cmd_new_phase(args, root: Path):
    phase_slug = args.slug
    todo_dir = root / ".cache" / "TODO"
    todo_dir.mkdir(parents=True, exist_ok=True)

    spec_path = todo_dir / f"phase-{phase_slug}.md"
    kickoff_path = todo_dir / f"phase-{phase_slug}-kickoff.md"

    if (spec_path.exists() or kickoff_path.exists()) and not args.force:
        die(f"phase '{phase_slug}' files already exist; use --force to overwrite")

    template_dir = Path(__file__).parent.parent / "skills" / "coro-develop" / "templates"
    spec_template = (template_dir / "phase.md").read_text()
    kickoff_template = (template_dir / "phase-kickoff.md").read_text()

    spec_path.write_text(spec_template.replace("{slug}", phase_slug))
    kickoff_path.write_text(kickoff_template.replace("{slug}", phase_slug))

    print(f"created {spec_path}")
    print(f"created {kickoff_path}")


def cmd_hold(args, root: Path) -> int:
    slug = resolve_session_arg(root, args.name)
    load_session(root, slug)
    reason = " ".join(r for r in (args.reason or []) if r.strip())
    write_hold(root, slug, reason)
    print(f"held session {slug}" + (f" — {reason}" if reason else ""))
    return 0


def cmd_unhold(args, root: Path) -> int:
    slug = resolve_session_arg(root, args.name)
    load_session(root, slug)
    prior = clear_hold(root, slug)
    if prior is None:
        print(f"session {slug} was not held")
    else:
        print(f"unheld session {slug}" + (f" (was: {prior})" if prior else ""))
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def die(msg: str) -> None:
    """Raise an operator-facing error.

    Implemented via CoroError so logic functions can be exercised from tests
    without triggering SystemExit. The CLI entry point catches CoroError and
    exits 1.
    """
    raise CoroError(msg)


def main():
    parser = argparse.ArgumentParser(
        prog="coroutine",
        description="Stateful Claude session manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Runtime config via env:\n"
            "  CORO_MODEL      alias (opus|sonnet|haiku|best), canonical id, or [1m]-suffixed;\n"
            "                  unknown slugs pass through with a warning. Default: sonnet.\n"
            "  CORO_EFFORT     low|medium|high|xhigh|max. If unset, the spec's per-model\n"
            "                  default is used (coro does not inherit CLAUDE_CODE_EFFORT_LEVEL).\n"
            "  CORO_PROJECT    project root (default: auto-discover)\n"
            "  CORO_ADD_DIRS   colon-separated --add-dir paths\n"
            "  CORO_MAX_BUDGET_USD  per-turn budget cap (soft-fail in send, hard-fail in create)\n"
            "  CORO_TOKEN_WARN_RATIO / CORO_TOKEN_WARN / CORO_COST_WARN  override thresholds\n\n"
            "Subprocess env defaults (set when unset in parent):\n"
            "  API_TIMEOUT_MS=1200000  BASH_MAX_TIMEOUT_MS=1200000"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", help="Create session (sends preamble; stdin for turn 1 is deprecated — use 'send')")
    p_create.add_argument("name")

    p_new_phase = sub.add_parser("new-phase", help="Scaffold a new phase spec + kickoff from templates")
    p_new_phase.add_argument("slug")
    p_new_phase.add_argument("--force", action="store_true", help="Overwrite existing files")

    p_send = sub.add_parser("send", help="Send a message (reads from stdin)")
    p_send.add_argument("name", nargs="?", default=None)

    p_status = sub.add_parser("status", help="Show last YIELD signal")
    p_status.add_argument("name", nargs="?", default=None)

    p_turns = sub.add_parser("turns", help="List all turns with cost summary")
    p_turns.add_argument("name", nargs="?", default=None)

    p_log = sub.add_parser("log", help="Print raw jsonl for a turn (default: last)")
    p_log.add_argument("name", nargs="?", default=None)
    p_log.add_argument("turn", nargs="?", type=int, default=None)

    p_use = sub.add_parser("use", help="Push a session onto the CURRENT stack")
    p_use.add_argument("name")

    sub.add_parser("pop", help="Pop the top of the CURRENT stack")

    sub.add_parser("list", help="Show the CURRENT stack, top to bottom")

    p_hold = sub.add_parser("hold", help="Mark session as awaiting human input")
    p_hold.add_argument("name", nargs="?", default=None)
    p_hold.add_argument("reason", nargs="*", help="optional reason")

    p_unhold = sub.add_parser("unhold", help="Clear hold on session")
    p_unhold.add_argument("name", nargs="?", default=None)

    args = parser.parse_args()

    try:
        root = find_project_root()

        if args.command == "create":
            cmd_create(args, root)
        elif args.command == "new-phase":
            cmd_new_phase(args, root)
        elif args.command == "send":
            cmd_send(root, args.name)
        elif args.command == "status":
            cmd_status(root, args.name)
        elif args.command == "turns":
            cmd_turns(root, args.name)
        elif args.command == "log":
            cmd_log(root, args.name, args.turn)
        elif args.command == "use":
            cmd_use(root, args.name)
        elif args.command == "pop":
            cmd_pop(root)
        elif args.command == "list":
            cmd_list_sessions(root)
        elif args.command == "hold":
            sys.exit(cmd_hold(args, root))
        elif args.command == "unhold":
            sys.exit(cmd_unhold(args, root))
    except CoroError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
