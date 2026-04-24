"""Unit tests for slug generation, parsing, and name resolution."""
from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# make_slug
# ---------------------------------------------------------------------------

def test_make_slug_format(coro_module):
    slug = coro_module.make_slug("foo", time_fn=lambda: 1234567890)
    assert slug == "foo_1234567890"


def test_make_slug_truncates_float_to_int(coro_module):
    slug = coro_module.make_slug("x", time_fn=lambda: 1234567890.789)
    assert slug == "x_1234567890"


def test_make_slug_default_is_real_wall_clock(coro_module):
    """Without time_fn, uses current time.time() — verify it's in a plausible range."""
    import time
    slug = coro_module.make_slug("probe")
    parsed = coro_module.parse_slug(slug)
    assert parsed is not None
    name, ts = parsed
    assert name == "probe"
    now = int(time.time())
    assert abs(ts - now) < 5                        # within 5s of wall-clock


def test_make_slug_preserves_hyphens_in_name(coro_module):
    slug = coro_module.make_slug("phase-1-implementation", time_fn=lambda: 100)
    assert slug == "phase-1-implementation_100"


# ---------------------------------------------------------------------------
# parse_slug
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "slug, expected",
    [
        ("foo_1234567890",              ("foo", 1234567890)),
        ("phase-1_1745123456",          ("phase-1", 1745123456)),
        ("phase-1-impl_99",             ("phase-1-impl", 99)),
        ("a_b_c_100",                   ("a_b_c", 100)),     # greedy: split on final _<digits>
        ("my_session_9999999999999",    ("my_session", 9999999999999)),
    ],
)
def test_parse_slug_valid(coro_module, slug, expected):
    assert coro_module.parse_slug(slug) == expected


@pytest.mark.parametrize(
    "slug",
    [
        "no-digits",                    # no trailing _<digits>
        "foo_",                         # trailing underscore, no digits
        "foo_bar",                      # trailing non-digit
        "_123",                         # empty name part (regex uses .+, so at least one char)
        "foo_abc",
        "foo1234",                      # no underscore separator
    ],
)
def test_parse_slug_invalid(coro_module, slug):
    assert coro_module.parse_slug(slug) is None


def test_parse_make_slug_roundtrip(coro_module):
    for name in ["foo", "phase-1", "a-b-c-d", "my_session"]:
        slug = coro_module.make_slug(name, time_fn=lambda: 1700000000)
        parsed = coro_module.parse_slug(slug)
        assert parsed is not None
        # Note: "my_session" parses as ("my", "session_1700000000"[0:10]) — the
        # parser splits on final _<digits>. So roundtrip gives the full "my_session"
        # as name because parse_slug is greedy on the name part.
        recovered_name, recovered_ts = parsed
        assert recovered_name == name
        assert recovered_ts == 1700000000


# ---------------------------------------------------------------------------
# list_slugs
# ---------------------------------------------------------------------------

def test_list_slugs_empty(coro_module, tmp_project):
    # No sessions yet
    assert coro_module.list_slugs(tmp_project) == []


def test_list_slugs_no_coro_dir(coro_module, tmp_path):
    # .cache/coro/ doesn't exist
    assert coro_module.list_slugs(tmp_path) == []


def test_list_slugs_finds_valid_sessions(coro_module, tmp_project):
    # Create three fake session dirs with uuid files
    for slug in ["foo_100", "bar_200", "baz_150"]:
        d = tmp_project / ".cache" / "coro" / slug
        d.mkdir(parents=True)
        (d / "uuid").write_text("fake-uuid\n")
    # Create one dir without a uuid (should be skipped)
    (tmp_project / ".cache" / "coro" / "incomplete").mkdir()
    # And a non-directory file (should be skipped)
    (tmp_project / ".cache" / "coro" / "loose-file").write_text("noise")

    slugs = coro_module.list_slugs(tmp_project)
    assert slugs == ["bar_200", "baz_150", "foo_100"]  # sorted


# ---------------------------------------------------------------------------
# resolve_slug
# ---------------------------------------------------------------------------

def _make_session(root: Path, slug: str, coro_module):
    coro_module.save_session(root, slug, f"uuid-{slug}", "sonnet")


def test_resolve_slug_exact_match(coro_module, tmp_project):
    _make_session(tmp_project, "phase-1_100", coro_module)
    assert coro_module.resolve_slug(tmp_project, "phase-1_100") == "phase-1_100"


def test_resolve_slug_single_name_match(coro_module, tmp_project):
    _make_session(tmp_project, "phase-1_100", coro_module)
    assert coro_module.resolve_slug(tmp_project, "phase-1") == "phase-1_100"


def test_resolve_slug_no_match_fails_fast(coro_module, tmp_project):
    with pytest.raises(coro_module.CoroError, match="no session matches"):
        coro_module.resolve_slug(tmp_project, "phase-99")


def test_resolve_slug_ambiguous_fails_fast(coro_module, tmp_project):
    _make_session(tmp_project, "phase-1_100", coro_module)
    _make_session(tmp_project, "phase-1_200", coro_module)

    with pytest.raises(coro_module.CoroError, match="ambiguous") as exc:
        coro_module.resolve_slug(tmp_project, "phase-1")
    # Error message should list both candidate slugs
    msg = str(exc.value)
    assert "phase-1_100" in msg
    assert "phase-1_200" in msg


def test_resolve_slug_distinguishes_different_names(coro_module, tmp_project):
    _make_session(tmp_project, "phase-1_100", coro_module)
    _make_session(tmp_project, "phase-2_100", coro_module)
    assert coro_module.resolve_slug(tmp_project, "phase-1") == "phase-1_100"
    assert coro_module.resolve_slug(tmp_project, "phase-2") == "phase-2_100"


def test_resolve_slug_exact_wins_over_name_match(coro_module, tmp_project):
    """If a session's slug happens to equal a name+something, exact match wins."""
    _make_session(tmp_project, "phase-1_100", coro_module)
    # Exact: "phase-1_100" — resolves directly, no name resolution path
    assert coro_module.resolve_slug(tmp_project, "phase-1_100") == "phase-1_100"


# ---------------------------------------------------------------------------
# resolve_session_arg (CURRENT fallback)
# ---------------------------------------------------------------------------

def test_resolve_session_arg_with_explicit(coro_module, tmp_project):
    _make_session(tmp_project, "foo_100", coro_module)
    assert coro_module.resolve_session_arg(tmp_project, "foo") == "foo_100"


def test_resolve_session_arg_falls_back_to_current(coro_module, tmp_project):
    _make_session(tmp_project, "foo_100", coro_module)
    coro_module.current_push(tmp_project, "foo_100")
    assert coro_module.resolve_session_arg(tmp_project, None) == "foo_100"


def test_resolve_session_arg_no_arg_empty_current_fails(coro_module, tmp_project):
    with pytest.raises(coro_module.CoroError, match="CURRENT stack is empty"):
        coro_module.resolve_session_arg(tmp_project, None)


def test_resolve_session_arg_explicit_bad_name_fails_even_with_current(coro_module, tmp_project):
    """Explicit arg is always resolved via resolve_slug, even if CURRENT is populated."""
    _make_session(tmp_project, "foo_100", coro_module)
    coro_module.current_push(tmp_project, "foo_100")
    with pytest.raises(coro_module.CoroError, match="no session matches"):
        coro_module.resolve_session_arg(tmp_project, "bar")


# ---------------------------------------------------------------------------
# Slug regex edge cases
# ---------------------------------------------------------------------------

def test_slug_with_numeric_name_part(coro_module):
    """Names starting with digits: the greedy regex includes them in name part."""
    assert coro_module.parse_slug("123_456") == ("123", 456)


def test_slug_regex_greedy_on_name(coro_module):
    """Multiple underscores: split at the final _<digits>."""
    assert coro_module.parse_slug("a_b_c_1_2_100") == ("a_b_c_1_2", 100)
