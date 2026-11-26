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
    LOG_LINE_LIMIT,
    SHORTEN_LINE,
    STATE_LIMIT,
    limit_errors,
    render_start_context,
    rotate_log,
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

    def test_no_selected_work_names_none_and_open_count(self) -> None:
        text = render_start_context(self.root, "cursor/no-number", switch=False)
        self.assertIn("작업: 없음 (열린 줄 3)", text)
        self.assertNotIn(self.state, text)
        closed = render_start_context(self.root, "topic-30", switch=False)
        self.assertIn("작업: 없음 (열린 줄 3)", closed)
        self.assertNotIn(self.state, closed)

    def test_mode_line_is_carried_and_old_state_still_renders(self) -> None:
        write_note(self.root, "43", "모드: 조사\n다음 할 일\n", self.log)
        text = render_start_context(self.root, "work-43", switch=False)
        self.assertIn("모드: 조사\n", text)
        self.assertNotIn("작업: 없음", text)
        plain = render_start_context(self.root, "work-44", switch=False)
        self.assertIn("다른 작업 상태", plain)
        self.assertNotIn("작업: 없음", plain)

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

    def test_github_suffix_keeps_open_lines_and_drops_closed(self) -> None:
        write_board(
            self.root,
            [
                "- 43: 상태 진행, 담당 dev, 막힘 없음, GitHub 검토 중, 검사 통과",
                "- 44: 상태 시작, 담당 dev, 막힘 없음, GitHub 열림",
                "- 30: 상태 시작, 담당 dev, 막힘 없음, GitHub 닫힘",
                "- 12: 상태 시작, 담당 dev, 막힘 없음, GitHub 완료",
            ],
        )
        text = render_start_context(self.root, "work-43", switch=False)
        self.assertIn("GitHub 검토 중, 검사 통과", text)
        self.assertIn("GitHub 열림", text)
        self.assertIn(self.state, text)
        self.assertNotIn("GitHub 닫힘", text)
        self.assertNotIn("GitHub 완료", text)
        closed = render_start_context(self.root, "work-30", switch=False)
        self.assertNotIn(self.state, closed)
        self.assertNotIn("GitHub 닫힘", closed)

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

    def test_injection_at_limit_is_kept(self) -> None:
        state = "S" * 100 + "\n"
        prefix = "- 43: 상태 시작, 담당 dev, 막힘 "
        block_len = INJECT_LIMIT - len(prefix) - 1 - len(state)
        self.assertGreater(block_len, 0)
        self.assertLess(len(state), STATE_LIMIT)
        line = prefix + ("나" * block_len)
        write_board(self.root, [line])
        write_note(self.root, "43", state, self.log)
        kept = render_start_context(self.root, "work-43", switch=False)
        self.assertEqual(len(kept), INJECT_LIMIT)
        self.assertIn(state, kept)
        self.assertNotEqual(kept, SHORTEN_LINE)
        longer = prefix + ("나" * (block_len + 1))
        write_board(self.root, [longer])
        over = render_start_context(self.root, "work-43", switch=False)
        self.assertEqual(over, SHORTEN_LINE)

    def test_injection_over_limit_is_one_shorten_line(self) -> None:
        long_block = "나" * (INJECT_LIMIT + 1)
        write_board(
            self.root,
            [board_line("43", "시작", long_block)],
        )
        write_note(self.root, "43", "STATE-KEEP\n", self.log)
        self.assertLess(len("STATE-KEEP\n"), STATE_LIMIT)
        text = render_start_context(self.root, "work-43", switch=True)
        self.assertGreater(len(long_block), INJECT_LIMIT)
        self.assertEqual(text, SHORTEN_LINE)
        self.assertNotIn("나", text)
        self.assertNotIn("STATE-KEEP", text)
        self.assertNotIn("L19", text)

    def test_missing_board_says_none_and_zero_open_lines(self) -> None:
        bare = Path(self.tmp.name) / "bare"
        bare.mkdir()
        self.assertEqual(
            render_start_context(bare, "work-43", switch=True),
            "작업: 없음 (열린 줄 0)\n",
        )

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


class LogLimitTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _log(self, work_id: str, text: str) -> Path:
        folder = self.root / ".team" / "sessions" / work_id
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "log.md"
        path.write_text(text, encoding="utf-8")
        return path

    def test_rotate_moves_the_prefix_unchanged(self) -> None:
        original = "".join(f"L{i:04d}\n" for i in range(250))
        path = self._log("44", original)
        archive = rotate_log(self.root, "44")
        self.assertIsNotNone(archive)
        moved = archive.read_text(encoding="utf-8")
        live = path.read_text(encoding="utf-8")
        self.assertTrue(live.startswith("이전: log/001.md\n"))
        kept = live[len("이전: log/001.md\n") :]
        self.assertEqual(moved + kept, original)
        self.assertLessEqual(len(live.splitlines()), LOG_LINE_LIMIT)
        self.assertIn("L0000\n", moved)
        self.assertNotIn("L0000\n", live)
        self.assertIn("L0249\n", live)
        first = moved
        path.write_text(live + "".join(f"N{i:02d}\n" for i in range(10)), encoding="utf-8")
        second = rotate_log(self.root, "44")
        self.assertEqual(second.name, "002.md")
        self.assertEqual(archive.read_text(encoding="utf-8"), first)

    def test_rotate_under_limit_is_noop(self) -> None:
        original = "".join(f"L{i}\n" for i in range(10))
        path = self._log("44", original)
        self.assertIsNone(rotate_log(self.root, "44"))
        self.assertEqual(path.read_text(encoding="utf-8"), original)
        self.assertFalse((path.parent / "log").exists())

    def test_rotate_rejects_path_escape(self) -> None:
        outside = self.root / "outside.md"
        with self.assertRaises(SystemExit):
            rotate_log(self.root, "../outside")
        self.assertFalse(outside.exists())

    def test_check_fails_when_state_or_log_is_over_limit(self) -> None:
        folder = self.root / ".team" / "sessions" / "44"
        folder.mkdir(parents=True)
        (folder / "state.md").write_text("가" * (STATE_LIMIT + 1), encoding="utf-8")
        (folder / "log.md").write_text("줄\n" * (LOG_LINE_LIMIT + 1), encoding="utf-8")
        errors = "\n".join(limit_errors(self.root, "work-44"))
        self.assertIn("상태 파일이 2000자를 넘는다: 44", errors)
        self.assertIn("로그가 200줄을 넘는다: 44", errors)

    def test_check_ignores_notes_folder_and_passes_small_files(self) -> None:
        notes = self.root / ".team" / "sessions" / "12"
        notes.mkdir(parents=True)
        (notes / "notes.md").write_text("가" * (STATE_LIMIT + 50), encoding="utf-8")
        self._log("44", "한 줄\n")
        (self.root / ".team" / "sessions" / "44" / "state.md").write_text("다음 할 일\n", encoding="utf-8")
        self.assertEqual(limit_errors(self.root, "work-44"), [])

    def test_check_fails_when_injection_exceeds_limit(self) -> None:
        line = "- 44: 상태 시작, 담당 dev, 막힘 " + ("나" * (INJECT_LIMIT + 1))
        write_board(self.root, [line])
        self._log("44", "한 줄\n")
        (self.root / ".team" / "sessions" / "44" / "state.md").write_text("짧은 상태\n", encoding="utf-8")
        errors = "\n".join(limit_errors(self.root, "work-44"))
        self.assertIn(str(INJECT_LIMIT), errors)
        self.assertNotIn(str(STATE_LIMIT + 1), errors)

    def test_cli_rotate_and_check(self) -> None:
        original = "".join(f"L{i:04d}\n" for i in range(LOG_LINE_LIMIT + 5))
        path = self._log("44", original)
        (path.parent / "state.md").write_text("상태\n", encoding="utf-8")
        write_board(self.root, ["- 44: 상태 시작, 담당 dev, 막힘 없음"])
        env = os.environ.copy()
        env["TEAM_ROOT"] = str(self.root)
        env["GITHUB_HEAD_REF"] = "work-44"
        before = subprocess.run(
            ["python3", str(SCRIPT), "check"],
            cwd=self.root,
            env=env,
            text=True,
            capture_output=True,
        )
        self.assertEqual(before.returncode, 1, before.stdout)
        self.assertIn("44", before.stderr)
        rotated = subprocess.run(
            ["python3", str(SCRIPT), "rotate", "44"],
            cwd=self.root,
            env=env,
            text=True,
            capture_output=True,
        )
        self.assertEqual(rotated.returncode, 0, rotated.stderr)
        after = subprocess.run(
            ["python3", str(SCRIPT), "check"],
            cwd=self.root,
            env=env,
            text=True,
            capture_output=True,
        )
        self.assertEqual(after.returncode, 0, after.stderr)
        live = path.read_text(encoding="utf-8")
        archive = (path.parent / "log" / "001.md").read_text(encoding="utf-8")
        self.assertEqual(archive + live[len("이전: log/001.md\n") :], original)


class ModeCommandTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.state = "모드:\n\n# 상태 43\n\n## 다음 할 일\n\n계획을 쓴다\n"
        write_note(self.root, "43", self.state, "L\n")
        write_board(self.root, [board_line("43", "시작")])

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run(self, *args: str, head_ref: str | None) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["TEAM_ROOT"] = str(self.root)
        env.pop("GITHUB_HEAD_REF", None)
        if head_ref is not None:
            env["GITHUB_HEAD_REF"] = head_ref
        return subprocess.run(
            ["python3", str(SCRIPT), "mode", *args],
            cwd=self.root,
            env=env,
            text=True,
            capture_output=True,
        )

    def test_mode_changes_only_the_first_line(self) -> None:
        result = self._run("기능", head_ref="work-43")
        self.assertEqual(result.returncode, 0, result.stderr)
        text = (self.root / ".team" / "sessions" / "43" / "state.md").read_text(
            encoding="utf-8"
        )
        self.assertTrue(text.startswith("모드: 기능\n"))
        self.assertIn("## 다음 할 일\n\n계획을 쓴다\n", text)
        self.assertEqual(text.count("모드:"), 1)

    def test_unknown_mode_is_rejected(self) -> None:
        before = (self.root / ".team" / "sessions" / "43" / "state.md").read_text(
            encoding="utf-8"
        )
        result = self._run("자율", head_ref="work-43")
        self.assertNotEqual(result.returncode, 0)
        after = (self.root / ".team" / "sessions" / "43" / "state.md").read_text(
            encoding="utf-8"
        )
        self.assertEqual(after, before)

    def test_spaced_mode_name_is_one_argument(self) -> None:
        result = self._run("작은", "수정", head_ref="work-43")
        self.assertEqual(result.returncode, 0, result.stderr)
        text = (self.root / ".team" / "sessions" / "43" / "state.md").read_text(
            encoding="utf-8"
        )
        self.assertTrue(text.startswith("모드: 작은 수정\n"))
        self.assertIn("계획을 쓴다\n", text)

    def test_replaces_a_first_line_that_is_not_a_mode(self) -> None:
        path = self.root / ".team" / "sessions" / "43" / "state.md"
        path.write_text("# 상태 43\n\n## 지금 상태\nKEEP\n", encoding="utf-8")
        before_lines = path.read_text(encoding="utf-8").splitlines()
        result = self._run("기능", head_ref="work-43")
        self.assertEqual(result.returncode, 0, result.stderr)
        after = path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(after[0], "모드: 기능")
        self.assertEqual(after[1:], before_lines[1:])
        self.assertNotIn("# 상태 43", after)

    def test_keeps_crlf_on_the_other_lines(self) -> None:
        path = self.root / ".team" / "sessions" / "43" / "state.md"
        path.write_bytes("모드: 조사\r\n## 다음 할 일\r\nKEEP\r\n".encode())
        result = self._run("기능", head_ref="work-43")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            path.read_bytes(),
            "모드: 기능\r\n## 다음 할 일\r\nKEEP\r\n".encode(),
        )

    def test_no_open_work_creates_nothing(self) -> None:
        bare = Path(self.tmp.name) / "bare"
        bare.mkdir()
        env = os.environ.copy()
        env["TEAM_ROOT"] = str(bare)
        env["GITHUB_HEAD_REF"] = "cursor/no-number"
        result = subprocess.run(
            ["python3", str(SCRIPT), "mode", "조사"],
            cwd=bare,
            env=env,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((bare / ".team").exists())

    def test_command_bodies_match(self) -> None:
        claude = (ROOT / ".claude" / "commands" / "mode.md").read_bytes()
        codex = (ROOT / ".agents" / "skills" / "mode" / "SKILL.md").read_bytes()
        self.assertEqual(claude, codex)
        self.assertIn("python3 scripts/team-session.py mode".encode(), claude)


class LineLimitTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_check_fails_when_rule_or_command_is_too_long(self) -> None:
        from session_context import text_line_errors

        rule = self.root / ".rulesync" / "rules"
        rule.mkdir(parents=True)
        (rule / "dam.md").write_text("줄\n" * 51, encoding="utf-8")
        command = self.root / ".claude" / "commands"
        command.mkdir(parents=True)
        (command / "mode.md").write_text("줄\n" * 41, encoding="utf-8")
        skill = self.root / ".agents" / "skills" / "mode"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("다른\n", encoding="utf-8")
        errors = "\n".join(text_line_errors(self.root))
        self.assertIn("51", errors)
        self.assertIn("41", errors)
        self.assertIn("다르다", errors)
        proc = subprocess.run(
            ["python3", str(SCRIPT), "check"],
            cwd=self.root,
            env={**os.environ, "TEAM_ROOT": str(self.root)},
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("51", proc.stderr)


class CodeCleanTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=self.root, check=True)
        script = self.root / "scripts"
        script.mkdir()
        (script / "ok.py").write_text("x = 1\n", encoding="utf-8")
        subprocess.run(["git", "add", "scripts/ok.py"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.root, check=True, capture_output=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["TEAM_ROOT"] = str(self.root)
        return subprocess.run(
            ["python3", str(SCRIPT), *args],
            cwd=self.root,
            env=env,
            text=True,
            capture_output=True,
        )

    def test_code_clean_ignores_team_and_fails_on_code(self) -> None:
        notes = self.root / ".team" / "sessions" / "66"
        notes.mkdir(parents=True)
        (notes / "result.md").write_text("노트\n", encoding="utf-8")
        clean = self._run("code-clean")
        self.assertEqual(clean.returncode, 0, clean.stderr)
        (self.root / "scripts" / "ok.py").write_text("x = 2\n", encoding="utf-8")
        dirty = self._run("code-clean")
        self.assertEqual(dirty.returncode, 1, dirty.stdout)
        self.assertIn("scripts/ok.py", dirty.stderr)

    def test_result_is_written_only_for_an_open_task(self) -> None:
        from session_context import append_result

        bare = append_result(self.root, "cursor/no-number", "결론: 없다\n근거: 파일\n")
        self.assertFalse(bare)
        self.assertFalse((self.root / ".team").exists())
        write_board(self.root, [board_line("66", "시작")])
        folder = self.root / ".team" / "sessions" / "66"
        folder.mkdir(parents=True)
        (folder / "result.md").write_text("# 결과 66\n", encoding="utf-8")
        wrote = append_result(self.root, "work-66", "결론: 원인\n근거: 로그\n")
        self.assertTrue(wrote)
        text = (folder / "result.md").read_text(encoding="utf-8")
        self.assertIn("결론: 원인", text)
        self.assertIn("근거: 로그", text)


class PlanCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=self.root, check=True)
        (self.root / "scripts").mkdir()
        (self.root / "scripts" / "ok.py").write_text("x = 1\n", encoding="utf-8")
        subprocess.run(["git", "add", "scripts/ok.py"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.root, check=True, capture_output=True)
        folder = self.root / ".team" / "sessions" / "68"
        folder.mkdir(parents=True)
        (folder / "log.md").write_text("# 로그\n", encoding="utf-8")
        (folder / "task.md").write_text(
            "# 작업 68\n\n## 계획\n\n- 읽기 | 없음 | scripts/ok.py | python3 scripts/ok_test.py\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run(self) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["TEAM_ROOT"] = str(self.root)
        return subprocess.run(
            ["python3", str(SCRIPT), "plan-check", "68"],
            cwd=self.root,
            env=env,
            text=True,
            capture_output=True,
        )

    def test_complete_plan_passes(self) -> None:
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_check_names_the_unit(self) -> None:
        task = self.root / ".team" / "sessions" / "68" / "task.md"
        task.write_text("# 작업\n\n## 계획\n\n- 읽기 | 없음 | scripts/ok.py |\n", encoding="utf-8")
        result = self._run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("읽기", result.stderr)
        self.assertIn("검증", result.stderr)

    def test_code_change_before_go_fails(self) -> None:
        (self.root / "scripts" / "ok.py").write_text("x = 2\n", encoding="utf-8")
        result = self._run()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("scripts/ok.py", result.stderr)

    def test_long_plan_prints_shorten_notice(self) -> None:
        rows = "\n".join(
            f"- 단위{i} | 없음 | scripts/ok.py | python3 scripts/ok_test.py" for i in range(41)
        )
        task = self.root / ".team" / "sessions" / "68" / "task.md"
        task.write_text(f"# 작업\n\n## 계획\n\n{rows}\n", encoding="utf-8")
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("줄여라", result.stdout)


class GoScopeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=self.root, check=True)
        (self.root / "a.py").write_text("x = 1\n", encoding="utf-8")
        (self.root / "b.py").write_text("y = 1\n", encoding="utf-8")
        subprocess.run(["git", "add", "a.py", "b.py"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.root, check=True, capture_output=True)
        folder = self.root / ".team" / "sessions" / "69"
        folder.mkdir(parents=True)
        (folder / "log.md").write_text(
            "2026-11-26T00:00:00Z Codex go 계획 승인\n",
            encoding="utf-8",
        )
        (folder / "task.md").write_text(
            "# 작업\n\n## 계획\n\n- 읽기 | 없음 | a.py | python3 a_test.py\n\n## 계획 밖\n\n- 새단위 | 없음 | b.py | python3 b_test.py\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run(self) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["TEAM_ROOT"] = str(self.root)
        return subprocess.run(
            ["python3", str(SCRIPT), "plan-check", "69"],
            cwd=self.root,
            env=env,
            text=True,
            capture_output=True,
        )

    def test_extra_unit_stops(self) -> None:
        result = self._run()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("계획 밖 단위다: 새단위", result.stderr)

    def test_file_outside_the_list_is_a_warning(self) -> None:
        task = self.root / ".team" / "sessions" / "69" / "task.md"
        task.write_text(
            "# 작업\n\n## 계획\n\n- 읽기 | 없음 | a.py | python3 a_test.py\n",
            encoding="utf-8",
        )
        (self.root / "b.py").write_text("y = 2\n", encoding="utf-8")
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("파일 목록 밖이다: b.py", result.stdout)

    def test_rule_and_adr_name_the_go_scope(self) -> None:
        rule = (ROOT / ".rulesync/rules/dam.md").read_text(encoding="utf-8")
        adr = (ROOT / "docs/adr/0002-subagent-driven-development.md").read_text(encoding="utf-8")
        self.assertIn("go 하나는 그 계획 전체", rule)
        self.assertIn("## go의 범위", adr)
        self.assertLessEqual(len(rule.splitlines()), 50)


class ResumeModeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        write_board(self.root, [board_line("70", "시작")])
        folder = self.root / ".team" / "sessions" / "70"
        folder.mkdir(parents=True)
        (folder / "state.md").write_text(
            "모드: 기능\n# 상태 70\n다음 할 일\n",
            encoding="utf-8",
        )
        (folder / "log.md").write_text("2026-11-26T00:00:00Z Codex go 남음\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run(self, *args: str, root: Path | None = None) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["TEAM_ROOT"] = str(root or self.root)
        env["GITHUB_HEAD_REF"] = "work-70"
        return subprocess.run(
            ["python3", str(SCRIPT), "resume", *args],
            cwd=root or self.root,
            env=env,
            text=True,
            capture_output=True,
        )

    def test_begin_records_previous_mode_and_end_restores_it(self) -> None:
        begin = self._run("begin")
        self.assertEqual(begin.returncode, 0, begin.stderr)
        text = (self.root / ".team" / "sessions" / "70" / "state.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("모드: 이어받기\n"))
        self.assertIn("이전 모드: 기능\n", text)
        self.assertIn("다음 할 일\n", text)
        end = self._run("end")
        self.assertEqual(end.returncode, 0, end.stderr)
        after = (self.root / ".team" / "sessions" / "70" / "state.md").read_text(encoding="utf-8")
        self.assertTrue(after.startswith("모드: 기능\n"))
        self.assertNotIn("이전 모드:", after)
        self.assertIn("다음 할 일\n", after)

    def test_missing_state_does_not_create_a_file(self) -> None:
        bare = Path(self.tmp.name) / "bare"
        bare.mkdir()
        write_board(bare, [board_line("70", "시작")])
        result = self._run("begin", root=bare)
        self.assertEqual(result.returncode, 1)
        self.assertIn("상태 파일이 없다", result.stderr)
        self.assertFalse((bare / ".team" / "sessions" / "70").exists())


if __name__ == "__main__":
    unittest.main()
