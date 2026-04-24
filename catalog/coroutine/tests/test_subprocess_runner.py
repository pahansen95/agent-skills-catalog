"""Tests for the production SubprocessRunner.

Uses `python -c` as a harmless subprocess to emit canned stream-json, which
validates the full Popen plumbing (stdin write, stdout line iteration,
stderr capture, return code handling) without invoking claude.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest


def _py_argv(body: str) -> list[str]:
    """Build argv for a one-shot python subprocess that runs `body`."""
    return [sys.executable, "-c", body]


def test_subprocess_runner_yields_parsed_events(coro_module, tmp_path):
    runner = coro_module.SubprocessRunner()
    body = (
        "import json, sys;"
        "print(json.dumps({'type': 'system', 'session_id': 'abc'}));"
        "print(json.dumps({'type': 'assistant', 'msg': 'hi'}));"
        "print(json.dumps({'type': 'result', 'ok': True}))"
    )
    events = list(runner.run_stream_json(
        _py_argv(body), cwd=tmp_path, env=os.environ.copy(), stdin_payload=""
    ))
    assert len(events) == 3
    assert events[0]["session_id"] == "abc"
    assert events[1]["type"] == "assistant"
    assert events[2]["type"] == "result"


def test_subprocess_runner_skips_blank_lines(coro_module, tmp_path):
    runner = coro_module.SubprocessRunner()
    body = (
        "import json;"
        "print();"
        "print(json.dumps({'a': 1}));"
        "print();"
        "print();"
        "print(json.dumps({'a': 2}));"
        "print()"
    )
    events = list(runner.run_stream_json(
        _py_argv(body), cwd=tmp_path, env=os.environ.copy(), stdin_payload=""
    ))
    assert events == [{"a": 1}, {"a": 2}]


def test_subprocess_runner_skips_malformed_json(coro_module, tmp_path):
    runner = coro_module.SubprocessRunner()
    body = (
        "import json;"
        "print('not json');"
        "print(json.dumps({'valid': True}));"
        "print('also not json {');"
        "print(json.dumps({'also_valid': True}))"
    )
    events = list(runner.run_stream_json(
        _py_argv(body), cwd=tmp_path, env=os.environ.copy(), stdin_payload=""
    ))
    assert events == [{"valid": True}, {"also_valid": True}]


def test_subprocess_runner_passes_stdin_payload(coro_module, tmp_path):
    runner = coro_module.SubprocessRunner()
    # Child reads stdin and echoes it back as a JSON event
    body = (
        "import sys, json;"
        "data = sys.stdin.read();"
        "print(json.dumps({'stdin_received': data}))"
    )
    events = list(runner.run_stream_json(
        _py_argv(body), cwd=tmp_path, env=os.environ.copy(), stdin_payload="hello from test"
    ))
    assert events == [{"stdin_received": "hello from test"}]


def test_subprocess_runner_passes_cwd(coro_module, tmp_path):
    runner = coro_module.SubprocessRunner()
    body = (
        "import os, json;"
        "print(json.dumps({'cwd': os.getcwd()}))"
    )
    events = list(runner.run_stream_json(
        _py_argv(body), cwd=tmp_path, env=os.environ.copy(), stdin_payload=""
    ))
    # Use resolve() on both sides because macOS may route through /private/var
    assert Path(events[0]["cwd"]).resolve() == tmp_path.resolve()


def test_subprocess_runner_passes_env(coro_module, tmp_path):
    runner = coro_module.SubprocessRunner()
    body = (
        "import os, json;"
        "print(json.dumps({'mark': os.environ.get('CORO_TEST_MARKER', 'MISSING')}))"
    )
    env = os.environ.copy()
    env["CORO_TEST_MARKER"] = "xyz-42"
    events = list(runner.run_stream_json(
        _py_argv(body), cwd=tmp_path, env=env, stdin_payload=""
    ))
    assert events == [{"mark": "xyz-42"}]


def test_subprocess_runner_non_zero_exit_warns(coro_module, tmp_path, capsys):
    runner = coro_module.SubprocessRunner()
    body = (
        "import json, sys;"
        "print(json.dumps({'ok': True}));"
        "sys.stderr.write('something went wrong\\n');"
        "sys.exit(1)"
    )
    events = list(runner.run_stream_json(
        _py_argv(body), cwd=tmp_path, env=os.environ.copy(), stdin_payload=""
    ))
    # Events yielded before exit are still returned
    assert events == [{"ok": True}]
    # Warning surfaced on stderr
    captured = capsys.readouterr()
    assert "claude exited with code 1" in captured.err
    assert "something went wrong" in captured.err


def test_subprocess_runner_zero_exit_no_warning(coro_module, tmp_path, capsys):
    runner = coro_module.SubprocessRunner()
    body = "import json; print(json.dumps({'ok': True}))"
    list(runner.run_stream_json(
        _py_argv(body), cwd=tmp_path, env=os.environ.copy(), stdin_payload=""
    ))
    captured = capsys.readouterr()
    assert "claude exited" not in captured.err


def test_subprocess_runner_truncates_long_stderr(coro_module, tmp_path, capsys):
    runner = coro_module.SubprocessRunner()
    # Emit >500 chars on stderr with non-zero exit
    body = (
        "import sys;"
        "sys.stderr.write('x' * 2000);"
        "sys.exit(1)"
    )
    list(runner.run_stream_json(
        _py_argv(body), cwd=tmp_path, env=os.environ.copy(), stdin_payload=""
    ))
    captured = capsys.readouterr()
    # Truncated to 500 chars
    assert len(captured.err.strip().split("\n")[-1]) < 700  # some overhead for prefix
