"""Red tests for REQ-045 — Claude Code plugin distributes Pragma invisibly.

v0.2.0 thesis. Pragma's point is to be invisible. The user types
intent in plain English; Claude (driven by the plugin's hooks and
skill) calls pragma start, watches edits, drives the gate. The user
never types `pragma slice activate`.

Plugin shape (Claude Code convention):
- plugin/.claude-plugin/plugin.json — plugin manifest.
- plugin/hooks/hooks.json — declares which hooks fire and the
  shell scripts that run.
- plugin/hooks/*.sh — shell scripts that read $CLAUDE_PROJECT_DIR
  and call `pragma` accordingly.
- plugin/skills/pragma/SKILL.md — concise rules teaching Claude
  the loop.
- .claude-plugin/marketplace.json at repo root — so users install
  via `/plugin install pragma@joncik91/pragma`.

These tests assert the files exist and pass minimal sanity checks.
End-to-end "user installs plugin and Claude drives the loop" is a
manual integration test (Claude Code itself isn't part of the
pytest harness).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from pragma_sdk import set_permutation, trace

REPO_ROOT = Path(__file__).resolve().parents[4]


@trace("REQ-045")
def _assert_plugin_manifest_valid() -> None:
    manifest_path = REPO_ROOT / "plugin" / ".claude-plugin" / "plugin.json"
    assert manifest_path.exists(), (
        f"plugin manifest must exist at {manifest_path}; got missing file"
    )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload.get("name") == "pragma", (
        f"plugin manifest name must be 'pragma'; got {payload!r}"
    )
    assert payload.get("version", "").strip(), (
        f"plugin manifest must declare a non-empty version; got {payload!r}"
    )


@trace("REQ-045")
def _assert_marketplace_manifest_present() -> None:
    market_path = REPO_ROOT / ".claude-plugin" / "marketplace.json"
    assert market_path.exists(), (
        f"marketplace manifest must exist at {market_path} so users can "
        "`/plugin install pragma@joncik91/pragma`; got missing file"
    )
    payload = json.loads(market_path.read_text(encoding="utf-8"))
    plugins = payload.get("plugins") or []
    assert any(p.get("name") == "pragma" for p in plugins), (
        f"marketplace.json must reference the pragma plugin; got {payload!r}"
    )


@trace("REQ-045")
def _assert_session_start_hook_emits_state(tmp_path: Path) -> None:
    """Run the SessionStart hook against a real Pragma project and
    confirm it emits active-slice context to stdout/stderr.
    """
    # Bootstrap a Pragma project via `pragma start`.
    subprocess.run(
        [
            str(REPO_ROOT / ".venv" / "bin" / "pragma"),
            "start",
            "User can log in",
        ],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    # Run the SessionStart hook.
    hook_path = REPO_ROOT / "plugin" / "hooks" / "session-start.sh"
    assert hook_path.exists(), (
        f"SessionStart hook script must exist at {hook_path}; got missing file"
    )
    result = subprocess.run(
        ["bash", str(hook_path)],
        cwd=str(tmp_path),
        env={
            "PATH": "/usr/bin:/bin:" + str(REPO_ROOT / ".venv" / "bin"),
            "CLAUDE_PROJECT_DIR": str(tmp_path),
        },
        capture_output=True,
        text=True,
    )
    output = (result.stdout or "") + (result.stderr or "")
    assert result.returncode == 0, (
        f"SessionStart hook must exit 0; rc={result.returncode}, output:\n{output}"
    )
    assert "M01.S1" in output, (
        f"SessionStart hook must surface the active slice id (M01.S1); got:\n{output}"
    )
    assert "LOCKED" in output, (
        f"SessionStart hook must surface the current gate state; got:\n{output}"
    )


@trace("REQ-045")
def _assert_skill_md_present() -> None:
    skill_path = REPO_ROOT / "plugin" / "skills" / "pragma" / "SKILL.md"
    assert skill_path.exists(), f"skill file must exist at {skill_path}; got missing file"
    content = skill_path.read_text(encoding="utf-8")
    assert "pragma start" in content, (
        f"SKILL.md must instruct Claude to call `pragma start`; got:\n{content}"
    )
    # Skill should also tell Claude what NOT to do (edit pragma.yaml directly).
    assert "pragma.yaml" in content, (
        f"SKILL.md must mention pragma.yaml so Claude knows the manifest is sacred; got:\n{content}"
    )


def test_req_045_plugin_manifest_valid() -> None:
    with set_permutation("plugin_manifest_valid"):
        _assert_plugin_manifest_valid()


def test_req_045_marketplace_manifest_present() -> None:
    with set_permutation("marketplace_manifest_present"):
        _assert_marketplace_manifest_present()


def test_req_045_session_start_hook_emits_state(tmp_path: Path) -> None:
    with set_permutation("session_start_hook_emits_state"):
        _assert_session_start_hook_emits_state(tmp_path)


def test_req_045_skill_md_present() -> None:
    with set_permutation("skill_md_present"):
        _assert_skill_md_present()
