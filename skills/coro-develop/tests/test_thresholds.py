"""Unit tests for token / cost threshold calculations."""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# token_warn_threshold
# ---------------------------------------------------------------------------

def test_token_warn_default_80pct_sonnet_base(coro_module, monkeypatch):
    """Default ratio is 0.80; sonnet base = 200k → threshold 160_000."""
    monkeypatch.delenv("CORO_TOKEN_WARN_RATIO", raising=False)
    monkeypatch.delenv("CORO_TOKEN_WARN", raising=False)
    r = coro_module.resolve("sonnet")
    assert coro_module.token_warn_threshold(r) == 160_000


def test_token_warn_default_80pct_sonnet_1m(coro_module, monkeypatch):
    monkeypatch.delenv("CORO_TOKEN_WARN_RATIO", raising=False)
    monkeypatch.delenv("CORO_TOKEN_WARN", raising=False)
    r = coro_module.resolve("sonnet[1m]")
    assert coro_module.token_warn_threshold(r) == 800_000


def test_token_warn_ratio_override(coro_module, monkeypatch):
    monkeypatch.setenv("CORO_TOKEN_WARN_RATIO", "0.50")
    monkeypatch.delenv("CORO_TOKEN_WARN", raising=False)
    r = coro_module.resolve("sonnet")
    assert coro_module.token_warn_threshold(r) == 100_000


def test_token_warn_absolute_override_wins(coro_module, monkeypatch):
    """CORO_TOKEN_WARN overrides ratio."""
    monkeypatch.setenv("CORO_TOKEN_WARN_RATIO", "0.80")
    monkeypatch.setenv("CORO_TOKEN_WARN", "50000")
    r = coro_module.resolve("sonnet")
    assert coro_module.token_warn_threshold(r) == 50_000


def test_token_warn_explicit_ctx_window_arg(coro_module, monkeypatch):
    """Explicit ctx_window arg bypasses spec lookup."""
    monkeypatch.delenv("CORO_TOKEN_WARN_RATIO", raising=False)
    monkeypatch.delenv("CORO_TOKEN_WARN", raising=False)
    r = coro_module.resolve("sonnet")
    assert coro_module.token_warn_threshold(r, ctx_window=500_000) == 400_000


def test_token_warn_unknown_model_uses_200k_fallback(coro_module, monkeypatch):
    monkeypatch.delenv("CORO_TOKEN_WARN_RATIO", raising=False)
    monkeypatch.delenv("CORO_TOKEN_WARN", raising=False)
    r = coro_module.resolve("unknown-slug")
    assert coro_module.token_warn_threshold(r) == 160_000  # 80% of 200k fallback


# ---------------------------------------------------------------------------
# cost_warn_threshold
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "model, expected",
    [
        ("opus",   50.00),
        ("sonnet", 25.00),
        ("haiku",  10.00),
    ],
)
def test_cost_warn_per_model_default(coro_module, monkeypatch, model, expected):
    monkeypatch.delenv("CORO_COST_WARN", raising=False)
    r = coro_module.resolve(model)
    assert coro_module.cost_warn_threshold(r) == expected


def test_cost_warn_unknown_model_uses_25(coro_module, monkeypatch):
    monkeypatch.delenv("CORO_COST_WARN", raising=False)
    r = coro_module.resolve("unknown-slug")
    assert coro_module.cost_warn_threshold(r) == 25.00


def test_cost_warn_env_override(coro_module, monkeypatch):
    monkeypatch.setenv("CORO_COST_WARN", "7.50")
    for m in ("opus", "sonnet", "haiku"):
        r = coro_module.resolve(m)
        assert coro_module.cost_warn_threshold(r) == 7.50


def test_cost_warn_env_override_with_decimal(coro_module, monkeypatch):
    monkeypatch.setenv("CORO_COST_WARN", "0.99")
    r = coro_module.resolve("haiku")
    assert coro_module.cost_warn_threshold(r) == 0.99


# ---------------------------------------------------------------------------
# _max_budget_usd env reader
# ---------------------------------------------------------------------------

def test_max_budget_usd_unset(coro_module, monkeypatch):
    monkeypatch.delenv("CORO_MAX_BUDGET_USD", raising=False)
    assert coro_module._max_budget_usd() is None


def test_max_budget_usd_set(coro_module, monkeypatch):
    monkeypatch.setenv("CORO_MAX_BUDGET_USD", "5.00")
    assert coro_module._max_budget_usd() == "5.00"


def test_max_budget_usd_empty_treated_as_unset(coro_module, monkeypatch):
    monkeypatch.setenv("CORO_MAX_BUDGET_USD", "")
    assert coro_module._max_budget_usd() is None


def test_max_budget_usd_whitespace_treated_as_unset(coro_module, monkeypatch):
    monkeypatch.setenv("CORO_MAX_BUDGET_USD", "   ")
    assert coro_module._max_budget_usd() is None
