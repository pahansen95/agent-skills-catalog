"""Tests for _skill_root — sentinel-based skill directory discovery."""
from __future__ import annotations

from pathlib import Path

import pytest


def test_skill_root_finds_sentinel_via_walk_up(coro_module, tmp_path, monkeypatch):
    """Installed-tree shape: coroutine.py sits at <skill_root>/scripts/coroutine.py;
    SKILL.md one level up is discovered by walk-up."""
    skill_root = tmp_path / "installed-skill"
    (skill_root / "scripts").mkdir(parents=True)
    (skill_root / "SKILL.md").write_text("# sentinel")
    fake_script = skill_root / "scripts" / "coroutine.py"
    fake_script.write_text("# placeholder")

    monkeypatch.setattr(coro_module, "__file__", str(fake_script))
    assert coro_module._skill_root() == skill_root


def test_skill_root_finds_self_contained_skill_through_view_symlink(
    coro_module, tmp_path, monkeypatch
):
    """A view symlink resolves to the self-contained skill directory."""
    skill = tmp_path / "registry" / "coro-develop"
    (skill / "scripts").mkdir(parents=True)
    (skill / "SKILL.md").write_text("# sentinel")
    real_script = skill / "scripts" / "coroutine.py"
    real_script.write_text("# placeholder")

    view = tmp_path / "view" / "coro-develop"
    view.parent.mkdir()
    view.symlink_to(skill, target_is_directory=True)

    monkeypatch.setattr(coro_module, "__file__", str(view / "scripts" / "coroutine.py"))
    assert coro_module._skill_root() == skill


def test_skill_root_prefers_nearest_sentinel(coro_module, tmp_path, monkeypatch):
    """The nearest SKILL.md sentinel wins during upward discovery."""
    skill_root = tmp_path / "installed-skill"
    (skill_root / "scripts").mkdir(parents=True)
    (skill_root / "SKILL.md").write_text("# walk-up sentinel")
    fake_script = skill_root / "scripts" / "coroutine.py"
    fake_script.write_text("# placeholder")

    outer_root = skill_root.parent
    (outer_root / "SKILL.md").write_text("# outer sentinel")

    monkeypatch.setattr(coro_module, "__file__", str(fake_script))
    # Upward discovery finds skill_root before its parent.
    assert coro_module._skill_root() == skill_root


def test_skill_root_raises_when_no_sentinel(coro_module, tmp_path, monkeypatch):
    """No SKILL.md anywhere in the ancestry raises CoroError."""
    orphan = tmp_path / "orphan" / "coroutine.py"
    orphan.parent.mkdir(parents=True)
    orphan.write_text("# placeholder")

    monkeypatch.setattr(coro_module, "__file__", str(orphan))
    with pytest.raises(coro_module.CoroError, match="SKILL.md sentinel not found"):
        coro_module._skill_root()


def test_skill_root_rejects_script_outside_skill(coro_module, tmp_path, monkeypatch):
    """A script without an ancestor SKILL.md is rejected."""
    real_script = tmp_path / "orphan" / "coroutine.py"
    real_script.parent.mkdir()
    real_script.write_text("# placeholder")

    monkeypatch.setattr(coro_module, "__file__", str(real_script))
    with pytest.raises(coro_module.CoroError, match="SKILL.md sentinel not found"):
        coro_module._skill_root()


def test_skill_root_in_real_source_tree(coro_module):
    """Smoke: against the checked-in self-contained skill directory."""
    root = coro_module._skill_root()
    assert (root / "SKILL.md").is_file()
    assert root.name == "coro-develop"


def test_load_preamble_uses_skill_root(coro_module):
    """_load_preamble must resolve role/worker.md via _skill_root, not a fixed hop."""
    preamble = coro_module._load_preamble()
    assert "# Worker Role" in preamble


def test_cmd_new_phase_uses_skill_root(coro_module, tmp_project):
    """cmd_new_phase reads templates from _skill_root() / templates/."""
    import argparse
    coro_module.cmd_new_phase(
        argparse.Namespace(slug="root-test", force=False), tmp_project
    )
    spec = (tmp_project / ".cache" / "TODO" / "phase-root-test.md").read_text()
    assert "root-test" in spec
    assert "{slug}" not in spec
