#!/usr/bin/env python3
"""SessionStart 훅이 실패해도 세션 시작을 막지 않는지 보는 검사."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLAUDE = ROOT / ".claude" / "settings.json"
CODEX = ROOT / ".codex" / "hooks.json"
MATCHER = "startup|resume|clear|compact"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def command_of(payload: dict) -> str:
    group = payload["hooks"]["SessionStart"][0]
    hook = group["hooks"][0]
    return hook["command"]


class SessionHookTest(unittest.TestCase):
    def test_repo_hooks_call_start_context_and_do_not_block(self) -> None:
        for path in (CLAUDE, CODEX):
            payload = load(path)
            self.assertNotIn("PreCompact", payload["hooks"])
            group = payload["hooks"]["SessionStart"][0]
            self.assertEqual(group["matcher"], MATCHER)
            hook = group["hooks"][0]
            self.assertEqual(hook["type"], "command")
            self.assertEqual(hook["timeout"], 10)
            command = hook["command"]
            self.assertIn("scripts/team-session.py", command)
            self.assertIn("start-context", command)
            self.assertIn("|| true", command)
            self.assertNotIn("~/", command)
            self.assertNotIn("/home", command)
            self.assertNotIn(".codex/hooks.json", command)
        self.assertIn("CLAUDE_PROJECT_DIR", command_of(load(CLAUDE)))
        self.assertIn("git rev-parse --show-toplevel", command_of(load(CODEX)))

    def test_failed_hook_command_exits_zero(self) -> None:
        command = command_of(load(CLAUDE))
        root = Path(tempfile.mkdtemp())
        folder = root / ".team" / "sessions" / "45"
        folder.mkdir(parents=True)
        (folder / "state.md").write_bytes(b"\xff\xfe broken")
        (root / ".team" / "board.md").write_text(
            "- 45: 상태 시작, 담당 dev, 막힘 없음\n",
            encoding="utf-8",
        )
        env = os.environ.copy()
        env["TEAM_ROOT"] = str(root)
        env["CLAUDE_PROJECT_DIR"] = str(ROOT)
        env.pop("GITHUB_HEAD_REF", None)
        env["GITHUB_HEAD_REF"] = "work-45"
        done = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            shell=True,
            text=True,
            capture_output=True,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn('"continue": false', done.stdout)
        self.assertNotIn("continue: false", done.stdout)

    def test_hook_command_still_prints_context(self) -> None:
        command = command_of(load(CODEX))
        root = Path(tempfile.mkdtemp())
        folder = root / ".team" / "sessions" / "45"
        folder.mkdir(parents=True)
        (folder / "state.md").write_text("다음 할 일\n훅을 확인한다\n", encoding="utf-8")
        (root / ".team" / "board.md").write_text(
            "- 45: 상태 시작, 담당 dev, 막힘 없음\n",
            encoding="utf-8",
        )
        env = os.environ.copy()
        env["TEAM_ROOT"] = str(root)
        env.pop("GITHUB_HEAD_REF", None)
        env["GITHUB_HEAD_REF"] = "work-45"
        done = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            shell=True,
            text=True,
            capture_output=True,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("훅을 확인한다", done.stdout)
        self.assertNotIn("TASK", done.stdout)


if __name__ == "__main__":
    unittest.main()
