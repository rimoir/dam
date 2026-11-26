#!/usr/bin/env python3
"""team-session 생성기의 실패 우선 검사."""

import fcntl
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "team-session.py"
TRACKER = ROOT / "scripts" / "issue_tracker.py"


def install_fake_gh(root: Path) -> Path:
    bindir = root / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    script = bindir / "gh"
    script.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys

log_path = os.environ.get("GH_LOG")
if log_path:
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(" ".join(sys.argv[1:]) + "\\n")
failed = os.environ.get("GH_FAIL")
if failed:
    sys.stderr.write(failed)
    if not failed.endswith("\\n"):
        sys.stderr.write("\\n")
    sys.exit(1)
raw = os.environ.get("GH_RAW")
if raw is not None:
    sys.stdout.write(raw)
    sys.exit(0)
args = sys.argv[1:]
if len(args) >= 3 and args[0] == "issue" and args[1] == "view":
    number = args[2]
    custom = os.environ.get("GH_JSON_FILE")
    if custom:
        sys.stdout.write(open(custom, encoding="utf-8").read())
        sys.exit(0)
    body = "### Acceptance Criteria\\n\\n- [ ] 조건 %s\\n" % number
    json.dump(
        {
            "title": "이슈 %s" % number,
            "url": "https://github.com/rimoir/dam/issues/%s" % number,
            "body": body,
        },
        sys.stdout,
    )
    sys.exit(0)
sys.stderr.write("거절된 gh 호출\\n")
sys.exit(3)
""",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return bindir


def run(
    root: Path,
    *args: str,
    gh_fail: str | None = None,
    gh_json: dict | None = None,
    gh_raw: str | None = None,
    path_mode: str = "fake",
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["TEAM_ROOT"] = str(root)
    env.pop("GH_FAIL", None)
    env.pop("GH_JSON_FILE", None)
    env.pop("GH_RAW", None)
    if path_mode == "fake":
        bindir = install_fake_gh(root)
        env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
        env["GH_LOG"] = str(root / "gh.log")
        if gh_fail is not None:
            env["GH_FAIL"] = gh_fail
        if gh_json is not None:
            payload = root / "issue.json"
            payload.write_text(json.dumps(gh_json), encoding="utf-8")
            env["GH_JSON_FILE"] = str(payload)
        if gh_raw is not None:
            env["GH_RAW"] = gh_raw
    elif path_mode == "bare":
        python_bin = shutil.which("python3")
        if not python_bin:
            raise RuntimeError("python3가 없다")
        bindir = root / "barebin"
        bindir.mkdir(parents=True, exist_ok=True)
        git_bin = shutil.which("git")
        if not git_bin:
            raise RuntimeError("git가 없다")
        for name, target in (("python3", python_bin), ("git", git_bin)):
            link = bindir / name
            if not link.exists():
                link.symlink_to(target)
        env["PATH"] = str(bindir)
    return subprocess.run(
        ["python3", str(SCRIPT), *args],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
    )


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"모듈을 열지 못했다: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def section_map(text: str) -> dict[str, str]:
    parts = text.split("\n## ")
    found: dict[str, str] = {}
    for part in parts[1:]:
        name, _, body = part.partition("\n")
        found[name.strip()] = body
    return found


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

    def test_log_line_names_the_tool(self) -> None:
        result = run(self.root, "new", "15")
        self.assertEqual(result.returncode, 0, result.stderr)
        log = (self.root / ".team" / "sessions" / "15" / "log.md").read_text(encoding="utf-8")
        self.assertIn("YYYY-MM-DDTHH:MM:SSZ", log)
        self.assertIn("Claude Code", log)
        self.assertIn("Codex", log)
        for kind in ("시작", "go", "종료", "push", "재개"):
            self.assertIn(kind, log)

    def test_summary_is_state_only_and_within_limit(self) -> None:
        created = run(self.root, "new", "14")
        self.assertEqual(created.returncode, 0, created.stderr)
        state = self.root / ".team" / "sessions" / "14" / "state.md"
        state.write_text("다음 할 일\n계획을 쓴다\n", encoding="utf-8")
        log = self.root / ".team" / "sessions" / "14" / "log.md"
        log.write_text("로그전문-MARKER\n", encoding="utf-8")
        result = run(self.root, "summary", "14")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "다음 할 일\n계획을 쓴다\n")
        self.assertNotIn("로그전문-MARKER", result.stdout)
        self.assertLessEqual(len(result.stdout), 10000)

    def test_summary_fails_when_state_exceeds_limit(self) -> None:
        created = run(self.root, "new", "14")
        self.assertEqual(created.returncode, 0, created.stderr)
        state = self.root / ".team" / "sessions" / "14" / "state.md"
        state.write_text("가" * 10001, encoding="utf-8")
        result = run(self.root, "summary", "14")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("10000", result.stderr)

    def test_parallel_new_keeps_both_board_lines(self) -> None:
        env = os.environ.copy()
        for i in range(25):
            root = self.root / f"try{i}"
            root.mkdir()
            bindir = install_fake_gh(root)
            env["TEAM_ROOT"] = str(root)
            env["PATH"] = str(bindir) + os.pathsep + os.environ.get("PATH", "")
            env["GH_LOG"] = str(root / "gh.log")
            env.pop("GH_FAIL", None)
            env.pop("GH_JSON_FILE", None)
            env.pop("GH_RAW", None)
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


class IssueStartTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_issue_fields_land_in_the_existing_sections(self) -> None:
        payload = {
            "title": "[M3b] 제목",
            "url": "https://github.com/rimoir/dam/issues/30",
            "body": (
                "### Objective\n본문\n\n"
                "### Covers\n"
                "Covers: 첫째 조건\n"
                "Covers: 둘째 조건\n"
            ),
        }
        result = run(self.root, "new", "30", gh_json=payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        task = (self.root / ".team" / "sessions" / "30" / "task.md").read_text(encoding="utf-8")
        parts = section_map(task)
        self.assertIn("[M3b] 제목", parts["목표"])
        self.assertIn("https://github.com/rimoir/dam/issues/30", parts["목표"])
        self.assertNotIn("첫째 조건", parts["목표"])
        self.assertIn("첫째 조건", parts["완료 기준"])
        self.assertIn("둘째 조건", parts["완료 기준"])
        self.assertNotIn("[M3b] 제목", parts["완료 기준"])
        self.assertIn("(단계)", parts["계획"])
        for name in ("state.md", "log.md", "result.md"):
            self.assertTrue((self.root / ".team" / "sessions" / "30" / name).is_file())
        board = (self.root / ".team" / "board.md").read_text(encoding="utf-8")
        self.assertEqual(board.count("\n- 30:"), 1)
        self.assertIn("상태 시작", board)

    def test_acceptance_checkboxes_become_the_criteria_list(self) -> None:
        payload = {
            "title": "체크 제목",
            "url": "https://github.com/rimoir/dam/issues/4",
            "body": (
                "### Acceptance Criteria\n\n"
                "- [ ] 열린 조건\n"
                "- [x] 끝난 조건\n\n"
                "### Covers\n"
                "Covers: 이쪽은 목록에 넣지 않는다\n"
            ),
        }
        result = run(self.root, "new", "4", gh_json=payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        task = (self.root / ".team" / "sessions" / "4" / "task.md").read_text(encoding="utf-8")
        parts = section_map(task)
        self.assertIn("- 열린 조건", parts["완료 기준"])
        self.assertIn("- 끝난 조건", parts["완료 기준"])
        self.assertNotIn("이쪽은 목록에 넣지 않는다", parts["완료 기준"])

    def test_missing_criteria_leave_an_empty_marker(self) -> None:
        payload = {
            "title": "기준 없는 이슈",
            "url": "https://github.com/rimoir/dam/issues/8",
            "body": "설명만 있다",
        }
        result = run(self.root, "new", "8", gh_json=payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        task = (self.root / ".team" / "sessions" / "8" / "task.md").read_text(encoding="utf-8")
        self.assertIn("- (없음)", section_map(task)["완료 기준"])

    def test_fake_tracker_matches_cli_task(self) -> None:
        session = load_module(SCRIPT, "team_session_under_test")
        record = session.IssueRecord(
            number=30,
            title="같은제목",
            url="https://github.com/rimoir/dam/issues/30",
            acceptance=("기준 하나", "기준 둘"),
        )

        class Fake:
            def read_issue(self, number: int):
                self.number = number
                return record

        fake = Fake()
        session.create_session(self.root, "30", "dev", fake)
        via_fake = (self.root / ".team" / "sessions" / "30" / "task.md").read_text(encoding="utf-8")
        self.assertEqual(fake.number, 30)
        other = self.root / "cli"
        other.mkdir()
        payload = {
            "title": "같은제목",
            "url": "https://github.com/rimoir/dam/issues/30",
            "body": "### Acceptance Criteria\n\n- [ ] 기준 하나\n- [ ] 기준 둘\n",
        }
        result = run(other, "new", "30", gh_json=payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        via_cli = (other / ".team" / "sessions" / "30" / "task.md").read_text(encoding="utf-8")
        self.assertEqual(via_fake, via_cli)
        self.assertIn("같은제목", section_map(via_cli)["목표"])
        self.assertIn("https://github.com/rimoir/dam/issues/30", section_map(via_cli)["목표"])
        self.assertIn("- 기준 하나", section_map(via_cli)["완료 기준"])
        self.assertIn("- 기준 둘", section_map(via_cli)["완료 기준"])

    def test_new_only_views_the_issue(self) -> None:
        result = run(self.root, "new", "30")
        self.assertEqual(result.returncode, 0, result.stderr)
        log = (self.root / "gh.log").read_text(encoding="utf-8").strip()
        self.assertEqual(log.count("\n") + 1, 1)
        self.assertIn("issue view 30", log)
        self.assertIn("--json title,url,body", log)
        for banned in ("comment", "close", "edit", " pr ", "label", "api"):
            self.assertNotIn(banned, log)

    def test_rerun_keeps_handwritten_task_and_skips_read(self) -> None:
        first = run(self.root, "new", "30")
        self.assertEqual(first.returncode, 0, first.stderr)
        task = self.root / ".team" / "sessions" / "30" / "task.md"
        task.write_text(task.read_text(encoding="utf-8") + "\n손글씨\n", encoding="utf-8")
        before = task.read_bytes()
        log = self.root / "gh.log"
        log.unlink()
        second = run(self.root, "new", "30", gh_fail="should not run")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(task.read_bytes(), before)
        self.assertFalse(log.exists())

    def test_read_failure_leaves_no_session(self) -> None:
        result = run(self.root, "new", "30", gh_fail="gh auth login")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("이슈를 읽지 못했다", result.stderr)
        self.assertIn("gh auth login", result.stderr)
        self.assertFalse((self.root / ".team" / "sessions" / "30").exists())
        self.assertFalse((self.root / ".team" / "board.md").exists())

    def test_read_failure_keeps_existing_files(self) -> None:
        folder = self.root / ".team" / "sessions" / "12"
        folder.mkdir(parents=True)
        keep = folder / "notes.md"
        keep.write_text("증거\n", encoding="utf-8")
        result = run(self.root, "new", "12", gh_fail="network down")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(keep.read_text(encoding="utf-8"), "증거\n")
        self.assertFalse((folder / "task.md").exists())
        self.assertFalse((self.root / ".team" / "board.md").exists())

    def test_bad_json_leaves_no_session(self) -> None:
        result = run(self.root, "new", "30", gh_raw="not-json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("이슈를 읽지 못했다", result.stderr)
        self.assertFalse((self.root / ".team" / "sessions" / "30").exists())

    def test_missing_gh_leaves_no_notes(self) -> None:
        result = run(self.root, "new", "41", path_mode="bare")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("gh", result.stderr)
        self.assertFalse((self.root / ".team" / "sessions" / "41").exists())

    def test_secret_in_gh_error_is_not_echoed(self) -> None:
        secret = "ghp_" + ("A" * 36)
        result = run(self.root, "new", "30", gh_fail="login failed " + secret)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(secret, result.stderr)
        self.assertNotIn(secret, result.stdout)
        self.assertFalse((self.root / ".team" / "sessions" / "30").exists())

    def test_date_id_does_not_call_gh(self) -> None:
        session = load_module(SCRIPT, "team_session_date")

        class Boom:
            def read_issue(self, number: int):
                raise AssertionError("date id must not read")

        session.create_session(self.root, "2026-11-26-memo", "dev", Boom())
        task = (self.root / ".team" / "sessions" / "2026-11-26-memo" / "task.md").read_text(encoding="utf-8")
        self.assertIn("(한 줄)", section_map(task)["목표"])
        self.assertNotIn("github.com", task)
        result = run(self.root, "new", "2026-11-26-other")
        self.assertEqual(result.returncode, 0, result.stderr)
        log = self.root / "gh.log"
        self.assertFalse(log.exists())

    def test_unknown_tracker_leaves_no_notes(self) -> None:
        team = self.root / ".team"
        team.mkdir(parents=True)
        (team / "adapters.lock").write_text("issue-tracker: linear\n", encoding="utf-8")
        result = run(self.root, "new", "30")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("linear", result.stderr)
        self.assertFalse((team / "sessions").exists())
        self.assertFalse((self.root / "gh.log").exists())

    def test_github_lock_still_reads(self) -> None:
        team = self.root / ".team"
        team.mkdir(parents=True)
        (team / "adapters.lock").write_text(
            "# 선택 결과\nissue-tracker: github\nreport: dooray\n",
            encoding="utf-8",
        )
        result = run(self.root, "new", "30")
        self.assertEqual(result.returncode, 0, result.stderr)
        task = (team / "sessions" / "30" / "task.md").read_text(encoding="utf-8")
        self.assertIn("이슈 30", section_map(task)["목표"])

    def test_criteria_heading_in_this_repo_fills_the_list(self) -> None:
        payload = {
            "title": "노트 쌓기",
            "url": "https://github.com/rimoir/dam/issues/2",
            "body": (
                "### 사용자 관점의 완료 조건\n\n"
                "검증은 실제 세션과 생성된 파일로 한다.\n\n"
                "- [ ] 첫 조건\n"
                "- [x] 둘째 조건\n"
            ),
        }
        result = run(self.root, "new", "2", gh_json=payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        criteria = section_map(
            (self.root / ".team" / "sessions" / "2" / "task.md").read_text(encoding="utf-8")
        )["완료 기준"]
        self.assertIn("- 첫 조건", criteria)
        self.assertIn("- 둘째 조건", criteria)
        self.assertNotIn("(없음)", criteria)

    def test_bom_lock_does_not_call_github(self) -> None:
        team = self.root / ".team"
        team.mkdir(parents=True)
        (team / "adapters.lock").write_bytes("\ufeffissue-tracker: linear\n".encode("utf-8"))
        result = run(self.root, "new", "30")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("linear", result.stderr)
        self.assertFalse((team / "sessions").exists())
        self.assertFalse((self.root / "gh.log").exists())

    def test_unreadable_lock_leaves_no_notes(self) -> None:
        team = self.root / ".team"
        team.mkdir(parents=True)
        (team / "adapters.lock").write_bytes(b"\xff\xfeissue")
        result = run(self.root, "new", "30")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("adapters.lock", result.stderr)
        self.assertFalse((team / "sessions").exists())
        self.assertFalse((self.root / "gh.log").exists())

    def test_failed_write_leaves_no_session(self) -> None:
        bindir = install_fake_gh(self.root)
        payload = self.root / "issue.json"
        payload.write_text(
            json.dumps(
                {
                    "title": "큰" + ("가" * 2000),
                    "url": "https://github.com/rimoir/dam/issues/30",
                    "body": "### Acceptance Criteria\n\n- [ ] 긴 조건\n",
                }
            ),
            encoding="utf-8",
        )
        env = os.environ.copy()
        env["TEAM_ROOT"] = str(self.root)
        env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
        env["GH_JSON_FILE"] = str(payload)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            ["bash", "-c", 'ulimit -f 1; python3 "$1" new 30', "bash", str(SCRIPT)],
            cwd=self.root,
            env=env,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / ".team" / "sessions" / "30").exists())
        self.assertFalse((self.root / ".team" / "board.md").exists())

    def test_write_without_command_does_not_call_runner(self) -> None:
        tracker_mod = load_module(TRACKER, "issue_tracker_under_test")
        called: list[list[str]] = []

        def runner(args: list[str], stdin: str | None = None):
            called.append(args)
            return tracker_mod.GhResult(0, "", "")

        tracker = tracker_mod.GithubIssueTracker("rimoir/dam", runner)
        for call in (
            lambda: tracker.comment(30, "본문", commanded=False),
            lambda: tracker.add_label(30, "bug", commanded=False),
            lambda: tracker.close_issue(30, commanded=False),
            lambda: tracker.open_pull_request("제목", "본문", commanded=False),
        ):
            with self.assertRaises(tracker_mod.IssueTrackerError):
                call()
        self.assertEqual(called, [])

    def test_commanded_write_is_gh_and_nothing_else(self) -> None:
        tracker_mod = load_module(TRACKER, "issue_tracker_commanded")
        seen: list[tuple[list[str], str | None]] = []

        def runner(args: list[str], stdin: str | None = None):
            seen.append((args, stdin))
            return tracker_mod.GhResult(0, "", "")

        tracker = tracker_mod.GithubIssueTracker("rimoir/dam", runner)
        tracker.comment(30, "본문", commanded=True)
        self.assertEqual(len(seen), 1)
        args, stdin = seen[0]
        self.assertEqual(args[0], "gh")
        self.assertEqual(args[1:3], ["issue", "comment"])
        self.assertEqual(stdin, "본문")
        self.assertNotIn("dooray", " ".join(args))
        self.assertTrue(all(item != "curl" for item in args))

    def test_slug_drops_credentials(self) -> None:
        tracker_mod = load_module(TRACKER, "issue_tracker_slug")
        secret = "ghs_" + ("b" * 36)
        url = f"https://x-access-token:{secret}@github.com/rimoir/dam.git"
        slug = tracker_mod.github_slug(url)
        self.assertEqual(slug, "rimoir/dam")
        self.assertNotIn(secret, slug or "")
        self.assertEqual(tracker_mod.github_slug("git@github.com:rimoir/dam.git"), "rimoir/dam")
        self.assertIsNone(tracker_mod.github_slug("https://gitlab.com/rimoir/dam.git"))


def install_pr_gh(root: Path) -> Path:
    bindir = root / "prbin"
    bindir.mkdir(parents=True, exist_ok=True)
    script = bindir / "gh"
    script.write_text(
        """#!/usr/bin/env python3
import os
import sys

log_path = os.environ.get("GH_LOG")
if log_path:
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(" ".join(sys.argv[1:]) + "\\n")
data = sys.stdin.read()
stdin_path = os.environ.get("GH_STDIN")
if stdin_path:
    with open(stdin_path, "w", encoding="utf-8") as handle:
        handle.write(data)
failed = os.environ.get("GH_FAIL")
if failed:
    sys.stderr.write(failed)
    if not failed.endswith("\\n"):
        sys.stderr.write("\\n")
    sys.exit(1)
args = sys.argv[1:]
if len(args) >= 2 and args[0] == "pr" and args[1] == "create":
    sys.stdout.write("https://github.com/rimoir/dam/pull/99\\n")
    sys.exit(0)
sys.stderr.write("거절된 gh 호출\\n")
sys.exit(3)
""",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return bindir


def pull(root: Path, *args: str, gh_fail: str | None = None) -> subprocess.CompletedProcess[str]:
    bindir = install_pr_gh(root)
    env = os.environ.copy()
    env["TEAM_ROOT"] = str(root)
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    env["GH_LOG"] = str(root / "gh.log")
    env["GH_STDIN"] = str(root / "gh-stdin.txt")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("GH_FAIL", None)
    if gh_fail is not None:
        env["GH_FAIL"] = gh_fail
    return subprocess.run(
        ["python3", str(SCRIPT), "pull", *args],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
    )


class PullLogTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        folder = self.root / ".team" / "sessions" / "31"
        folder.mkdir(parents=True)
        self.log = folder / "log.md"
        self.log.write_text("# 로그 31\n\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_pull_body_has_issue_link_and_log_has_url(self) -> None:
        result = pull(self.root, "31", "--title", "제목", "--tool", "Codex")
        self.assertEqual(result.returncode, 0, result.stderr)
        body = (self.root / "gh-stdin.txt").read_text(encoding="utf-8")
        self.assertIn("https://github.com/rimoir/dam/issues/31", body)
        self.assertNotIn("pull/99", body)
        log_lines = [
            line
            for line in self.log.read_text(encoding="utf-8").splitlines()
            if line.startswith("20")
        ]
        self.assertEqual(len(log_lines), 1)
        self.assertRegex(
            log_lines[0],
            r"^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ Codex push https://github.com/rimoir/dam/pull/99$",
        )
        gh_log = (self.root / "gh.log").read_text(encoding="utf-8")
        self.assertIn("pr create", gh_log)
        self.assertNotIn("issue comment", gh_log)
        self.assertNotIn("api ", gh_log)

    def test_second_pull_appends_a_line(self) -> None:
        first = pull(self.root, "31", "--title", "제목", "--tool", "Claude Code")
        self.assertEqual(first.returncode, 0, first.stderr)
        before = self.log.read_text(encoding="utf-8")
        second = pull(self.root, "31", "--title", "제목", "--tool", "Claude Code")
        self.assertEqual(second.returncode, 0, second.stderr)
        after = self.log.read_text(encoding="utf-8")
        self.assertTrue(after.startswith(before))
        added = [line for line in after[len(before) :].splitlines() if line]
        self.assertEqual(len(added), 1)
        self.assertIn("Claude Code push https://github.com/rimoir/dam/pull/99", added[0])

    def test_failed_open_does_not_change_log(self) -> None:
        before = self.log.read_bytes()
        result = pull(self.root, "31", "--title", "제목", "--tool", "Codex", gh_fail="pr create failed")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("쓰지 못했다", result.stderr)
        self.assertEqual(self.log.read_bytes(), before)
        self.assertNotIn("ghp_", result.stderr)

    def test_missing_log_does_not_call_gh(self) -> None:
        self.log.unlink()
        result = pull(self.root, "31", "--title", "제목", "--tool", "Codex")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "gh.log").exists())
        self.assertFalse(self.log.exists())

    def test_date_id_and_bad_tool_do_not_call_gh(self) -> None:
        date = pull(self.root, "2026-11-26-memo", "--title", "제목", "--tool", "Codex")
        self.assertNotEqual(date.returncode, 0)
        bad = pull(self.root, "31", "--title", "제목", "--tool", "Cursor")
        self.assertNotEqual(bad.returncode, 0)
        self.assertFalse((self.root / "gh.log").exists())

    def test_new_does_not_open_a_pull(self) -> None:
        created = run(self.root, "new", "32")
        self.assertEqual(created.returncode, 0, created.stderr)
        viewed = (self.root / "gh.log").read_text(encoding="utf-8")
        self.assertNotIn("pr create", viewed)


def install_board_gh(root: Path) -> Path:
    bindir = root / "boardbin"
    bindir.mkdir(parents=True, exist_ok=True)
    script = bindir / "gh"
    script.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys

log_path = os.environ.get("GH_LOG")
if log_path:
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(" ".join(sys.argv[1:]) + "\\n")
if os.environ.get("GH_FAIL"):
    sys.stderr.write(os.environ["GH_FAIL"])
    if not os.environ["GH_FAIL"].endswith("\\n"):
        sys.stderr.write("\\n")
    sys.exit(1)
spec = json.load(open(os.environ["GH_SPEC"], encoding="utf-8"))
args = sys.argv[1:]
if len(args) >= 3 and args[0] == "issue" and args[1] == "view":
    item = spec["issues"].get(args[2])
    if item is None:
        sys.stderr.write("issue missing\\n")
        sys.exit(1)
    json.dump(item, sys.stdout)
    sys.exit(0)
if len(args) >= 2 and args[0] == "pr" and args[1] == "list":
    json.dump(spec.get("prs", []), sys.stdout)
    sys.exit(0)
if len(args) >= 3 and args[0] == "pr" and args[1] == "checks":
    if args[2] in spec.get("nochecks", []):
        sys.stderr.write("no checks reported on the 'topic' branch\\n")
        sys.exit(1)
    json.dump(spec.get("checks", {}).get(args[2], []), sys.stdout)
    sys.exit(0)
sys.stderr.write("거절된 gh 호출\\n")
sys.exit(3)
""",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return bindir


def board_cmd(root: Path, spec: dict | None = None, gh_fail: str | None = None) -> subprocess.CompletedProcess[str]:
    bindir = install_board_gh(root)
    if spec is not None:
        (root / "gh-spec.json").write_text(json.dumps(spec), encoding="utf-8")
    env = os.environ.copy()
    env["TEAM_ROOT"] = str(root)
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    env["GH_LOG"] = str(root / "gh.log")
    env["GH_SPEC"] = str(root / "gh-spec.json")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("GH_FAIL", None)
    if gh_fail is not None:
        env["GH_FAIL"] = gh_fail
    return subprocess.run(
        ["python3", str(SCRIPT), "board"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
    )


class BoardRefreshTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        team = self.root / ".team"
        team.mkdir()
        self.board = team / "board.md"
        self.board.write_text(
            "# 작업 현황\n\n"
            "- 31: 상태 시작, 담당 dev, 막힘 없음\n"
            "- 30: 상태 시작, 담당 dev, 막힘 없음\n"
            "- 2026-11-26-memo: 상태 시작, 담당 dev, 막힘 없음\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_refresh_shows_review_checks_done_and_closed(self) -> None:
        spec = {
            "issues": {"31": {"state": "OPEN"}, "30": {"state": "CLOSED"}},
            "prs": [
                {
                    "number": 7,
                    "state": "OPEN",
                    "body": "https://github.com/rimoir/dam/issues/31",
                    "closingIssuesReferences": [{"number": 31}],
                }
            ],
            "checks": {
                "7": [
                    {"name": "python test", "bucket": "pass"},
                    {"name": "gitleaks", "bucket": "pass"},
                ]
            },
        }
        result = board_cmd(self.root, spec)
        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.board.read_text(encoding="utf-8")
        self.assertIn("- 31: 상태 시작, 담당 dev, 막힘 없음, GitHub 검토 중, 검사 통과\n", text)
        self.assertIn("- 30: 상태 시작, 담당 dev, 막힘 없음, GitHub 닫힘\n", text)
        self.assertIn("- 2026-11-26-memo: 상태 시작, 담당 dev, 막힘 없음\n", text)
        self.assertNotIn("GitHub 검토 중, 검사 통과, GitHub", text)
        log = (self.root / "gh.log").read_text(encoding="utf-8")
        for banned in ("pr create", "issue comment", "issue close", "issue edit"):
            self.assertNotIn(banned, log)

    def test_failed_check_and_pending_and_merged(self) -> None:
        spec = {
            "issues": {
                "31": {"state": "OPEN"},
                "12": {"state": "OPEN"},
                "13": {"state": "OPEN"},
            },
            "prs": [
                {"number": 8, "state": "OPEN", "body": "", "closingIssuesReferences": [{"number": 31}]},
                {"number": 9, "state": "OPEN", "body": "Closes #12", "closingIssuesReferences": []},
                {"number": 10, "state": "MERGED", "body": "", "closingIssuesReferences": [{"number": 13}]},
            ],
            "checks": {
                "8": [{"name": "python test", "bucket": "fail"}],
                "9": [{"name": "python test", "bucket": "pending"}],
            },
        }
        self.board.write_text(
            "- 31: 상태 시작, 담당 dev, 막힘 없음\n"
            "- 12: 상태 시작, 담당 dev, 막힘 스펙\n"
            "- 13: 상태 시작, 담당 dev, 막힘 없음\n",
            encoding="utf-8",
        )
        result = board_cmd(self.root, spec)
        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.board.read_text(encoding="utf-8")
        self.assertIn("막힘 없음, GitHub 검토 중, 검사 실패", text)
        self.assertIn("막힘 스펙, GitHub 검토 중, 검사 아직 안 돎", text)
        self.assertIn("- 13: 상태 시작, 담당 dev, 막힘 없음, GitHub 완료\n", text)

    def test_fake_tracker_matches_board_text(self) -> None:
        session = load_module(SCRIPT, "team_session_board")
        view = session.WorkView(issue_closed=False, pull_state="open", checks="pass")

        class Fake:
            def read_status(self, number: int):
                self.number = number
                return view

        only = self.root / "fake"
        team = only / ".team"
        team.mkdir(parents=True)
        board = team / "board.md"
        board.write_text("- 31: 상태 시작, 담당 dev, 막힘 없음\n", encoding="utf-8")
        session.refresh_board(only, Fake())
        via_fake = board.read_text(encoding="utf-8")
        self.board.write_text("- 31: 상태 시작, 담당 dev, 막힘 없음\n", encoding="utf-8")
        spec = {
            "issues": {"31": {"state": "OPEN"}},
            "prs": [{"number": 7, "state": "OPEN", "body": "", "closingIssuesReferences": [{"number": 31}]}],
            "checks": {"7": [{"name": "python test", "bucket": "pass"}]},
        }
        result = board_cmd(self.root, spec)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(via_fake, self.board.read_text(encoding="utf-8"))

    def test_refresh_failure_keeps_the_board(self) -> None:
        before = self.board.read_bytes()
        result = board_cmd(self.root, {"issues": {}, "prs": [], "checks": {}}, gh_fail="gh auth login")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("읽지 못했다", result.stderr)
        self.assertEqual(self.board.read_bytes(), before)

    def test_second_refresh_replaces_the_github_clause(self) -> None:
        spec = {
            "issues": {"31": {"state": "OPEN"}, "30": {"state": "OPEN"}},
            "prs": [{"number": 7, "state": "OPEN", "body": "", "closingIssuesReferences": [{"number": 31}]}],
            "checks": {"7": [{"name": "python test", "bucket": "pass"}]},
        }
        first = board_cmd(self.root, spec)
        self.assertEqual(first.returncode, 0, first.stderr)
        spec["issues"]["31"] = {"state": "CLOSED"}
        (self.root / "gh-spec.json").write_text(json.dumps(spec), encoding="utf-8")
        second = board_cmd(self.root, spec)
        self.assertEqual(second.returncode, 0, second.stderr)
        text = self.board.read_text(encoding="utf-8")
        self.assertIn("- 31: 상태 시작, 담당 dev, 막힘 없음, GitHub 닫힘\n", text)
        self.assertEqual(text.count("GitHub"), 2)
        self.assertNotIn("검토 중", text)

    def test_closes_keyword_is_the_pull_and_epic_url_is_not(self) -> None:
        self.board.write_text(
            "- 32: 상태 시작, 담당 dev, 막힘 없음\n"
            "- 4: 상태 진행, 담당 팀, 막힘 없음\n",
            encoding="utf-8",
        )
        spec = {
            "issues": {
                "32": {"state": "OPEN", "closedByPullRequestsReferences": []},
                "4": {"state": "OPEN", "closedByPullRequestsReferences": []},
            },
            "prs": [
                {
                    "number": 48,
                    "state": "OPEN",
                    "body": "Closes #32\n\n에픽: https://github.com/rimoir/dam/issues/4\n",
                    "closingIssuesReferences": [],
                }
            ],
            "checks": {"48": [{"name": "python test", "bucket": "pass"}]},
        }
        result = board_cmd(self.root, spec)
        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.board.read_text(encoding="utf-8")
        self.assertIn("- 32: 상태 시작, 담당 dev, 막힘 없음, GitHub 검토 중, 검사 통과\n", text)
        self.assertIn("- 4: 상태 진행, 담당 팀, 막힘 없음, GitHub 열림\n", text)

    def test_no_checks_reported_is_not_run_yet(self) -> None:
        self.board.write_text(
            "- 31: 상태 시작, 담당 dev, 막힘 없음\n"
            "- 32: 상태 계획, 담당 사람, 막힘 스펙\n",
            encoding="utf-8",
        )
        spec = {
            "issues": {
                "31": {"state": "OPEN", "closedByPullRequestsReferences": []},
                "32": {"state": "OPEN", "closedByPullRequestsReferences": []},
            },
            "prs": [
                {"number": 8, "state": "OPEN", "body": "Closes #31", "closingIssuesReferences": []},
                {"number": 9, "state": "OPEN", "body": "Closes #32", "closingIssuesReferences": []},
            ],
            "checks": {},
            "nochecks": ["8", "9"],
        }
        result = board_cmd(self.root, spec)
        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.board.read_text(encoding="utf-8")
        self.assertIn("GitHub 검토 중, 검사 아직 안 돎", text)
        self.assertEqual(text.count("아직 안 돎"), 2)

    def test_refresh_keeps_a_line_added_while_it_reads(self) -> None:
        self.board.write_text("- 31: 상태 시작, 담당 dev, 막힘 없음\n", encoding="utf-8")
        bindir = self.root / "slowbin"
        bindir.mkdir()
        script = bindir / "gh"
        script.write_text(
            """#!/usr/bin/env python3
import json, sys, time
args = sys.argv[1:]
if args[:2] == ["issue", "view"]:
    time.sleep(0.4)
    json.dump({"state": "OPEN", "closedByPullRequestsReferences": []}, sys.stdout)
    sys.exit(0)
if args[:2] == ["pr", "list"]:
    json.dump([], sys.stdout)
    sys.exit(0)
sys.stderr.write("거절된 gh 호출\\n")
sys.exit(3)
""",
            encoding="utf-8",
        )
        script.chmod(0o755)
        env = os.environ.copy()
        env["TEAM_ROOT"] = str(self.root)
        env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.Popen(
            ["python3", str(SCRIPT), "board"],
            cwd=self.root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        def add_line() -> None:
            import time

            time.sleep(0.15)
            with self.board.open("a+", encoding="utf-8") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                handle.seek(0)
                text = handle.read()
                if "- 99:" not in text:
                    if text and not text.endswith("\n"):
                        handle.write("\n")
                    handle.write("- 99: 상태 시작, 담당 qa, 막힘 없음\n")

        import threading

        worker = threading.Thread(target=add_line)
        worker.start()
        stderr = proc.communicate()[1]
        worker.join()
        self.assertEqual(proc.returncode, 0, stderr)
        text = self.board.read_text(encoding="utf-8")
        self.assertIn("GitHub 열림", text)
        self.assertIn("- 99: 상태 시작, 담당 qa, 막힘 없음", text)


class WorkerWriteDecisionTest(unittest.TestCase):
    def test_adr_0007_replaces_conflicting_lines(self) -> None:
        adr = (ROOT / "docs/adr/0007-worker-github-write-and-merge.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("squash 머지", adr)
        self.assertIn("처음부터 push, PR, 머지 도구", adr)
        self.assertIn("헤드 SHA", adr)
        self.assertIn("확인 방법", adr)
        self.assertIn("증거", adr)
        self.assertIn(
            "https://github.com/rimoir/dam/issues/4#issuecomment-7182074410", adr
        )
        self.assertIn(
            "https://github.com/rimoir/dam/issues/60#issuecomment-7183757371", adr
        )
        self.assertIn("같은 GitHub 계정", adr)
        self.assertIn("샌드박스", adr)
        self.assertIn("새 토큰은 만들지 않는다", adr)
        self.assertIn("docs/conventions.md", adr)
        self.assertIn("제품 워커", adr)
        self.assertIn("force push", adr)
        self.assertIn("이슈 라벨", adr)
        self.assertIn("직접 확인", adr)

        rule = (ROOT / ".rulesync/rules/dam.md").read_text(encoding="utf-8")
        self.assertNotIn("PR은 자동으로 열지 않는다", rule)
        self.assertNotIn("사람이 그 동작을 직접 명령했을 때만 그 어댑터를 통한다", rule)
        self.assertIn("ADR 0007", rule)
        self.assertIn("새 토큰은 만들지 않는다", rule)
        self.assertIn("python3 scripts/team-session.py pull", rule)

        adr5 = (ROOT / "docs/adr/0005-adapter-choice.md").read_text(encoding="utf-8")
        self.assertIn("일부 대체: 0007", adr5)
        self.assertIn("ADR 0007 조건 안의 워커", adr5)
        self.assertIn("작업 시작 명령은 그 함수를 부르지 않는다", adr5)

        adr3 = (ROOT / "docs/adr/0003-ci-and-merge.md").read_text(encoding="utf-8")
        self.assertIn("사람, 또는 ADR 0007 조건을 지킨 워커", adr3)
        self.assertIn("헤드 SHA", adr3)
        self.assertIn("확인 방법", adr3)
        self.assertNotIn("이 비공개 저장소", adr3)
        self.assertIn("이 저장소는 공개다", adr3)

        spec = (ROOT / "docs/spec.md").read_text(encoding="utf-8")
        self.assertNotIn("사람이 그 동작을 직접 명령했을 때만 호출한다", spec)
        self.assertIn("ADR 0007 조건 안의 워커", spec)
        self.assertIn("작업 시작 명령은 읽기만 한다", spec)

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("PR은 사람이 명령할 때만 연다", readme)
        self.assertIn("ADR 0007", readme)
        self.assertIn("헤드 SHA", readme)
        self.assertIn("사람이 이미 로그인한", readme)

        conventions = (ROOT / "docs/conventions.md").read_text(encoding="utf-8")
        self.assertIn(
            "| Dev bot | how (tech spec, PRs) | code, `docs/`, `.team/`, PRs, sub-issues | merge, deploy, external posts |",
            conventions,
        )

        for name in ("AGENTS.md", "CLAUDE.md"):
            generated = (ROOT / name).read_text(encoding="utf-8")
            self.assertNotIn("PR은 자동으로 열지 않는다", generated)
            self.assertIn("ADR 0007", generated)

        gate = (ROOT / "scripts/issue_tracker.py").read_text(encoding="utf-8")
        self.assertIn(
            "GitHub 쓰기는 사람이 그 동작을 직접 명령했을 때만 한다", gate
        )


if __name__ == "__main__":
    unittest.main()
