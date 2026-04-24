"""Unit tests for the model registry + resolve().

Covers every alias, every effort permutation, [1m] suffix handling, unknown
slug pass-through, dated snapshot substring fallback, and CLAUDE_CODE_DISABLE_1M_CONTEXT
env-dependent warnings.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Registry structure
# ---------------------------------------------------------------------------

def test_registry_has_three_models(coro_module):
    assert len(coro_module.REGISTRY) == 3
    ids = {m.id for m in coro_module.REGISTRY}
    assert ids == {"claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5"}


@pytest.mark.parametrize(
    "mid, ctx, ext, max_out, default_effort",
    [
        ("claude-opus-4-7",   200_000, 1_000_000, 128_000, "xhigh"),
        ("claude-sonnet-4-6", 200_000, 1_000_000,  64_000, "high"),
        ("claude-haiku-4-5",  200_000, None,       64_000, None),
    ],
)
def test_registry_entries_correct(coro_module, mid, ctx, ext, max_out, default_effort):
    spec = next(m for m in coro_module.REGISTRY if m.id == mid)
    assert spec.context_window == ctx
    assert spec.extended_context == ext
    assert spec.max_output == max_out
    if default_effort is None:
        assert spec.default_effort is None
    else:
        assert spec.default_effort.value == default_effort


# ---------------------------------------------------------------------------
# Happy-path alias + id resolution
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "arg, expected_spec_id, expected_effort",
    [
        ("opus",              "claude-opus-4-7",   "xhigh"),
        ("best",              "claude-opus-4-7",   "xhigh"),
        ("sonnet",            "claude-sonnet-4-6", "high"),
        ("haiku",             "claude-haiku-4-5",  None),
        ("claude-opus-4-7",   "claude-opus-4-7",   "xhigh"),
        ("claude-sonnet-4-6", "claude-sonnet-4-6", "high"),
        ("claude-haiku-4-5",  "claude-haiku-4-5",  None),
    ],
)
def test_resolve_aliases_and_ids(coro_module, arg, expected_spec_id, expected_effort):
    r = coro_module.resolve(arg)
    assert r.spec is not None
    assert r.spec.id == expected_spec_id
    if expected_effort is None:
        assert r.effort is None
    else:
        assert r.effort.value == expected_effort
    assert r.claude_arg == arg                      # never rewritten
    assert r.extended is False
    assert r.warnings == ()


# ---------------------------------------------------------------------------
# [1m] suffix handling
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "arg, expected_spec_id, expected_ctx",
    [
        ("opus[1m]",   "claude-opus-4-7",   1_000_000),
        ("sonnet[1m]", "claude-sonnet-4-6", 1_000_000),
        ("haiku[1m]",  "claude-haiku-4-5",    200_000),   # no extended → base
    ],
)
def test_resolve_1m_suffix(coro_module, arg, expected_spec_id, expected_ctx):
    r = coro_module.resolve(arg)
    assert r.spec.id == expected_spec_id
    assert r.extended is True
    assert r.claude_arg == arg
    assert coro_module.resolved_context_window(r) == expected_ctx


def test_1m_suffix_with_disable_env_warns(coro_module, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_DISABLE_1M_CONTEXT", "1")
    r = coro_module.resolve("sonnet[1m]")
    assert any("CLAUDE_CODE_DISABLE_1M_CONTEXT" in w for w in r.warnings)


def test_1m_suffix_no_disable_no_warning(coro_module, monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_DISABLE_1M_CONTEXT", raising=False)
    r = coro_module.resolve("sonnet[1m]")
    assert r.warnings == ()


# ---------------------------------------------------------------------------
# Effort handling
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "model, effort_input, expected_effort, expected_warn_count",
    [
        # Happy paths — spec supports the requested effort
        ("opus",   "low",    "low",    0),
        ("opus",   "medium", "medium", 0),
        ("opus",   "high",   "high",   0),
        ("opus",   "xhigh",  "xhigh",  0),
        ("opus",   "max",    "max",    0),
        ("sonnet", "low",    "low",    0),
        ("sonnet", "high",   "high",   0),
        ("sonnet", "max",    "max",    0),
        # Sonnet doesn't support xhigh → pass through with warning
        ("sonnet", "xhigh",  "xhigh",  1),
        # Haiku has no effort support → drop with warning
        ("haiku", "low",    None, 1),
        ("haiku", "high",   None, 1),
        ("haiku", "max",    None, 1),
        # Invalid effort → fall back to spec default, warn
        ("sonnet", "bogus",  "high", 1),
        ("opus",   "BOGUS",  "xhigh", 1),
        # Empty/whitespace → treated as unset, spec default applies
        ("sonnet", "",       "high", 0),
        ("sonnet", "   ",    "high", 0),
        ("haiku",  "",       None,   0),
    ],
)
def test_resolve_effort_behavior(coro_module, model, effort_input, expected_effort, expected_warn_count):
    r = coro_module.resolve(model, effort_input)
    actual = r.effort.value if r.effort else None
    assert actual == expected_effort
    assert len(r.warnings) == expected_warn_count


def test_resolve_effort_case_insensitive(coro_module):
    r = coro_module.resolve("opus", "HIGH")
    assert r.effort.value == "high"
    assert r.warnings == ()


# ---------------------------------------------------------------------------
# Unknown slug pass-through
# ---------------------------------------------------------------------------

def test_resolve_unknown_slug(coro_module):
    r = coro_module.resolve("claude-nebula-5-0")
    assert r.spec is None
    assert r.claude_arg == "claude-nebula-5-0"
    assert r.extended is False
    assert any("unknown model" in w for w in r.warnings)


def test_resolve_unknown_slug_with_effort(coro_module):
    """Unknown + valid effort passes both through."""
    r = coro_module.resolve("claude-nebula-5-0", "high")
    assert r.spec is None
    assert r.effort.value == "high"


def test_resolve_unknown_slug_with_invalid_effort(coro_module):
    """Unknown + invalid effort: invalid effort dropped, unknown warning."""
    r = coro_module.resolve("claude-nebula-5-0", "bogus")
    assert r.spec is None
    assert r.effort is None                          # no spec to provide default
    assert len(r.warnings) == 2                      # unknown + invalid


def test_resolve_unknown_with_1m(coro_module):
    r = coro_module.resolve("claude-nebula-5-0[1m]")
    assert r.spec is None
    assert r.extended is True


# ---------------------------------------------------------------------------
# Dated snapshot substring fallback
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "dated_id, expected_spec_id",
    [
        ("claude-opus-4-7-20260101",   "claude-opus-4-7"),
        ("claude-sonnet-4-6-20250929", "claude-sonnet-4-6"),
        ("claude-haiku-4-5-20251001",  "claude-haiku-4-5"),
    ],
)
def test_resolve_dated_snapshot_substring_match(coro_module, dated_id, expected_spec_id):
    r = coro_module.resolve(dated_id)
    assert r.spec is not None
    assert r.spec.id == expected_spec_id
    assert r.claude_arg == dated_id                  # verbatim pass-through


# ---------------------------------------------------------------------------
# resolved_context_window
# ---------------------------------------------------------------------------

def test_resolved_context_window_none_spec(coro_module):
    r = coro_module.resolve("unknown-slug")
    assert coro_module.resolved_context_window(r) == 200_000


def test_resolved_context_window_with_extended(coro_module):
    r = coro_module.resolve("opus[1m]")
    assert coro_module.resolved_context_window(r) == 1_000_000


def test_resolved_context_window_without_extended(coro_module):
    r = coro_module.resolve("opus")
    assert coro_module.resolved_context_window(r) == 200_000


def test_resolved_context_window_haiku_1m_falls_back(coro_module):
    """Haiku has no extended_context; [1m] suffix falls back to base 200k."""
    r = coro_module.resolve("haiku[1m]")
    assert coro_module.resolved_context_window(r) == 200_000
