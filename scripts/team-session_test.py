#!/usr/bin/env python3
"""team-session 생성기의 실패 우선 검사."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "team-session.py"


def run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["TEAM_ROOT"] = str(root)
    return subprocess.run(
        ["python3", str(SCRIPT), *args],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
    )


class NewSessionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_new_writes_four_notes_and_one_board_line(self) -> None:
        result = run(self.root, "new", "12", "--session", "dev")
        self.assertEqual(result.returncode, 0, result.stderr)
        folder = self.root / ".team" / "sessions" / "12"
        for name in ("task.md", "state.md", "log.md", "result.md"):
            text = (folder / name).read_text(encoding="utf-8")
            self.assertIn("12", text)
        task = (folder / "task.md").read_text(encoding="utf-8")
        self.assertIn("목표", task)
        self.assertIn("완료 기준", task)
        self.assertIn("계획", task)
        state = (folder / "state.md").read_text(encoding="utf-8")
        self.assertIn("지금 상태", state)
        self.assertIn("결정", state)
        self.assertIn("다음 할 일", state)
        log = (folder / "log.md").read_text(encoding="utf-8")
        self.assertIn("시작", log)
        self.assertIn("push", log)
        result_text = (folder / "result.md").read_text(encoding="utf-8")
        self.assertIn("결과", result_text)
        self.assertIn("교훈 후보", result_text)
        board = (self.root / ".team" / "board.md").read_text(encoding="utf-8")
        self.assertEqual(board.count("\n- 12:"), 1)
        self.assertIn("담당 dev", board)
        self.assertIn("막힘", board)

    def test_second_work_does_not_clobber_the_first(self) -> None:
        first = run(self.root, "new", "12")
        self.assertEqual(first.returncode, 0, first.stderr)
        task = self.root / ".team" / "sessions" / "12" / "task.md"
        task.write_text(task.read_text(encoding="utf-8") + "\n손글씨\n", encoding="utf-8")
        before = task.read_bytes()
        second = run(self.root, "new", "13", "--session", "other")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(task.read_bytes(), before)
        self.assertTrue((self.root / ".team" / "sessions" / "13" / "state.md").is_file())
        board = (self.root / ".team" / "board.md").read_text(encoding="utf-8")
        self.assertIn("\n- 12:", board)
        self.assertIn("\n- 13:", board)
        self.assertEqual(board.count("\n- 12:"), 1)

    def test_date_id_is_accepted_and_escape_is_rejected(self) -> None:
        ok = run(self.root, "new", "2026-11-26-memo")
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertTrue((self.root / ".team" / "sessions" / "2026-11-26-memo" / "task.md").is_file())
        bad = run(self.root, "new", "../outside")
        self.assertNotEqual(bad.returncode, 0)
        self.assertFalse((self.root / "outside").exists())

    def test_parallel_new_keeps_both_board_lines(self) -> None:
        env = os.environ.copy()
        for i in range(25):
            root = self.root / f"try{i}"
            root.mkdir()
            env["TEAM_ROOT"] = str(root)
            first = subprocess.Popen(
                ["python3", str(SCRIPT), "new", "12", "--session", "s12"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            second = subprocess.Popen(
                ["python3", str(SCRIPT), "new", "13", "--session", "s13"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            err1 = first.communicate()[1]
            err2 = second.communicate()[1]
            self.assertEqual(first.returncode, 0, err1)
            self.assertEqual(second.returncode, 0, err2)
            board = (root / ".team" / "board.md").read_text(encoding="utf-8")
            self.assertEqual(board.count("\n- 12:"), 1, board)
            self.assertEqual(board.count("\n- 13:"), 1, board)


if __name__ == "__main__":
    unittest.main()
