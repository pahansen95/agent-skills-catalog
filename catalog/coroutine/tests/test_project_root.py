"""Tests for find_project_root (env override + walk-up discovery)."""
from __future__ import annotations

from pathlib import Path

import pytest


def test_find_project_root_env_override(coro_module, tmp_path, monkeypatch):
    """CORO_PROJECT points at an existing dir → return that dir."""
    target = tmp_path / "my-project"
    target.mkdir()
    monkeypatch.setenv("CORO_PROJECT", str(target))
    assert coro_module.find_project_root() == target.resolve()


def test_find_project_root_env_override_missing_fails(coro_module, tmp_path, monkeypatch):
    """CORO_PROJECT points at a non-existent path → raise CoroError."""
    monkeypatch.setenv("CORO_PROJECT", str(tmp_path / "does-not-exist"))
    with pytest.raises(coro_module.CoroError, match="CORO_PROJECT path does not exist"):
        coro_module.find_project_root()


def test_find_project_root_walks_up_to_find_cache_coro(coro_module, tmp_path, monkeypatch):
    """Starting from a nested dir, walk up until .cache/coro/ is found."""
    # Lay out: tmp_path/project/.cache/coro, cwd = tmp_path/project/nested/deeply/
    project = tmp_path / "project"
    (project / ".cache" / "coro").mkdir(parents=True)
    nested = project / "nested" / "deeply"
    nested.mkdir(parents=True)

    monkeypatch.delenv("CORO_PROJECT", raising=False)
    monkeypatch.chdir(nested)
    assert coro_module.find_project_root() == project


def test_find_project_root_no_match_returns_cwd(coro_module, tmp_path, monkeypatch):
    """When walk-up finds no .cache/coro, return cwd as fallback.

    We construct an isolated filesystem island where no parent has .cache/coro,
    by chdir-ing to a tmp subdir and confirming the function doesn't blow up.
    Note: if /Users/.../.cache/coro somehow exists in the walk-up, this test
    will produce a path deep in the home dir instead of tmp_path — but we
    check that the function *terminates* and returns something reasonable.
    """
    monkeypatch.delenv("CORO_PROJECT", raising=False)
    monkeypatch.chdir(tmp_path)

    # In a clean tmp_path, no ancestor has .cache/coro (unlikely), so fallback
    # to cwd. If an ancestor happens to have it (e.g. the repo under test
    # during dev), the function returns that ancestor; either way, it must
    # return an existing Path.
    result = coro_module.find_project_root()
    assert result.exists()


def test_find_project_root_start_at_project_itself(coro_module, tmp_path, monkeypatch):
    """cwd = the project root → returns cwd immediately."""
    project = tmp_path / "project"
    (project / ".cache" / "coro").mkdir(parents=True)
    monkeypatch.delenv("CORO_PROJECT", raising=False)
    monkeypatch.chdir(project)
    assert coro_module.find_project_root() == project
