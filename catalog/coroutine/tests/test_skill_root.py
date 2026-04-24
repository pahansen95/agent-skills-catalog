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


def test_skill_root_finds_via_symlink_fallback(coro_module, tmp_path, monkeypatch):
    """Source-tree shape: coroutine.py is at catalog/<domain>/src/coroutine.py,
    which is not an ancestor of any SKILL.md. The skill in
    catalog/<domain>/skills/<name>/ symlinks scripts/coroutine.py back to
    src/coroutine.py; _skill_root() finds it via the sibling scan."""
    domain = tmp_path / "domain"
    src = domain / "src"
    src.mkdir(parents=True)
    real_script = src / "coroutine.py"
    real_script.write_text("# placeholder")

    skill = domain / "skills" / "my-skill"
    (skill / "scripts").mkdir(parents=True)
    (skill / "SKILL.md").write_text("# sentinel")
    (skill / "scripts" / "coroutine.py").symlink_to(real_script)

    monkeypatch.setattr(coro_module, "__file__", str(real_script))
    assert coro_module._skill_root() == skill


def test_skill_root_prefers_walk_up_over_sibling(coro_module, tmp_path, monkeypatch):
    """If both a walk-up SKILL.md and a sibling skill exist, walk-up wins —
    matches the installed-tree invariant (flat, self-contained)."""
    skill_root = tmp_path / "installed-skill"
    (skill_root / "scripts").mkdir(parents=True)
    (skill_root / "SKILL.md").write_text("# walk-up sentinel")
    fake_script = skill_root / "scripts" / "coroutine.py"
    fake_script.write_text("# placeholder")

    # Also create a sibling skills/ dir that would be a valid fallback.
    sibling = skill_root / "skills" / "other"
    (sibling / "scripts").mkdir(parents=True)
    (sibling / "SKILL.md").write_text("# sibling sentinel")
    (sibling / "scripts" / "coroutine.py").symlink_to(fake_script)

    monkeypatch.setattr(coro_module, "__file__", str(fake_script))
    # Walk-up finds skill_root first.
    assert coro_module._skill_root() == skill_root


def test_skill_root_raises_when_no_sentinel(coro_module, tmp_path, monkeypatch):
    """No SKILL.md anywhere in the ancestry or sibling skills/ → CoroError."""
    orphan = tmp_path / "orphan" / "coroutine.py"
    orphan.parent.mkdir(parents=True)
    orphan.write_text("# placeholder")

    monkeypatch.setattr(coro_module, "__file__", str(orphan))
    with pytest.raises(coro_module.CoroError, match="SKILL.md sentinel not found"):
        coro_module._skill_root()


def test_skill_root_ignores_siblings_without_matching_symlink(coro_module, tmp_path, monkeypatch):
    """A sibling skill that symlinks some *other* coroutine.py must not match."""
    domain = tmp_path / "domain"
    src = domain / "src"
    src.mkdir(parents=True)
    real_script = src / "coroutine.py"
    real_script.write_text("# placeholder")

    decoy_src = tmp_path / "decoy"
    decoy_src.mkdir()
    decoy_script = decoy_src / "coroutine.py"
    decoy_script.write_text("# decoy")

    skill = domain / "skills" / "my-skill"
    (skill / "scripts").mkdir(parents=True)
    (skill / "SKILL.md").write_text("# sentinel")
    # Symlinks to the decoy, not to our real_script.
    (skill / "scripts" / "coroutine.py").symlink_to(decoy_script)

    monkeypatch.setattr(coro_module, "__file__", str(real_script))
    with pytest.raises(coro_module.CoroError, match="SKILL.md sentinel not found"):
        coro_module._skill_root()


def test_skill_root_in_real_source_tree(coro_module):
    """Smoke: against the actual checked-in source tree, _skill_root() resolves
    to catalog/coroutine/skills/coro-develop/."""
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
