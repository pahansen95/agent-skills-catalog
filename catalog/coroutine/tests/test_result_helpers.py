"""Unit tests for result-event helpers."""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# extract_result
# ---------------------------------------------------------------------------

def test_extract_result_found(coro_module):
    events = [
        {"type": "system"},
        {"type": "assistant", "message": {"content": []}},
        {"type": "result", "total_cost_usd": 0.05, "is_error": False},
    ]
    r = coro_module.extract_result(events)
    assert r is not None
    assert r["total_cost_usd"] == 0.05


def test_extract_result_missing(coro_module):
    events = [{"type": "system"}, {"type": "assistant", "message": {"content": []}}]
    assert coro_module.extract_result(events) is None


def test_extract_result_first_wins(coro_module):
    """If multiple result events (shouldn't happen, but), return first."""
    events = [
        {"type": "result", "total_cost_usd": 0.01},
        {"type": "result", "total_cost_usd": 0.02},
    ]
    assert coro_module.extract_result(events)["total_cost_usd"] == 0.01


# ---------------------------------------------------------------------------
# result_tokens
# ---------------------------------------------------------------------------

def test_result_tokens_all_fields(coro_module):
    result = {
        "usage": {
            "input_tokens": 100,
            "cache_read_input_tokens": 500,
            "cache_creation_input_tokens": 300,
            "output_tokens": 50,
        }
    }
    assert coro_module.result_tokens(result) == (100, 500, 300, 50)


def test_result_tokens_missing_fields_default_zero(coro_module):
    result = {"usage": {}}
    assert coro_module.result_tokens(result) == (0, 0, 0, 0)


def test_result_tokens_no_usage_key(coro_module):
    assert coro_module.result_tokens({}) == (0, 0, 0, 0)


# ---------------------------------------------------------------------------
# extract_context_window
# ---------------------------------------------------------------------------

def test_extract_context_window_from_modelusage(coro_module):
    result = {
        "modelUsage": {
            "claude-sonnet-4-6[1m]": {"contextWindow": 1_000_000, "maxOutputTokens": 64_000}
        }
    }
    assert coro_module.extract_context_window(result) == 1_000_000


def test_extract_context_window_multiple_entries_returns_one(coro_module):
    """Multiple models (e.g. haiku bg + sonnet primary): returns any non-zero one."""
    result = {
        "modelUsage": {
            "claude-haiku-4-5-20251001": {"contextWindow": 200_000},
            "claude-sonnet-4-6":         {"contextWindow": 1_000_000},
        }
    }
    cw = coro_module.extract_context_window(result)
    assert cw in (200_000, 1_000_000)                  # dict order dep; either is acceptable


def test_extract_context_window_empty(coro_module):
    assert coro_module.extract_context_window({}) is None
    assert coro_module.extract_context_window({"modelUsage": {}}) is None


def test_extract_context_window_missing_field(coro_module):
    result = {"modelUsage": {"some-model": {"maxOutputTokens": 64_000}}}
    assert coro_module.extract_context_window(result) is None


# ---------------------------------------------------------------------------
# extract_max_output
# ---------------------------------------------------------------------------

def test_extract_max_output_from_modelusage(coro_module):
    result = {
        "modelUsage": {
            "claude-opus-4-7": {"contextWindow": 1_000_000, "maxOutputTokens": 128_000}
        }
    }
    assert coro_module.extract_max_output(result) == 128_000


def test_extract_max_output_empty(coro_module):
    assert coro_module.extract_max_output({}) is None
    assert coro_module.extract_max_output({"modelUsage": {}}) is None


def test_extract_max_output_zero_ignored(coro_module):
    """Zero maxOutputTokens is treated as unset."""
    result = {"modelUsage": {"m": {"maxOutputTokens": 0}}}
    assert coro_module.extract_max_output(result) is None


# ---------------------------------------------------------------------------
# budget_exceeded
# ---------------------------------------------------------------------------

def test_budget_exceeded_true(coro_module):
    assert coro_module.budget_exceeded({"subtype": "error_max_budget_usd"}) is True


def test_budget_exceeded_false_success(coro_module):
    assert coro_module.budget_exceeded({"subtype": "success"}) is False


def test_budget_exceeded_false_other_error(coro_module):
    assert coro_module.budget_exceeded({"subtype": "error_other", "is_error": True}) is False


def test_budget_exceeded_none_result(coro_module):
    assert coro_module.budget_exceeded(None) is False


def test_budget_exceeded_empty_result(coro_module):
    assert coro_module.budget_exceeded({}) is False
