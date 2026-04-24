"""Hypothesis property tests for invariants that should hold across inputs."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import assume, given, settings, strategies as st


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Names: non-empty strings without the slug trailing-digit pattern. Letters,
# digits, and hyphens — matches realistic human-assigned names.
valid_name_chars = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="-"),
    min_size=1,
    max_size=20,
)
# Filter out names that would themselves look slug-shaped (trailing _<digits>)
# and empty strings. Also disallow leading '-' to avoid argparse confusion.
valid_names = valid_name_chars.filter(lambda s: s and not s.startswith("-"))

valid_ts = st.integers(min_value=1_000_000_000, max_value=9_999_999_999)


# ---------------------------------------------------------------------------
# 1. parse_slug(make_slug(name, ts)) round-trip
# ---------------------------------------------------------------------------

@given(name=valid_names, ts=valid_ts)
def test_parse_slug_roundtrips(coro_module, name, ts):
    """For any valid name + any plausible unix-seconds timestamp:
    parse_slug(make_slug(name, t=ts)) == (name, ts)."""
    slug = coro_module.make_slug(name, time_fn=lambda: ts)
    parsed = coro_module.parse_slug(slug)
    assert parsed is not None
    recovered_name, recovered_ts = parsed
    assert recovered_name == name
    assert recovered_ts == ts


# ---------------------------------------------------------------------------
# 2. resolve_slug is deterministic and honest
# ---------------------------------------------------------------------------

@settings(deadline=None)  # filesystem IO can be slow on some runners
@given(
    names=st.lists(valid_names, min_size=1, max_size=5, unique=True),
    ts_base=valid_ts,
)
def test_resolve_slug_unique_names_always_resolve(coro_module, tmp_path_factory, names, ts_base):
    """If all session names are distinct, each shorthand resolves to its slug."""
    project = tmp_path_factory.mktemp("prop_unique")
    (project / ".cache" / "coro").mkdir(parents=True, exist_ok=True)

    # Create one session per name with monotonically-increasing timestamps
    slugs = {}
    for i, name in enumerate(names):
        slug = f"{name}_{ts_base + i}"
        coro_module.save_session(project, slug, f"uuid-{i}", "sonnet")
        slugs[name] = slug

    # Each name resolves to its unique slug
    for name, expected_slug in slugs.items():
        assert coro_module.resolve_slug(project, name) == expected_slug

    # Full slug always resolves to itself
    for expected_slug in slugs.values():
        assert coro_module.resolve_slug(project, expected_slug) == expected_slug


@settings(deadline=None)
@given(
    name=valid_names,
    count=st.integers(min_value=2, max_value=5),
    ts_base=valid_ts,
)
def test_resolve_slug_duplicate_names_always_fail(coro_module, tmp_path_factory, name, count, ts_base):
    """When multiple sessions share a name, shorthand always raises CoroError."""
    project = tmp_path_factory.mktemp("prop_dup")
    (project / ".cache" / "coro").mkdir(parents=True, exist_ok=True)

    slugs = []
    for i in range(count):
        slug = f"{name}_{ts_base + i}"
        coro_module.save_session(project, slug, f"uuid-{i}", "sonnet")
        slugs.append(slug)

    # Shorthand must fail fast
    with pytest.raises(coro_module.CoroError, match="ambiguous"):
        coro_module.resolve_slug(project, name)

    # Each full slug still resolves to itself
    for slug in slugs:
        assert coro_module.resolve_slug(project, slug) == slug


# ---------------------------------------------------------------------------
# 3. CURRENT stack is LIFO
# ---------------------------------------------------------------------------

@settings(deadline=None)
@given(
    items=st.lists(valid_names, min_size=1, max_size=20),
    ts_base=valid_ts,
)
def test_current_stack_is_lifo(coro_module, tmp_path_factory, items, ts_base):
    """Push sequence, pop gets items in reverse order."""
    project = tmp_path_factory.mktemp("prop_stack")
    (project / ".cache" / "coro").mkdir(parents=True, exist_ok=True)

    slugs = [f"{n}_{ts_base + i}" for i, n in enumerate(items)]
    for slug in slugs:
        coro_module.current_push(project, slug)

    # Top-to-bottom listing == insertion order
    assert coro_module.current_list(project) == slugs

    # Pop returns in LIFO order
    popped = []
    while True:
        x = coro_module.current_pop(project)
        if x is None:
            break
        popped.append(x)

    assert popped == list(reversed(slugs))
    # Stack is empty after pops
    assert coro_module.current_top(project) is None


# ---------------------------------------------------------------------------
# 4. Turn numbering is monotonic
# ---------------------------------------------------------------------------

@settings(deadline=None)
@given(
    n_turns=st.integers(min_value=1, max_value=15),
    ts=valid_ts,
)
def test_turn_numbering_monotonic(coro_module, tmp_path_factory, n_turns, ts):
    """Saving N turns via next_turn_number() + save_turn gives sequence 0..N-1."""
    project = tmp_path_factory.mktemp("prop_turns")
    (project / ".cache" / "coro").mkdir(parents=True, exist_ok=True)
    slug = f"sess_{ts}"
    coro_module.save_session(project, slug, "u", "sonnet")

    numbers = []
    for _ in range(n_turns):
        n = coro_module.next_turn_number(project, slug)
        numbers.append(n)
        coro_module.save_turn(project, slug, n, [{"type": "result", "total_cost_usd": 0.01}])

    assert numbers == list(range(n_turns))
    assert coro_module.last_turn_number(project, slug) == n_turns - 1


# ---------------------------------------------------------------------------
# 5. YIELD extraction stable under trailing whitespace
# ---------------------------------------------------------------------------

yield_statuses = st.sampled_from(["DONE", "BLOCKED", "FAILED", "RUNNING", "CHECK"])
summary_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("Ll", "Lu", "Nd", "Zs"),
        whitelist_characters=" .,:;",
    ),
    min_size=1,
    max_size=60,
)
trailing_ws = st.text(alphabet=" \t\n", min_size=0, max_size=10)
leading_ws_lines = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Nd", "Zs", "Cc"), blacklist_characters=":"),
    max_size=40,
)


@given(status=yield_statuses, summary=summary_text, trailing=trailing_ws, noise=leading_ws_lines)
def test_yield_extraction_stable_under_whitespace_noise(coro_module, status, summary, trailing, noise):
    """YIELD extraction returns the same logical signal regardless of trailing
    whitespace, blank lines after, or non-yield noise before."""
    yield_line = f"YIELD: {status} | {summary}"
    text = f"{noise}\n{yield_line}{trailing}"

    extracted = coro_module.extract_yield(text)
    assert extracted is not None
    # Extracted line should start with YIELD: (case-insensitive), have correct status
    assert extracted.upper().startswith(f"YIELD: {status}")
    # Summary content preserved
    assert summary.strip() in extracted or summary in extracted


# ---------------------------------------------------------------------------
# 6. Session cost = sum of per-turn costs
# ---------------------------------------------------------------------------

cost_values = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)


@settings(deadline=None)
@given(
    costs=st.lists(cost_values, min_size=0, max_size=10),
    ts=valid_ts,
)
def test_session_total_cost_equals_sum(coro_module, tmp_path_factory, costs, ts):
    """session_total_cost equals the sum of per-turn total_cost_usd values."""
    project = tmp_path_factory.mktemp("prop_cost")
    (project / ".cache" / "coro").mkdir(parents=True, exist_ok=True)
    slug = f"sess_{ts}"
    coro_module.save_session(project, slug, "u", "sonnet")

    for i, c in enumerate(costs):
        coro_module.save_turn(
            project, slug, i, [{"type": "result", "total_cost_usd": c}]
        )

    total = coro_module.session_total_cost(project, slug)
    assert total == pytest.approx(sum(costs), abs=1e-9)
