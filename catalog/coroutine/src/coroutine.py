#!/usr/bin/env python3
"""
coroutine — stateful Claude session manager

Usage:
  coroutine create <name>       # create session (preamble only; stdin for turn 1 deprecated)
  coroutine send <name>         # reads prompt from stdin
  coroutine status <name>       # last YIELD signal
  coroutine turns <name>        # list turns with cost summary
  coroutine log <name> [<N>]    # raw jsonl for turn N (default: last)
  coroutine new-phase <slug>    # scaffold .cache/TODO/phase-<slug>.md + kickoff

Environment:
  CORO_MODEL      Claude model slug (default: sonnet)
  CORO_PROJECT    Project root path (default: auto-discover from cwd)
  CORO_ADD_DIRS   Colon-separated list of extra --add-dir paths for claude
  CORO_EFFORT     Effort level passed to claude (low|medium|high|xhigh|max)

Sessions stored in: <project>/.cache/sessions/
Turn logs stored in: <project>/.cache/turns/
"""

import argparse
import fcntl
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import IO

# ---------------------------------------------------------------------------
# Config — loaded from environment, no CLI overrides
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "sonnet"

def _claude_flags() -> list[str]:
    flags = [
        "--output-format", "stream-json",
        "--input-format", "stream-json",
        "--verbose",
        "--dangerously-skip-permissions",
    ]
    effort = os.environ.get("CORO_EFFORT", "").strip()
    if effort:
        flags += ["--effort", effort]
    add_dirs = os.environ.get("CORO_ADD_DIRS", "")
    for d in add_dirs.split(":"):
        d = d.strip()
        if d:
            flags += ["--add-dir", d]
    return flags

def _load_preamble() -> str:
    """Load protocol.md from fixed path relative to this script."""
    protocol = Path(__file__).parent.parent / "protocol.md"
    if not protocol.exists():
        die(f"protocol.md not found at {protocol}")
    return f"/salience on\n\n{protocol.read_text().strip()}\n\nAcknowledge this protocol and wait for your first instruction."

def _model() -> str:
    return os.environ.get("CORO_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL

MODEL_CONTEXT = {
    "opus": 1_000_000,
    "sonnet": 200_000,
    "haiku": 200_000,
}

def model_context(model: str) -> int:
    for slug, ctx in MODEL_CONTEXT.items():
        if slug in model:
            return ctx
    print(f"note: unknown model '{model}', assuming 200k context window", file=sys.stderr)
    return 200_000

def token_warn_threshold(model: str, ctx_window: int | None = None) -> int:
    abs_override = os.environ.get("CORO_TOKEN_WARN", "").strip()
    if abs_override:
        return int(abs_override)
    ratio = float(os.environ.get("CORO_TOKEN_WARN_RATIO", "0.80"))
    if ctx_window is None:
        ctx_window = model_context(model)
    return int(ctx_window * ratio)

def cost_warn_threshold() -> float:
    return float(os.environ.get("CORO_COST_WARN", "25.00"))

def _project_override() -> str | None:
    return os.environ.get("CORO_PROJECT", "").strip() or None


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
        if (current / ".cache" / "sessions").exists():
            return current
        parent = current.parent
        if parent == current:
            return Path.cwd()
        current = parent


# ---------------------------------------------------------------------------
# Session storage
# ---------------------------------------------------------------------------

def sessions_dir(root: Path) -> Path:
    return root / ".cache" / "sessions"

def turns_dir(root: Path) -> Path:
    return root / ".cache" / "turns"

def session_file(root: Path, name: str) -> Path:
    return sessions_dir(root) / f"{name}.uuid"

def meta_file(root: Path, name: str) -> Path:
    return sessions_dir(root) / f"{name}.meta"

def send_lock_path(root: Path, name: str) -> Path:
    return sessions_dir(root) / f"{name}.lock"

def acquire_send_lock(root: Path, name: str) -> IO:
    path = send_lock_path(root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)
    fh = path.open("w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fh
    except BlockingIOError:
        fh.close()
        die(f"another send is in flight for session '{name}'")

def check_send_lock(root: Path, name: str) -> bool:
    path = send_lock_path(root, name)
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

def hold_sentinel_path(root: Path, name: str) -> Path:
    return sessions_dir(root) / f"{name}.hold"

def write_hold(root: Path, name: str, reason: str) -> None:
    p = hold_sentinel_path(root, name)
    p.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    p.write_text(f"{reason}\n{ts}\n" if reason else f"\n{ts}\n")

def clear_hold(root: Path, name: str) -> str | None:
    """Remove sentinel; return prior reason if any (for logging)."""
    p = hold_sentinel_path(root, name)
    if not p.exists():
        return None
    text = p.read_text()
    p.unlink()
    lines = text.splitlines()
    return lines[0] if lines and lines[0].strip() else None

def read_hold(root: Path, name: str) -> tuple[bool, str]:
    p = hold_sentinel_path(root, name)
    if not p.exists():
        return (False, "")
    lines = p.read_text().splitlines()
    return (True, lines[0] if lines and lines[0].strip() else "")

def current_stack_path(root: Path) -> Path:
    return sessions_dir(root) / "CURRENT"

def current_top(root: Path) -> str | None:
    p = current_stack_path(root)
    if not p.exists():
        return None
    lines = [l for l in p.read_text().splitlines() if l.strip()]
    return lines[-1] if lines else None

def current_push(root: Path, name: str) -> None:
    p = current_stack_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = p.read_text().splitlines() if p.exists() else []
    existing = [l for l in existing if l.strip()]
    existing.append(name)
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

def resolve_name(root: Path, name: str | None) -> str:
    if name is not None:
        return name
    top = current_top(root)
    if top is None:
        die("no session specified and CURRENT stack is empty; run 'coro use <name>' first")
    return top

def load_session(root: Path, name: str) -> str:
    path = session_file(root, name)
    if not path.exists():
        die(f"no session '{name}' — run: coro create {name}")
    return path.read_text().strip()

def load_meta(root: Path, name: str) -> dict:
    path = meta_file(root, name)
    if not path.exists():
        return {}
    return json.loads(path.read_text())

def save_session(root: Path, name: str, uuid: str, model: str):
    sessions_dir(root).mkdir(parents=True, exist_ok=True)
    session_file(root, name).write_text(uuid + "\n")
    meta_file(root, name).write_text(json.dumps({"model": model}) + "\n")

def turn_log_file(root: Path, name: str, turn: int) -> Path:
    return turns_dir(root) / f"{name}-{turn:03d}.jsonl"

def next_turn_number(root: Path, name: str) -> int:
    turns_dir(root).mkdir(parents=True, exist_ok=True)
    existing = sorted(turns_dir(root).glob(f"{name}-*.jsonl"))
    if not existing:
        return 0
    return int(existing[-1].stem.rsplit("-", 1)[-1]) + 1

def last_turn_number(root: Path, name: str) -> int:
    existing = sorted(turns_dir(root).glob(f"{name}-*.jsonl"))
    if not existing:
        return -1
    return int(existing[-1].stem.rsplit("-", 1)[-1])


# ---------------------------------------------------------------------------
# Claude invocation
# ---------------------------------------------------------------------------

def make_payload(content: str) -> str:
    return json.dumps({
        "type": "user",
        "message": {"role": "user", "content": content}
    })

def run_claude(root: Path, payload: str, model: str, resume_uuid: str | None = None) -> list[dict]:
    cmd = ["claude", "--print", "--model", model] + _claude_flags()
    if resume_uuid:
        cmd += ["--resume", resume_uuid]
    proc = subprocess.run(cmd, input=payload.encode(), capture_output=True, cwd=root)
    events = []
    for line in proc.stdout.decode().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass
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

def result_tokens(result: dict) -> tuple[int, int, int, int]:
    """Returns (input, cache_read, cache_creation, output). Sum of first three = total context tokens."""
    u = result.get("usage", {})
    return (
        u.get("input_tokens", 0),
        u.get("cache_read_input_tokens", 0),
        u.get("cache_creation_input_tokens", 0),
        u.get("output_tokens", 0),
    )

def session_total_cost(root: Path, name: str) -> float:
    total = 0.0
    for path in sorted(turns_dir(root).glob(f"{name}-*.jsonl")):
        events = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        r = extract_result(events)
        if r:
            total += r.get("total_cost_usd", 0.0)
    return total

def save_turn(root: Path, name: str, turn: int, events: list[dict]):
    turns_dir(root).mkdir(parents=True, exist_ok=True)
    path = turn_log_file(root, name, turn)
    with path.open("w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

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

def cmd_create(args, root: Path):
    name = args.name
    if session_file(root, name).exists():
        die(f"session '{name}' already exists — delete {session_file(root, name)} to recreate")

    model = _model()
    preamble = _load_preamble()

    turn = next_turn_number(root, name)
    print(f"[coroutine] creating session '{name}' (model={model})...", file=sys.stderr)
    events = run_claude(root, make_payload(preamble), model)

    uuid = extract_session_id(events)
    if not uuid:
        die("failed to get session_id from claude output")

    save_session(root, name, uuid, model)
    save_turn(root, name, turn, events)
    current_push(root, name)

    text = extract_text(events)
    result = extract_result(events)
    cost = result["total_cost_usd"] if result else 0
    print(f"[coroutine] session={uuid} turn={turn} cost=${cost:.4f}", file=sys.stderr)
    print(f"[coroutine] {extract_yield(text) or '(acknowledged)'}", file=sys.stderr)

    # Turn 1 (optional): if stdin has content, send immediately
    # Deprecated: use 'coro send <name>' for turn 1 instead.
    if not sys.stdin.isatty():
        _warn("warning: 'coro create <name> < file' is deprecated; "
              "use 'coro send <name> < file' for turn 1")

        extra = sys.stdin.read().strip()
        if extra:
            turn = next_turn_number(root, name)
            print(f"[coroutine] sending initial content turn={turn}...", file=sys.stderr)
            events = run_claude(root, make_payload(extra), model, resume_uuid=uuid)
            save_turn(root, name, turn, events)

            text = extract_text(events)
            result = extract_result(events)
            signal = extract_yield(text)

            print(text)
            cost = result["total_cost_usd"] if result else 0
            print(f"\n[coroutine] turn={turn} cost=${cost:.4f}", file=sys.stderr)
            if signal:
                print(f"[coroutine] {signal}", file=sys.stderr)
            else:
                warn_missing_yield(turn)


def cmd_send(root: Path, name: str | None):
    name = resolve_name(root, name)
    uuid = load_session(root, name)
    meta = load_meta(root, name)
    model = meta.get("model", _model())

    content = read_stdin_or_die()

    prior_hold = clear_hold(root, name)
    if prior_hold is not None:
        msg = f"note: cleared hold on session '{name}'"
        if prior_hold:
            msg += f" (reason: {prior_hold})"
        print(msg, file=sys.stderr)

    lock_fh = acquire_send_lock(root, name)
    try:
        turn = next_turn_number(root, name)

        print(f"[coroutine] resuming '{name}' turn={turn} model={model}...", file=sys.stderr)
        events = run_claude(root, make_payload(content), model, resume_uuid=uuid)
        save_turn(root, name, turn, events)

        text = extract_text(events)
        result = extract_result(events)
        signal = extract_yield(text)

        print(text)
        cost = result["total_cost_usd"] if result else 0
        print(f"\n[coroutine] turn={turn} cost=${cost:.4f}", file=sys.stderr)
        if signal:
            print(f"[coroutine] {signal}", file=sys.stderr)
        else:
            warn_missing_yield(turn)
    finally:
        lock_fh.close()


def cmd_status(root: Path, name: str | None):
    name = resolve_name(root, name)
    meta = load_meta(root, name)
    model = os.environ.get("CORO_MODEL", "").strip() or meta.get("model", DEFAULT_MODEL)
    held = check_send_lock(root, name)
    turn = last_turn_number(root, name)
    if turn < 0:
        die(f"no turns found for session '{name}'")
    path = turn_log_file(root, name, turn)
    events = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    text = extract_text(events)
    result = extract_result(events)
    signal = extract_yield(text)

    if result:
        inp, cr, cc, out = result_tokens(result)
        total_ctx = inp + cr + cc
        tokens_str = f"{total_ctx} in / {out} out  (last turn)"
    else:
        tokens_str = "-"

    total_cost = session_total_cost(root, name)

    is_held, hold_reason = read_hold(root, name)
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
    print(f"{'session:':{W}}{name}")
    print(f"{'sending:':{W}}{'yes' if held else 'no'}")
    print(f"{'hold:':{W}}{hold_str}")
    print(f"{'tokens:':{W}}{tokens_str}")
    print(f"{'cost:':{W}}${total_cost:.4f} total")
    print(f"{'yield:':{W}}{yield_str}")

    if not signal:
        warn_missing_yield(turn)

    if result:
        ctx_window = model_context(model)
        warn_threshold = token_warn_threshold(model, ctx_window)
        if total_ctx > warn_threshold:
            pct = int(total_ctx / ctx_window * 100)
            _warn(f"warning: last turn used {total_ctx} input tokens — {pct}% of {model} context ({ctx_window})")

    cost_threshold = cost_warn_threshold()
    if total_cost > cost_threshold:
        _warn(f"warning: session cost ${total_cost:.2f} exceeds threshold ${cost_threshold:.2f}")


def cmd_turns(root: Path, name: str | None):
    name = resolve_name(root, name)
    logs = sorted(turns_dir(root).glob(f"{name}-*.jsonl"))
    if not logs:
        die(f"no turns found for session '{name}'")
    meta = load_meta(root, name)
    model = meta.get("model", "?")
    print(f"session: {name}  model: {model}")
    for path in logs:
        turn = int(path.stem.rsplit("-", 1)[-1])
        events = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        result = extract_result(events)
        text = extract_text(events)
        cost = f"${result['total_cost_usd']:.4f}" if result else "?"
        if turn == 0:
            summary = "(preamble)"
        else:
            summary = extract_yield(text) or f"(no yield) {text.strip().splitlines()[-1][:60] if text.strip() else ''}"
        print(f"  turn {turn:03d}  cost={cost}  {summary}")
    total = session_total_cost(root, name)
    print(f"  total        ${total:.4f}")


def cmd_log(root: Path, name: str | None, turn: int | None):
    name = resolve_name(root, name)
    if turn is None:
        turn = last_turn_number(root, name)
        if turn < 0:
            die(f"no turns found for session '{name}'")
    path = turn_log_file(root, name, turn)
    if not path.exists():
        die(f"no log for turn {turn} of session '{name}'")
    print(path.read_text(), end="")


def cmd_use(root: Path, name: str):
    if not session_file(root, name).exists():
        die(f"no session '{name}' — run: coro create {name}")
    current_push(root, name)
    print(f"pushed '{name}'", file=sys.stderr)


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
    for name in reversed(stack):
        print(name)


def cmd_new_phase(args, root: Path):
    slug = args.slug
    todo_dir = root / ".cache" / "TODO"
    todo_dir.mkdir(parents=True, exist_ok=True)

    spec_path = todo_dir / f"phase-{slug}.md"
    kickoff_path = todo_dir / f"phase-{slug}-kickoff.md"

    if (spec_path.exists() or kickoff_path.exists()) and not args.force:
        die(f"phase '{slug}' files already exist; use --force to overwrite")

    template_dir = Path(__file__).parent.parent / "skills" / "coro-develop" / "templates"
    spec_template = (template_dir / "phase.md").read_text()
    kickoff_template = (template_dir / "phase-kickoff.md").read_text()

    spec_path.write_text(spec_template.replace("{slug}", slug))
    kickoff_path.write_text(kickoff_template.replace("{slug}", slug))

    print(f"created {spec_path}")
    print(f"created {kickoff_path}")


def cmd_hold(args, root: Path) -> int:
    name = resolve_name(root, args.name)
    load_session(root, name)
    reason = " ".join(r for r in (args.reason or []) if r.strip())
    write_hold(root, name, reason)
    print(f"held session '{name}'" + (f" — {reason}" if reason else ""))
    return 0


def cmd_unhold(args, root: Path) -> int:
    name = resolve_name(root, args.name)
    load_session(root, name)
    prior = clear_hold(root, name)
    if prior is None:
        print(f"session '{name}' was not held")
    else:
        print(f"unheld session '{name}'" + (f" (was: {prior})" if prior else ""))
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def die(msg: str):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        prog="coroutine",
        description="Stateful Claude session manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Runtime config via env: CORO_MODEL, CORO_PROJECT, CORO_ADD_DIRS, CORO_EFFORT",
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


if __name__ == "__main__":
    main()
