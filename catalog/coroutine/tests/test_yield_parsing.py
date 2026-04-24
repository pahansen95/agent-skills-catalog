"""Unit tests for YIELD extraction and related event-stream parsers."""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# extract_yield
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text, expected",
    [
        ("YIELD: DONE | ok",                                "YIELD: DONE | ok"),
        ("blah\nYIELD: DONE | ok",                          "YIELD: DONE | ok"),
        ("line1\nline2\nYIELD: BLOCKED | need X",           "YIELD: BLOCKED | need X"),
        # Trailing whitespace / newlines stripped
        ("YIELD: DONE | ok\n",                              "YIELD: DONE | ok"),
        ("YIELD: DONE | ok\n\n\n",                          "YIELD: DONE | ok"),
        ("  YIELD: DONE | ok  ",                            "YIELD: DONE | ok"),
        # Case insensitive on "YIELD:" prefix
        ("yield: DONE | ok",                                "yield: DONE | ok"),
        ("Yield: DONE | ok",                                "Yield: DONE | ok"),
        # Scans from end; later YIELD wins if multiple
        ("YIELD: DONE | first\nYIELD: FAILED | later",      "YIELD: FAILED | later"),
        # Blank lines after YIELD don't confuse extractor
        ("YIELD: DONE | ok\n\n",                            "YIELD: DONE | ok"),
        # All 5 status types
        ("YIELD: DONE | x",     "YIELD: DONE | x"),
        ("YIELD: BLOCKED | x",  "YIELD: BLOCKED | x"),
        ("YIELD: FAILED | x",   "YIELD: FAILED | x"),
        ("YIELD: RUNNING | x",  "YIELD: RUNNING | x"),
        ("YIELD: CHECK | x",    "YIELD: CHECK | x"),
    ],
)
def test_extract_yield_positive_cases(coro_module, text, expected):
    assert coro_module.extract_yield(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "\n\n\n",
        "just some text\nwith no yield line",
        "YIELD DONE | no colon",           # missing colon
        "NOTYIELD: DONE | wrong prefix",   # "YIELD:" is a substring but line doesn't start with it
    ],
)
def test_extract_yield_negative_cases(coro_module, text):
    assert coro_module.extract_yield(text) is None


def test_extract_yield_finds_yield_anywhere_scanning_from_end(coro_module):
    """extract_yield scans lines from the end; returns the first YIELD it finds.

    If the YIELD line is not the last line (some trailing content appears after),
    the extractor still finds it while walking backwards.
    """
    text = "YIELD: DONE | first\nsome other content"
    assert coro_module.extract_yield(text) == "YIELD: DONE | first"


# ---------------------------------------------------------------------------
# extract_text
# ---------------------------------------------------------------------------

def test_extract_text_empty(coro_module):
    assert coro_module.extract_text([]) == ""


def test_extract_text_single_assistant(coro_module):
    events = [
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "hello"}]}},
    ]
    assert coro_module.extract_text(events) == "hello"


def test_extract_text_concatenates_multiple(coro_module):
    events = [
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "one "}]}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "two"}]}},
    ]
    assert coro_module.extract_text(events) == "one two"


def test_extract_text_concatenates_within_one_message(coro_module):
    events = [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "part1 "},
                    {"type": "text", "text": "part2"},
                ]
            },
        },
    ]
    assert coro_module.extract_text(events) == "part1 part2"


def test_extract_text_skips_non_text_blocks(coro_module):
    events = [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "before "},
                    {"type": "tool_use", "name": "Read", "input": {}},
                    {"type": "text", "text": "after"},
                ]
            },
        },
    ]
    assert coro_module.extract_text(events) == "before after"


def test_extract_text_skips_non_assistant_events(coro_module):
    events = [
        {"type": "system", "session_id": "abc"},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "only this"}]}},
        {"type": "result", "total_cost_usd": 0.01},
    ]
    assert coro_module.extract_text(events) == "only this"


# ---------------------------------------------------------------------------
# extract_session_id
# ---------------------------------------------------------------------------

def test_extract_session_id_found(coro_module):
    events = [
        {"type": "system", "session_id": "abc-123"},
        {"type": "assistant", "message": {"content": []}},
    ]
    assert coro_module.extract_session_id(events) == "abc-123"


def test_extract_session_id_missing(coro_module):
    events = [
        {"type": "assistant", "message": {"content": []}},
        {"type": "result", "total_cost_usd": 0.01},
    ]
    assert coro_module.extract_session_id(events) is None


def test_extract_session_id_first_system_wins(coro_module):
    events = [
        {"type": "system", "session_id": "first"},
        {"type": "system", "session_id": "second"},
    ]
    assert coro_module.extract_session_id(events) == "first"


# ---------------------------------------------------------------------------
# warn_missing_yield — just confirm it warns (stderr)
# ---------------------------------------------------------------------------

def test_warn_missing_yield_writes_to_stderr(coro_module, capsys):
    coro_module.warn_missing_yield(3)
    captured = capsys.readouterr()
    assert "turn 3" in captured.err
    assert "protocol violation" in captured.err
