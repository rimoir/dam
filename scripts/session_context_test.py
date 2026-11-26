#!/usr/bin/env python3
"""start-context가 열린 현황과 상태만 내는지 보는 검사."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from session_context import (
    INJECT_LIMIT,
    SHORTEN_LINE,
    STATE_LIMIT,
    render_start_context,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "team-session.py"


def write_note(root: Path, work_id: str, state: str, log: str) -> None:
    folder = root / ".team" / "sessions" / work_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "state.md").write_text(state, encoding="utf-8")
    (folder / "log.md").write_text(log, encoding="utf-8")
    (folder / "task.md").write_text(f"TASK-SECRET-{work_id}\n", encoding="utf-8")
    (folder / "result.md").write_text(f"RESULT-SECRET-{work_id}\n", encoding="utf-8")


def board_line(work_id: str, status: str, block: str = "없음") -> str:
    return f"- {work_id}: 상태 {status}, 담당 dev, 막힘 {block}"


def write_board(root: Path, lines: list[str]) -> None:
    path = root / ".team" / "board.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(
        [
            "# 작업 현황",
            "",
            "한 줄 형식: `- <작업ID>: 상태 <상태>, 담당 <세션>, 막힘 <이유>`",
            "",
            *lines,
            "",
        ]
    )
    path.write_text(body, encoding="utf-8")


def run_start(root: Path, *args: str, head_ref: str | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["TEAM_ROOT"] = str(root)
    env.pop("GITHUB_HEAD_REF", None)
    if head_ref is not None:
        env["GITHUB_HEAD_REF"] = head_ref
    return subprocess.run(
        ["python3", str(SCRIPT), "start-context", *args],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
    )


class StartContextTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.state = "다음 할 일\n계획을 쓴다\n"
        self.log = "".join(f"L{i:02d}\n" for i in range(20))
        write_note(self.root, "43", self.state, self.log)
        write_note(self.root, "44", "다른 작업 상태\n", "OTHER-LOG-HEAD\n")
        notes = self.root / ".team" / "sessions" / "12"
        notes.mkdir(parents=True)
        (notes / "notes.md").write_text("NOTES-SECRET\n", encoding="utf-8")
        write_board(
            self.root,
            [
                board_line("43", "시작"),
                board_line("44", "진행"),
                board_line("30", "완료"),
                board_line("12", "닫힘"),
                board_line("7", "시작", "완료 대기"),
            ],
        )
        write_note(self.root, "7", "일곱 상태\n", "L07\n")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_emits_open_lines_and_one_state(self) -> None:
        text = render_start_context(self.root, "cursor/work-43", switch=False)
        self.assertIn(board_line("43", "시작"), text)
        self.assertIn(board_line("44", "진행"), text)
        self.assertIn(board_line("7", "시작", "완료 대기"), text)
        self.assertIn(self.state, text)
        self.assertNotIn("다른 작업 상태", text)
        self.assertNotIn(board_line("30", "완료"), text)
        self.assertNotIn(board_line("12", "닫힘"), text)
        self.assertNotIn("한 줄 형식", text)
        self.assertNotIn("TASK-SECRET", text)
        self.assertNotIn("RESULT-SECRET", text)
        self.assertNotIn("NOTES-SECRET", text)
        self.assertNotIn("L19", text)
        self.assertLessEqual(len(text), INJECT_LIMIT)
        self.assertLessEqual(len(self.state), STATE_LIMIT)

    def test_missing_issue_number_emits_open_lines_only(self) -> None:
        text = render_start_context(self.root, "cursor/no-number", switch=False)
        self.assertIn(board_line("43", "시작"), text)
        self.assertNotIn(self.state, text)
        self.assertNotIn("다른 작업 상태", text)
        self.assertNotIn("L19", text)

    def test_non_digit_suffix_does_not_select_an_issue(self) -> None:
        text = render_start_context(self.root, "cursor/start-context-43-ed7f", switch=False)
        self.assertIn(board_line("43", "시작"), text)
        self.assertNotIn(self.state, text)

    def test_closed_branch_issue_does_not_add_its_state(self) -> None:
        text = render_start_context(self.root, "topic-30", switch=False)
        self.assertNotIn(board_line("30", "완료"), text)
        self.assertNotIn(self.state, text)
        self.assertIn(board_line("44", "진행"), text)

    def test_switch_adds_only_the_last_five_log_lines(self) -> None:
        text = render_start_context(self.root, "work-43", switch=True)
        tail = "".join(f"L{i:02d}\n" for i in range(15, 20))
        self.assertIn(tail, text)
        self.assertNotIn("L14\n", text)
        self.assertNotIn("OTHER-LOG-HEAD", text)
        self.assertIn(self.state, text)
        short = self.root / ".team" / "sessions" / "43" / "log.md"
        short.write_text("A\nB\nC\n", encoding="utf-8")
        short_text = render_start_context(self.root, "work-43", switch=True)
        self.assertIn("A\nB\nC\n", short_text)

    def test_state_over_char_limit_is_one_shorten_line(self) -> None:
        marker = "가" * (STATE_LIMIT + 1)
        write_note(self.root, "43", marker, self.log)
        text = render_start_context(self.root, "work-43", switch=False)
        self.assertEqual(text, SHORTEN_LINE)
        self.assertEqual(text.count("\n"), 1)
        self.assertNotIn("가", text)
        self.assertNotIn(board_line("43", "시작"), text)
        self.assertLessEqual(len(text), INJECT_LIMIT)

    def test_state_at_char_limit_is_kept(self) -> None:
        body = "가" * STATE_LIMIT
        self.assertGreater(len(body.encode("utf-8")), STATE_LIMIT)
        write_note(self.root, "43", body, self.log)
        text = render_start_context(self.root, "work-43", switch=False)
        self.assertIn(body, text)
        self.assertLessEqual(len(text), INJECT_LIMIT)
        self.assertNotEqual(text, SHORTEN_LINE)

    def test_injection_over_limit_is_one_shorten_line(self) -> None:
        long_block = "나" * 3000
        write_board(
            self.root,
            [board_line("43", "시작", long_block)],
        )
        write_note(self.root, "43", "STATE-KEEP\n", self.log)
        self.assertLess(len("STATE-KEEP\n"), STATE_LIMIT)
        text = render_start_context(self.root, "work-43", switch=True)
        self.assertGreater(len(long_block) + len("STATE-KEEP\n"), INJECT_LIMIT)
        self.assertEqual(text, SHORTEN_LINE)
        self.assertNotIn("나", text)
        self.assertNotIn("STATE-KEEP", text)
        self.assertNotIn("L19", text)

    def test_missing_board_is_empty(self) -> None:
        bare = Path(self.tmp.name) / "bare"
        bare.mkdir()
        self.assertEqual(render_start_context(bare, "work-43", switch=True), "")

    def test_missing_state_file_keeps_open_lines(self) -> None:
        (self.root / ".team" / "sessions" / "43" / "state.md").unlink()
        text = render_start_context(self.root, "work-43", switch=False)
        self.assertIn(board_line("43", "시작"), text)
        self.assertNotIn("계획을 쓴다", text)
        self.assertNotEqual(text, SHORTEN_LINE)

    def test_cli_prints_open_line_and_state(self) -> None:
        result = run_start(self.root, head_ref="work-43")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(board_line("43", "시작"), result.stdout)
        self.assertIn(self.state, result.stdout)
        self.assertNotIn("L19", result.stdout)
        self.assertNotIn("TASK-SECRET", result.stdout)
        self.assertLessEqual(len(result.stdout), INJECT_LIMIT)

    def test_cli_over_limit_exits_zero_with_one_line(self) -> None:
        write_note(self.root, "43", "가" * (STATE_LIMIT + 1), self.log)
        result = run_start(self.root, head_ref="work-43")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, SHORTEN_LINE)
        self.assertEqual(result.stderr, "")

    def test_cli_git_branch_tip_selects_issue(self) -> None:
        git = subprocess.run(
            ["git", "init", "-b", "work-43"],
            cwd=self.root,
            text=True,
            capture_output=True,
        )
        self.assertEqual(git.returncode, 0, git.stderr)
        result = run_start(self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(self.state, result.stdout)
        self.assertNotIn("다른 작업 상태", result.stdout)


if __name__ == "__main__":
    unittest.main()
