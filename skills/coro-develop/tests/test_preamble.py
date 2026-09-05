"""Unit tests for _load_preamble (reads role/worker.md)."""
from __future__ import annotations

import pytest


def test_preamble_loads_worker_role(coro_module):
    """Preamble should start with /salience on and include the worker role heading."""
    preamble = coro_module._load_preamble()
    assert preamble.startswith("/salience on\n\n")
    assert "# Worker Role" in preamble
    assert preamble.rstrip().endswith("Acknowledge this role and wait for your first instruction.")


def test_preamble_does_not_include_protocol(coro_module):
    """Worker role is self-contained; protocol.md content should not appear."""
    preamble = coro_module._load_preamble()
    # Protocol.md-specific headings that should NOT be in the worker preamble
    assert "# Coroutine Protocol" not in preamble
    assert "## Architecture" not in preamble
    assert "## Session storage" not in preamble
    assert "## Orchestrator FSM" not in preamble


def test_preamble_missing_role_doc_raises(coro_module, monkeypatch, tmp_path):
    """If SKILL.md exists (skill root resolves) but role/worker.md is missing,
    _load_preamble raises CoroError via die()."""
    skill_root = tmp_path / "broken-skill"
    (skill_root / "scripts").mkdir(parents=True)
    (skill_root / "SKILL.md").write_text("# sentinel")
    fake_script = skill_root / "scripts" / "coroutine.py"
    fake_script.write_text("# placeholder")
    # role/worker.md intentionally absent

    monkeypatch.setattr(coro_module, "__file__", str(fake_script))
    with pytest.raises(coro_module.CoroError, match="role/worker.md not found"):
        coro_module._load_preamble()
