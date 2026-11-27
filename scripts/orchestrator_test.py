#!/usr/bin/env python3
"""오케스트레이터 어댑터의 실패 우선 검사."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "orchestrator.py"
SESSION = ROOT / "scripts" / "team-session.py"
FIELDS = ("ok", "handle", "state", "line", "reason")


def setUpModule() -> None:
    # 테스트 프로세스는 PATH의 실제 도구를 고르지 않는다.
    os.environ["ORCH_CLAUDE"] = "-"


def place_worktree(root: Path, work_id: str) -> Path:
    dest = root.resolve().parent / f"dam-{work_id}"
    if dest.exists():
        raise RuntimeError(f"작업 폴더가 이미 있다: {dest}")
    dest.mkdir()
    return dest


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"모듈을 열지 못했다: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


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
args = sys.argv[1:]
if len(args) >= 3 and args[0] == "issue" and args[1] == "view":
    number = args[2]
    json.dump(
        {
            "title": "이슈 %s" % number,
            "url": "https://github.com/rimoir/dam/issues/%s" % number,
            "body": "### Acceptance Criteria\\n\\n- [ ] 조건 %s\\n" % number,
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


def install_marker(root: Path, name: str) -> None:
    bindir = root / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    script = bindir / name
    script.write_text(
        "#!/bin/sh\nprintf '%s\\n' ran >> \"$ORCH_MARKER\"\nexit 0\n",
        encoding="utf-8",
    )
    script.chmod(0o755)


def parse_record(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for raw in text.splitlines():
        if ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        found[key.strip()] = value.strip()
    return found


def run_orch(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["TEAM_ROOT"] = str(root)
    env["ORCH_MARKER"] = str(root / "marker.txt")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    bindir = root / "bin"
    if bindir.is_dir():
        env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    return subprocess.run(
        ["python3", str(SCRIPT), *args],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
    )


class AdapterShapeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        install_marker(self.root, "claude")
        install_marker(self.root, "codex")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_lock(self, text: str | None) -> None:
        if text is None:
            return
        team = self.root / ".team"
        team.mkdir(parents=True, exist_ok=True)
        (team / "adapters.lock").write_text(text, encoding="utf-8")

    def test_missing_lock_and_missing_key_are_native(self) -> None:
        module = load_module(SCRIPT, "orchestrator_missing")
        self.assertEqual(module.lock_name(self.root), "native")
        self.write_lock("issue-tracker: github\n")
        self.assertEqual(module.lock_name(self.root), "native")

    def test_fake_and_native_return_the_same_fields(self) -> None:
        module = load_module(SCRIPT, "orchestrator_shape")
        refused = module.start(self.root, "72")
        self.assertEqual(tuple(refused), FIELDS)
        self.assertEqual(refused["state"], "거부")
        self.assertEqual(refused["handle"], "")
        self.assertIn("계획", refused["reason"])
        write_work(
            self.root,
            "720072",
            "- 대기 | 없음 | scripts/orchestrator.py | python3 scripts/orchestrator_test.py",
            GO,
        )
        other = Path(self.tmp.name) / "fake-root"
        other.mkdir()
        (other / ".team").mkdir()
        (other / ".team" / "adapters.lock").write_text(
            "orchestrator: fake\n", encoding="utf-8"
        )
        write_work(
            other,
            "720073",
            "- 대기 | 없음 | scripts/orchestrator.py | python3 scripts/orchestrator_test.py",
            GO,
        )
        native_dir = place_worktree(self.root, "720072")
        fake_dir = place_worktree(other, "720073")
        try:
            native = module.start(self.root, "대기")
            fake = module.start(other, "대기")
            self.assertEqual(tuple(native), FIELDS)
            self.assertEqual(tuple(fake), FIELDS)
            self.assertEqual(native["ok"], "예")
            self.assertEqual(fake["ok"], "예")
            self.assertEqual(native["state"], "대기")
            self.assertEqual(fake["state"], "대기")
            self.assertTrue(native["handle"].startswith("native-"))
            self.assertTrue(fake["handle"].startswith("fake-"))
            self.assertFalse((native_dir / ".team" / "orchestrator").exists())
            self.assertFalse((fake_dir / ".team" / "orchestrator").exists())
            polled = module.poll(self.root, native["handle"])
            collected = module.collect(self.root, native["handle"])
            self.assertEqual(tuple(polled), FIELDS)
            self.assertEqual(tuple(collected), FIELDS)
        finally:
            shutil.rmtree(native_dir, ignore_errors=True)
            shutil.rmtree(fake_dir, ignore_errors=True)

    def test_unknown_name_refuses_without_a_handle(self) -> None:
        module = load_module(SCRIPT, "orchestrator_unknown")
        self.write_lock("# 메모\nissue-tracker: github\norchestrator: orca\n")
        record = module.start(self.root, "72")
        self.assertEqual(tuple(record), FIELDS)
        self.assertEqual(record["ok"], "아니오")
        self.assertEqual(record["state"], "거부")
        self.assertEqual(record["handle"], "")
        self.assertIn("orca", record["reason"])
        store = self.root / ".team" / "orchestrator"
        self.assertFalse(store.exists())

    def test_cli_prints_the_same_keys_for_both_adapters(self) -> None:
        seen: list[list[str]] = []
        for name in ("native", "fake"):
            root = Path(tempfile.mkdtemp(dir=self.tmp.name))
            install_marker(root, "claude")
            install_marker(root, "codex")
            team = root / ".team"
            team.mkdir()
            lock = "" if name == "native" else "orchestrator: fake\n"
            if lock:
                (team / "adapters.lock").write_text(lock, encoding="utf-8")
            started = run_orch(root, "start", "--unit", "72")
            self.assertNotEqual(started.returncode, 0, started.stderr)
            parsed = parse_record(started.stdout)
            self.assertEqual(tuple(parsed), FIELDS)
            self.assertEqual(parsed["ok"], "아니오")
            self.assertEqual(parsed["state"], "거부")
            self.assertEqual(parsed["handle"], "")
            seen.append(list(parse_record(started.stdout)))
            self.assertFalse((root / "marker.txt").exists())
        self.assertEqual(seen[0].__len__(), seen[1].__len__())

    def test_cli_unknown_name_refuses(self) -> None:
        self.write_lock('orchestrator: "orca"\n')
        done = run_orch(self.root, "start", "--unit", "72")
        self.assertNotEqual(done.returncode, 0)
        parsed = parse_record(done.stdout)
        self.assertEqual(parsed["state"], "거부")
        self.assertIn("orca", parsed["reason"])
        self.assertFalse((self.root / "marker.txt").exists())
        self.assertFalse((self.root / ".team" / "orchestrator").exists())

    def test_unreadable_lock_refuses(self) -> None:
        team = self.root / ".team"
        team.mkdir()
        (team / "adapters.lock").write_bytes(b"\xff\xfeorch")
        done = run_orch(self.root, "start", "--unit", "72")
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("adapters.lock", done.stdout + done.stderr)


class ClaudeLaunchTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        bindir = self.root / "bin"
        bindir.mkdir()
        (bindir / "claude").write_text(
            "#!/bin/sh\n"
            'printf \'%s\\n\' "$*" > "$ORCH_ARGV"\n'
            'printf \'%s\\n\' \'{"type":"system","subtype":"init"}\'\n'
            'printf \'%s\\n\' "## 결과" "" "PASS 끝" > result.md\n'
            "exit 0\n",
            encoding="utf-8",
        )
        (bindir / "codex").write_text(
            "#!/bin/sh\nprintf '%s\\n' ran > \"$ORCH_CODEX\"\nexit 0\n",
            encoding="utf-8",
        )
        for name in ("claude", "codex"):
            (bindir / name).chmod(0o755)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["TEAM_ROOT"] = str(self.root)
        env["ORCH_ARGV"] = str(self.root / "claude-argv.txt")
        env["ORCH_CODEX"] = str(self.root / "codex-ran.txt")
        env["PATH"] = str(self.root / "bin") + os.pathsep + env.get("PATH", "")
        env["ORCH_CLAUDE"] = str(self.root / "bin" / "claude")
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            ["python3", str(SCRIPT), *args],
            cwd=self.root,
            env=env,
            text=True,
            capture_output=True,
        )

    def test_start_poll_collect_runs_claude_and_reaps_it(self) -> None:
        write_work(
            self.root,
            "780079",
            "- 검증용 | 없음 | scripts/orchestrator.py | python3 scripts/orchestrator_test.py",
            GO,
        )
        dest = place_worktree(self.root, "780079")
        try:
            self._assert_reaped(dest)
        finally:
            shutil.rmtree(dest, ignore_errors=True)

    def _assert_reaped(self, dest: Path) -> None:
        started = self._run("start", "--unit", "검증용")
        self.assertEqual(started.returncode, 0, started.stderr)
        parsed = parse_record(started.stdout)
        self.assertEqual(parsed["ok"], "예")
        self.assertNotEqual(parsed["state"], "대기")
        seen = ""
        for _ in range(40):
            polled = self._run("poll", "--handle", parsed["handle"])
            self.assertEqual(polled.returncode, 0, polled.stderr)
            seen = parse_record(polled.stdout)["state"]
            if seen == "끝":
                break
            time.sleep(0.05)
        self.assertEqual(seen, "끝")
        collected = self._run("collect", "--handle", parsed["handle"])
        self.assertEqual(collected.returncode, 0, collected.stderr)
        done = parse_record(collected.stdout)
        self.assertTrue(done["line"].startswith("PASS"))
        argv = (self.root / "claude-argv.txt").read_text(encoding="utf-8")
        self.assertIn("--max-turns", argv)
        self.assertIn("40", argv)
        self.assertIn("stream-json", argv)
        self.assertIn("--verbose", argv)
        self.assertIn("acceptEdits", argv)
        self.assertNotIn("bypassPermissions", argv)
        self.assertNotIn("dangerously-skip-permissions", argv)
        self.assertFalse((self.root / "codex-ran.txt").exists())
        self.assertTrue((dest / "result.md").is_file())
        self.assertFalse((self.root / "result.md").exists())
        self.assertFalse((dest / ".team" / "orchestrator").exists())
        handle = self.root / ".team" / "orchestrator" / f"{parsed['handle']}.json"
        self.assertTrue(handle.is_file())
        self.assertFalse(str(handle.resolve()).startswith(str(dest)))
        self.assertNotIn("first_event", collected.stdout)
        stored = json.loads(handle.read_text(encoding="utf-8"))
        self.assertRegex(stored.get("first_event", ""), r"^[0-9]+(\.[0-9]+)?$")

    def test_launch_cwd_is_the_worktree(self) -> None:
        write_work(
            self.root,
            "780078",
            "- 검증용 | 없음 | scripts/orchestrator.py | python3 -m unittest scripts.orchestrator_test",
            GO,
        )
        dest = self.root.resolve().parent / "dam-780078"
        if dest.exists():
            self.skipTest("작업 폴더가 이미 있다")
        dest.mkdir()
        try:
            started = self._run("start", "--unit", "검증용")
            self.assertEqual(started.returncode, 0, started.stderr)
            parsed = parse_record(started.stdout)
            seen = ""
            for _ in range(40):
                polled = self._run("poll", "--handle", parsed["handle"])
                seen = parse_record(polled.stdout)["state"]
                if seen == "끝":
                    break
                time.sleep(0.05)
            self.assertEqual(seen, "끝")
            self.assertTrue((dest / "result.md").is_file())
            self.assertFalse((self.root / "result.md").exists())
            self.assertFalse((dest / ".team" / "orchestrator").exists())
            handle = self.root / ".team" / "orchestrator" / f"{parsed['handle']}.json"
            self.assertTrue(handle.is_file())
        finally:
            shutil.rmtree(dest, ignore_errors=True)

    def test_codex_is_not_launched(self) -> None:
        old = os.environ.get("ORCH_TOOL")
        os.environ["ORCH_TOOL"] = "codex"
        try:
            started = self._run("start", "--unit", "검증용")
        finally:
            if old is None:
                os.environ.pop("ORCH_TOOL", None)
            else:
                os.environ["ORCH_TOOL"] = old
        self.assertNotEqual(started.returncode, 0)
        parsed = parse_record(started.stdout)
        self.assertEqual(parsed["state"], "거부")
        self.assertIn("미검증", parsed["reason"])
        self.assertFalse((self.root / "claude-argv.txt").exists())
        self.assertFalse((self.root / "codex-ran.txt").exists())


class LaunchBoundaryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bindir = self.root / "bin"
        self.bindir.mkdir()
        self.log = self.root / "path-claude.log"
        (self.bindir / "claude").write_text(
            "#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$ORCH_PATH_CLAUDE_LOG\"\nexit 0\n",
            encoding="utf-8",
        )
        (self.bindir / "claude").chmod(0o755)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _env(self, root: Path | None = None) -> dict[str, str]:
        env = os.environ.copy()
        env.pop("ORCH_CLAUDE", None)
        env["PATH"] = str(self.bindir) + os.pathsep + env.get("PATH", "")
        env["ORCH_PATH_CLAUDE_LOG"] = str(self.log)
        env["TEAM_ROOT"] = str(root or self.root)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return env

    def _start(self, *args: str, root: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(SCRIPT), *args],
            cwd=root or self.root,
            env=self._env(root),
            text=True,
            capture_output=True,
        )

    def test_unplanned_unit_refuses_without_a_process(self) -> None:
        started = self._start("start", "--unit", "박스확인")
        self.assertNotEqual(started.returncode, 0, started.stdout + started.stderr)
        parsed = parse_record(started.stdout)
        self.assertEqual(parsed["state"], "거부")
        self.assertEqual(parsed["handle"], "")
        self.assertIn("계획", parsed["reason"])
        self.assertFalse(self.log.exists())
        self.assertFalse((self.root / ".team" / "orchestrator").exists())

    def test_planned_unit_without_a_worktree_refuses(self) -> None:
        write_work(
            self.root,
            "78",
            "- 검증용 | 없음 | scripts/orchestrator.py | python3 scripts/orchestrator_test.py",
            GO,
        )
        started = self._start("start", "--unit", "검증용")
        self.assertNotEqual(started.returncode, 0, started.stdout + started.stderr)
        parsed = parse_record(started.stdout)
        self.assertEqual(parsed["state"], "거부")
        self.assertEqual(parsed["handle"], "")
        self.assertIn("작업 폴더", parsed["reason"])
        self.assertFalse(self.log.exists())

    def test_suite_never_calls_a_path_claude(self) -> None:
        if os.environ.get("ORCH_SUITE_CHILD") == "1":
            return
        env = os.environ.copy()
        env.pop("ORCH_CLAUDE", None)
        env["PATH"] = str(self.bindir) + os.pathsep + env.get("PATH", "")
        env["ORCH_PATH_CLAUDE_LOG"] = str(self.log)
        env["ORCH_SUITE_CHILD"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        done = subprocess.run(
            ["python3", str(SCRIPT.with_name("orchestrator_test.py"))],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=120,
        )
        called = self.log.read_text(encoding="utf-8") if self.log.exists() else ""
        self.assertEqual(called, "", called)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


class TrackerRegressionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_issue_tracker_still_reads_when_orchestrator_key_exists(self) -> None:
        team = self.root / ".team"
        team.mkdir()
        (team / "adapters.lock").write_text(
            "# 선택\nissue-tracker: github\norchestrator: native\n",
            encoding="utf-8",
        )
        bindir = install_fake_gh(self.root)
        env = os.environ.copy()
        env["TEAM_ROOT"] = str(self.root)
        env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
        env["GH_LOG"] = str(self.root / "gh.log")
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        done = subprocess.run(
            ["python3", str(SESSION), "new", "72", "--session", "dev"],
            cwd=self.root,
            env=env,
            text=True,
            capture_output=True,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        task = (team / "sessions" / "72" / "task.md").read_text(encoding="utf-8")
        self.assertIn("이슈 72", task)
        log = (self.root / "gh.log").read_text(encoding="utf-8")
        self.assertIn("issue view 72", log)


GO = "2026-11-26T00:00:00Z Codex go 승인\n"
NO_GO = "2026-11-26T00:00:00Z Codex 시작 초안\n"


def write_work(root: Path, work_id: str, plan: str, log: str) -> None:
    folder = root / ".team" / "sessions" / work_id
    folder.mkdir(parents=True)
    (folder / "task.md").write_text(f"# 작업\n\n## 계획\n\n{plan}\n", encoding="utf-8")
    (folder / "log.md").write_text(log, encoding="utf-8")


SPACED_PLAN = (
    "- 멈춤 계획 | 없음 | docs/a.md | python3 scripts/orchestrator_test.py\n"
    "- Claude 시작 | 멈춤 계획 | scripts/orchestrator.py | python3 scripts/orchestrator_test.py\n"
    "- 시작 경계 | 없음 | scripts/orchestrator_test.py | python3 scripts/orchestrator_test.py"
)


class SpacedUnitTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        write_work(self.root, "78", SPACED_PLAN, GO)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_spaced_name_starts_after_admit_allows_it(self) -> None:
        admitted = run_orch(
            self.root,
            "admit",
            "--work",
            "78",
            "--unit",
            "Claude 시작",
            "--finished",
            "멈춤 계획",
        )
        self.assertEqual(admitted.returncode, 0, admitted.stderr)
        allowed = parse_record(admitted.stdout)
        self.assertEqual(allowed["state"], "허용")
        self.assertEqual(allowed["line"], "Claude 시작")
        dest = place_worktree(self.root, "78")
        try:
            started = run_orch(
                self.root,
                "start",
                "--unit",
                "Claude 시작",
                "--finished",
                "멈춤 계획",
            )
        finally:
            shutil.rmtree(dest, ignore_errors=True)
        self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
        parsed = parse_record(started.stdout)
        self.assertEqual(parsed["ok"], "예")
        self.assertEqual(parsed["state"], "허용")
        self.assertTrue(parsed["handle"].startswith("native-"))
        self.assertNotIn("계획에 없는", parsed["reason"])

    def test_two_spaced_names_stay_whole(self) -> None:
        dest = place_worktree(self.root, "78")
        try:
            started = run_orch(self.root, "start", "--work", "78")
        finally:
            shutil.rmtree(dest, ignore_errors=True)
        self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
        parsed = parse_record(started.stdout)
        self.assertEqual(parsed["ok"], "예")
        self.assertEqual(parsed["line"], "멈춤 계획 시작 경계")
        self.assertEqual(parsed["handle"].count("native-"), 2)


class NoteGuardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        write_work(
            self.root,
            "780091",
            "- 맡은단위 | 없음 | scripts/a.py | python3 scripts/a_test.py\n"
            "- 다른단위 | 없음 | scripts/b.py | python3 scripts/b_test.py",
            GO,
        )
        (self.root / ".team" / "sessions" / "780091" / "state.md").write_text(
            "# 상태\n\n## 결정\n\n- 비밀결정문장\n\n## 다음 할 일\n\n그대로\n",
            encoding="utf-8",
        )
        bindir = self.root / "bin"
        bindir.mkdir()
        (bindir / "claude").write_text(
            "#!/bin/sh\n"
            'printf \'%s\\n\' "$*" > "$ORCH_ARGV"\n'
            'mkdir -p .team/sessions/780091\n'
            'printf \'%s\\n\' \'# 상태\' \'\' \'## 결정\' \'\' \'- 비밀결정문장\' \'- 워커결정\' '
            '> .team/sessions/780091/state.md\n'
            'printf \'%s\\n\' \'2026-11-27T00:00:00Z Claude Code go 워커승인\' '
            '> .team/sessions/780091/log.md\n'
            'if [ -n "$NOTE_ROOT" ]; then\n'
            '  python3 -c \'from pathlib import Path; import os; '
            'p = Path(os.environ["NOTE_ROOT"]) / ".team/sessions/780091/state.md"; '
            't = p.read_text(encoding="utf-8"); n = "- 비밀결정문장\\n"; '
            'p.write_text(t.replace(n, n + "- 워커결정\\n", 1), encoding="utf-8")\'\n'
            '  printf \'%s\\n\' \'2026-11-27T00:00:00Z Claude Code go 워커승인\' '
            '>> "$NOTE_ROOT/.team/sessions/780091/log.md"\n'
            'fi\n'
            'printf \'%s\\n\' \'# 결과\' \'\' \'## 결과\' \'\' \'PASS 위조\' > result.md\n'
            "exit 0\n",
            encoding="utf-8",
        )
        (bindir / "claude").chmod(0o755)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["TEAM_ROOT"] = str(self.root)
        env["NOTE_ROOT"] = str(self.root)
        env["ORCH_ARGV"] = str(self.root / "prompt.txt")
        env["ORCH_CLAUDE"] = str(self.root / "bin" / "claude")
        env["PATH"] = str(self.root / "bin") + os.pathsep + env.get("PATH", "")
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            ["python3", str(SCRIPT), *args],
            cwd=self.root,
            env=env,
            text=True,
            capture_output=True,
        )

    def test_changed_decision_or_approval_is_not_accepted(self) -> None:
        dest = place_worktree(self.root, "780091")
        try:
            started = self._run("start", "--unit", "맡은단위")
            self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
            parsed = parse_record(started.stdout)
            seen = ""
            for _ in range(40):
                polled = self._run("poll", "--handle", parsed["handle"])
                seen = parse_record(polled.stdout)["state"]
                if seen == "끝":
                    break
                time.sleep(0.05)
            self.assertEqual(seen, "끝")
            collected = self._run("collect", "--handle", parsed["handle"])
        finally:
            shutil.rmtree(dest, ignore_errors=True)
        self.assertEqual(collected.returncode, 0, collected.stderr)
        done = parse_record(collected.stdout)
        self.assertEqual(done["state"], "문제")
        self.assertEqual(done["line"], "")
        self.assertIn("워커결정", done["reason"])
        self.assertIn("워커승인", done["reason"])
        prompt = (self.root / "prompt.txt").read_text(encoding="utf-8")
        self.assertIn("맡은단위", prompt)
        self.assertIn("scripts/a.py", prompt)
        self.assertNotIn("다른단위", prompt)
        self.assertNotIn("비밀결정문장", prompt)
        root_state = (
            self.root / ".team" / "sessions" / "780091" / "state.md"
        ).read_text(encoding="utf-8")
        root_log = (
            self.root / ".team" / "sessions" / "780091" / "log.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn("워커결정", root_state)
        self.assertNotIn("워커승인", root_log)
        self.assertIn("비밀결정문장", root_state)
        later = self._run("admit", "--work", "780091", "--unit", "다른단위")
        self.assertNotIn("워커승인", later.stdout)


class GateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_missing_go_refuses_and_does_not_start(self) -> None:
        write_work(
            self.root,
            "73",
            "- 읽기 | 없음 | scripts/a.py | python3 scripts/a_test.py",
            NO_GO,
        )
        module = load_module(SCRIPT, "orchestrator_gate_go")
        decision = module.admit_work(self.root, "73", running=0)
        self.assertEqual(decision["ok"], "아니오")
        self.assertEqual(decision["state"], "거부")
        self.assertIn("go", decision["reason"])
        started = run_orch(self.root, "start", "--work", "73")
        self.assertNotEqual(started.returncode, 0)
        self.assertIn("go", started.stdout)
        self.assertFalse((self.root / ".team" / "orchestrator").exists())

    def test_overlapping_files_refuse_parallel(self) -> None:
        write_work(
            self.root,
            "73",
            "- 읽기 | 없음 | scripts/a.py | python3 scripts/a_test.py\n"
            "- 쓰기 | 없음 | scripts/a.py docs/x.md | python3 scripts/b_test.py",
            GO,
        )
        module = load_module(SCRIPT, "orchestrator_gate_overlap")
        decision = module.admit_work(self.root, "73", running=0)
        self.assertEqual(decision["state"], "거부")
        self.assertIn("겹", decision["reason"])
        self.assertIn("scripts/a.py", decision["reason"])

    def test_parent_directory_overlaps_and_suffix_does_not(self) -> None:
        module = load_module(SCRIPT, "orchestrator_gate_dir")
        self.assertTrue(module.paths_overlap("scripts", "scripts/a.py"))
        self.assertFalse(module.paths_overlap("scripts/a.py", "scripts/a.py.bak"))
        write_work(
            self.root,
            "73",
            "- 상위 | 없음 | scripts | python3 scripts/a_test.py\n"
            "- 하위 | 없음 | scripts/a.py | python3 scripts/a_test.py",
            GO,
        )
        decision = module.admit_work(self.root, "73", running=0)
        self.assertEqual(decision["state"], "거부")
        self.assertIn("겹", decision["reason"])

    def test_result_dependency_refuses_parallel_until_finished(self) -> None:
        write_work(
            self.root,
            "73",
            "- 읽기 | 없음 | scripts/a.py | python3 scripts/a_test.py\n"
            "- 쓰기 | 읽기 | scripts/b.py | python3 scripts/b_test.py",
            GO,
        )
        module = load_module(SCRIPT, "orchestrator_gate_dep")
        both = module.admit_work(self.root, "73", running=0)
        self.assertEqual(both["state"], "거부")
        self.assertIn("결과", both["reason"])
        waiting = module.admit_work(self.root, "73", running=0, selected=["쓰기"])
        self.assertEqual(waiting["state"], "거부")
        done = module.admit_work(
            self.root, "73", running=0, selected=["쓰기"], finished=["읽기"]
        )
        self.assertEqual(done["ok"], "예")
        self.assertEqual(done["state"], "허용")

    def test_running_limit_refuses(self) -> None:
        write_work(
            self.root,
            "73",
            "- 읽기 | 없음 | scripts/a.py | python3 scripts/a_test.py",
            GO,
        )
        module = load_module(SCRIPT, "orchestrator_gate_limit")
        self.assertEqual(module.WORKER_LIMIT, 3)
        over = module.admit_work(self.root, "73", running=3)
        self.assertEqual(over["state"], "거부")
        self.assertIn("3", over["reason"])
        ok = module.admit_work(self.root, "73", running=2)
        self.assertEqual(ok["state"], "허용")

    def test_cli_allows_a_clean_plan(self) -> None:
        write_work(
            self.root,
            "73",
            "- 읽기 | 없음 | scripts/a.py | python3 scripts/a_test.py\n"
            "- 쓰기 | 없음 | scripts/b.py | python3 scripts/b_test.py",
            GO,
        )
        done = run_orch(self.root, "admit", "--work", "73", "--running", "0")
        self.assertEqual(done.returncode, 0, done.stderr)
        parsed = parse_record(done.stdout)
        self.assertEqual(tuple(parsed), FIELDS)
        self.assertEqual(parsed["state"], "허용")
        dest = place_worktree(self.root, "73")
        try:
            started = run_orch(self.root, "start", "--work", "73", "--running", "0")
            self.assertEqual(started.returncode, 0, started.stderr)
            self.assertTrue(parse_record(started.stdout)["handle"].startswith("native-"))
        finally:
            shutil.rmtree(dest, ignore_errors=True)

    def test_start_unit_without_go_does_not_open_a_handle(self) -> None:
        write_work(
            self.root,
            "73",
            "- 읽기 | 없음 | scripts/a.py | python3 scripts/a_test.py",
            NO_GO,
        )
        done = run_orch(self.root, "start", "--unit", "읽기")
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("go", done.stdout)
        self.assertFalse((self.root / ".team" / "orchestrator").exists())

    def test_dependency_starts_the_ready_unit_then_the_next(self) -> None:
        write_work(
            self.root,
            "73",
            "- 읽기 | 없음 | scripts/a.py | python3 scripts/a_test.py\n"
            "- 쓰기 | 읽기 | scripts/b.py | python3 scripts/b_test.py",
            GO,
        )
        dest = place_worktree(self.root, "73")
        try:
            first = run_orch(self.root, "start", "--work", "73")
            self.assertEqual(first.returncode, 0, first.stderr)
            parsed = parse_record(first.stdout)
            self.assertEqual(parsed["state"], "허용")
            self.assertIn("읽기", parsed["line"])
            self.assertNotIn("쓰기", parsed["line"])
            self.assertTrue(parsed["handle"].startswith("native-"))
            named = run_orch(self.root, "start", "--work", "73", "--unit", "읽기")
            self.assertEqual(named.returncode, 0, named.stderr)
            self.assertIn("읽기", parse_record(named.stdout)["line"])
            nxt = run_orch(
                self.root,
                "start",
                "--work",
                "73",
                "--unit",
                "쓰기",
                "--finished",
                "읽기",
            )
            self.assertEqual(nxt.returncode, 0, nxt.stderr)
            self.assertIn("쓰기", parse_record(nxt.stdout)["line"])
            self.assertTrue(parse_record(nxt.stdout)["handle"].startswith("native-"))
            admitted = run_orch(self.root, "admit", "--work", "73", "--finished", "읽기")
            self.assertEqual(admitted.returncode, 0, admitted.stderr)
            self.assertEqual(parse_record(admitted.stdout)["state"], "허용")
            self.assertFalse((dest / ".team" / "orchestrator").exists())
        finally:
            shutil.rmtree(dest, ignore_errors=True)


def init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=path, check=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "빈 커밋", "-q"],
        cwd=path,
        check=True,
        capture_output=True,
    )


class PrepareTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.box = Path(self.tmp.name)
        self.repo = self.box / "dam"
        init_repo(self.repo)
        install_fake_gh(self.repo)
        self._old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = str(self.repo / "bin") + os.pathsep + self._old_path

    def tearDown(self) -> None:
        os.environ["PATH"] = self._old_path
        subprocess.run(
            ["git", "-C", str(self.repo), "worktree", "list", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
        )
        for path in self.box.glob("dam-*"):
            subprocess.run(
                ["git", "-C", str(self.repo), "worktree", "remove", "--force", str(path)],
                check=False,
                capture_output=True,
            )
        subprocess.run(
            ["git", "-C", str(self.repo), "branch", "-D", "worker/74", "worker/75"],
            check=False,
            capture_output=True,
        )
        self.tmp.cleanup()

    def test_prepare_makes_notes_branch_and_worktree(self) -> None:
        module = load_module(SCRIPT, "orchestrator_prepare")
        record = module.prepare_unit(self.repo, "74", "cursor")
        self.assertEqual(record["ok"], "예")
        self.assertEqual(record["handle"], "worker/74")
        worktree = self.repo.parent / "dam-74"
        self.assertTrue(worktree.is_dir())
        self.assertTrue((self.repo / ".team" / "sessions" / "74" / "task.md").is_file())
        self.assertTrue((self.repo / ".team" / "sessions" / "74" / "state.md").is_file())
        state = (self.repo / ".team" / "sessions" / "74" / "state.md").read_text(encoding="utf-8")
        self.assertIn("작업 폴더 생성:", state)
        branches = subprocess.run(
            ["git", "-C", str(self.repo), "branch", "--list", "worker/74"],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("worker/74", branches.stdout)
        dam_branches = subprocess.run(
            ["git", "-C", str(ROOT), "branch", "--list", "worker/74"],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(dam_branches.stdout.strip(), "")

    def test_existing_worktree_is_not_overwritten(self) -> None:
        module = load_module(SCRIPT, "orchestrator_prepare_again")
        first = module.prepare_unit(self.repo, "74", "cursor")
        self.assertEqual(first["ok"], "예")
        task = self.repo / ".team" / "sessions" / "74" / "task.md"
        task.write_text(task.read_text(encoding="utf-8") + "\n손글씨\n", encoding="utf-8")
        before = task.read_bytes()
        marker = self.repo.parent / "dam-74" / "keep.txt"
        marker.write_text("그대로\n", encoding="utf-8")
        second = module.prepare_unit(self.repo, "74", "cursor")
        self.assertEqual(second["ok"], "아니오")
        self.assertIn("이미", second["reason"])
        self.assertEqual(task.read_bytes(), before)
        self.assertEqual(marker.read_text(encoding="utf-8"), "그대로\n")

    def test_worker_reads_only_its_task_and_state(self) -> None:
        module = load_module(SCRIPT, "orchestrator_brief")
        self.assertEqual(module.prepare_unit(self.repo, "74", "cursor")["ok"], "예")
        self.assertEqual(module.prepare_unit(self.repo, "75", "cursor")["ok"], "예")
        folder = self.repo / ".team" / "sessions" / "74"
        (folder / "log.md").write_text("LOG-SECRET-74\n", encoding="utf-8")
        (folder / "result.md").write_text("RESULT-SECRET-74\n", encoding="utf-8")
        other = self.repo / ".team" / "sessions" / "75" / "task.md"
        other.write_text("OTHER-SECRET-75\n", encoding="utf-8")
        brief = module.worker_brief(self.repo, "74")
        self.assertIn("task.md", brief)
        self.assertIn("state.md", brief)
        self.assertNotIn("LOG-SECRET-74", brief)
        self.assertNotIn("RESULT-SECRET-74", brief)
        self.assertNotIn("OTHER-SECRET-75", brief)
        target = self.repo.parent / "dam-75" / "nope.txt"
        refused = module.guarded_write(self.repo.parent / "dam-74", "../dam-75/nope.txt", "침범\n")
        self.assertEqual(refused["ok"], "아니오")
        self.assertFalse(target.exists())

    def test_cli_prepare_prints_branch_and_time(self) -> None:
        done = run_orch(self.repo, "prepare", "--work", "74", "--session", "cursor")
        self.assertEqual(done.returncode, 0, done.stderr)
        parsed = parse_record(done.stdout)
        self.assertEqual(parsed["handle"], "worker/74")
        self.assertEqual(parsed["ok"], "예")
        state = (self.repo / ".team" / "sessions" / "74" / "state.md").read_text(encoding="utf-8")
        self.assertIn("작업 폴더 생성:", state)
        brief = run_orch(self.repo, "brief", "--work", "74")
        self.assertEqual(brief.returncode, 0, brief.stderr)
        self.assertNotIn("LOG-SECRET", brief.stdout)


class JudgeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        install_marker(self.root, "claude")
        install_marker(self.root, "codex")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_four_outcomes(self) -> None:
        module = load_module(SCRIPT, "orchestrator_judge")
        self.assertEqual(module.judge(0, "PASS 끝", True), "성공")
        self.assertEqual(module.judge(0, "ISSUES 남음", True), "문제")
        self.assertEqual(module.judge(0, "BLOCKED 막힘", False), "문제")
        self.assertEqual(module.judge(2, "PASS 끝", True), "실패")
        self.assertEqual(module.judge(0, "", True), "미완")
        self.assertEqual(module.judge(0, "(아직 없음)", True), "미완")
        self.assertEqual(module.judge(0, "PASS 끝", False), "미완")
        self.assertEqual(module.judge(0, "PASS 끝", True, turn_failed=True), "실패")

    def test_collect_reads_only_the_result_line(self) -> None:
        folder = self.root / ".team" / "sessions" / "75"
        folder.mkdir(parents=True)
        (folder / "result.md").write_text(
            "# 결과 75\n\n## 결과\n\nPASS 한줄\n\n## 교훈 후보\n\n- EXTRA-BODY\n",
            encoding="utf-8",
        )
        (folder / "state.md").write_text(
            "# 상태\n\n## 다음 할 일\n\n남은 일을 적었다\n",
            encoding="utf-8",
        )
        module = load_module(SCRIPT, "orchestrator_collect")
        record = module.collect_work(self.root, "75")
        self.assertEqual(record["line"], "PASS 한줄")
        self.assertEqual(record["state"], "성공")
        self.assertNotIn("EXTRA-BODY", record["line"])
        self.assertNotIn("교훈", record["line"])

    def test_secret_does_not_remain_in_output(self) -> None:
        token = "ghp_" + ("A" * 36)
        folder = self.root / ".team" / "sessions" / "75"
        folder.mkdir(parents=True)
        (folder / "result.md").write_text(
            f"# 결과\n\n## 결과\n\nPASS {token}\n\n## 교훈 후보\n\n- {token}\n",
            encoding="utf-8",
        )
        (folder / "state.md").write_text(
            "# 상태\n\n## 다음 할 일\n\n고쳤다\n",
            encoding="utf-8",
        )
        module = load_module(SCRIPT, "orchestrator_secret")
        record = module.collect_work(self.root, "75")
        self.assertNotIn(token, record["line"])
        self.assertNotIn(token, (folder / "result.md").read_text(encoding="utf-8"))
        self.assertNotIn(token, (folder / "worker-out.txt").read_text(encoding="utf-8"))
        self.assertTrue(record["line"].startswith("PASS"))
        self.assertFalse((self.root / "marker.txt").exists())

    def test_github_token_shapes_leave_every_note(self) -> None:
        gho = "gho_" + ("B" * 36)
        ghp = "ghp_" + ("C" * 36)
        folder = self.root / ".team" / "sessions" / "75"
        folder.mkdir(parents=True)
        (folder / "result.md").write_text(
            f"# 결과\n\n## 결과\n\nPASS {gho}\n\n## 교훈 후보\n\n- EXTRA-BODY {ghp}\n",
            encoding="utf-8",
        )
        (folder / "state.md").write_text(
            "# 상태\n\n## 다음 할 일\n\n고쳤다\n",
            encoding="utf-8",
        )
        (folder / "log.md").write_text(f"2026-11-26T00:00:00Z Codex 시작 {ghp}\n", encoding="utf-8")
        done = run_orch(self.root, "collect", "--work", "75")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn(gho, done.stdout)
        self.assertNotIn(ghp, done.stdout)
        self.assertTrue(parse_record(done.stdout)["line"].startswith("PASS"))
        result = (folder / "result.md").read_text(encoding="utf-8")
        out = (folder / "worker-out.txt").read_text(encoding="utf-8")
        log = (folder / "log.md").read_text(encoding="utf-8")
        self.assertNotIn(gho, result)
        self.assertNotIn(ghp, result)
        self.assertNotIn(gho, out)
        self.assertNotIn(ghp, out)
        self.assertNotIn(ghp, log)
        self.assertNotIn(gho, log)
        self.assertIn("EXTRA-BODY", result)

    def test_stall_notice_for_a_live_worker(self) -> None:
        module = load_module(SCRIPT, "orchestrator_stall")
        self.assertEqual(module.STALL_LIMIT_SECONDS, 900)
        old = module.datetime(2026, 11, 26, 0, 0, tzinfo=module.timezone.utc)
        now = old + module.timedelta(seconds=901)
        self.assertEqual(module.stall_notice(True, old, now), "멈춤 의심")
        self.assertEqual(module.stall_notice(True, now, now), "")
        self.assertEqual(module.stall_notice(False, old, now), "")

    def test_cli_judge_and_collect(self) -> None:
        folder = self.root / ".team" / "sessions" / "75"
        folder.mkdir(parents=True)
        (folder / "result.md").write_text(
            "# 결과\n\n## 결과\n\n\n## 교훈 후보\n\n- EXTRA-BODY\n",
            encoding="utf-8",
        )
        (folder / "state.md").write_text("# 상태\n\n## 다음 할 일\n\n고쳤다\n", encoding="utf-8")
        judged = run_orch(self.root, "judge", "--exit", "0", "--line", "ISSUES 남음", "--next-updated")
        self.assertEqual(judged.returncode, 0, judged.stderr)
        self.assertEqual(parse_record(judged.stdout)["state"], "문제")
        collected = run_orch(self.root, "collect", "--work", "75")
        self.assertEqual(collected.returncode, 0, collected.stderr)
        parsed = parse_record(collected.stdout)
        self.assertEqual(parsed["state"], "미완")
        self.assertNotIn("EXTRA-BODY", collected.stdout)


class ParallelBoardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_resume_uses_only_board_and_state(self) -> None:
        module = load_module(SCRIPT, "orchestrator_parallel")
        folder = self.root / ".team" / "sessions" / "76"
        folder.mkdir(parents=True)
        (folder / "log.md").write_text(
            "2026-11-26T01:02:03Z Codex 시작 작업\n",
            encoding="utf-8",
        )
        (folder / "state.md").write_text("# 상태 76\n\n## 지금 상태\n\n진행\n", encoding="utf-8")
        (folder / "task.md").write_text("TASK-SECRET\n", encoding="utf-8")
        board = self.root / ".team" / "board.md"
        board.write_text(
            "# 작업 현황\n\n- 76: 상태 진행, 담당 cursor, 막힘 없음\n",
            encoding="utf-8",
        )
        module.record_parallel(self.root, "76")
        before = module.resume_parallel(self.root)
        self.assertIn("마지막 로그 2026-11-26T01:02:03Z", before)
        self.assertIn("상태 진행", before)
        self.assertIn("담당 cursor", before)
        self.assertIn("막힘 없음", before)
        (folder / "log.md").unlink()
        (folder / "task.md").unlink()
        after = module.resume_parallel(self.root)
        self.assertEqual(after, before)
        self.assertNotIn("TASK-SECRET", after)

    def test_parallel_keeps_a_closed_github_clause(self) -> None:
        folder = self.root / ".team" / "sessions" / "76"
        folder.mkdir(parents=True)
        (folder / "log.md").write_text(
            "2026-11-26T01:02:03Z Codex 시작 작업\n",
            encoding="utf-8",
        )
        (folder / "state.md").write_text("# 상태 76\n\n## 지금 상태\n\n시작\n", encoding="utf-8")
        (self.root / ".team" / "sessions" / "77").mkdir(parents=True)
        board = self.root / ".team" / "board.md"
        board.write_text(
            "# 작업 현황\n\n"
            "- 76: 상태 시작, 담당 cursor, 막힘 없음, GitHub 닫힘\n"
            "- 77: 상태 시작, 담당 cursor, 막힘 없음, GitHub 검토 중, 검사 통과\n",
            encoding="utf-8",
        )
        context = load_module(ROOT / "scripts" / "session_context.py", "session_context_closed")
        before = context.render_start_context(self.root, "main")
        self.assertIn("열린 줄 1", before)
        self.assertNotIn("- 76:", before)
        done = run_orch(self.root, "parallel", "--work", "76")
        self.assertEqual(done.returncode, 0, done.stderr)
        text = board.read_text(encoding="utf-8")
        self.assertIn("마지막 로그 2026-11-26T01:02:03Z", text)
        self.assertTrue(
            text.splitlines()[2].endswith("GitHub 닫힘"),
            text,
        )
        after = context.render_start_context(self.root, "main")
        self.assertIn("열린 줄 1", after)
        self.assertNotIn("- 76:", after)

    def test_many_parallel_lines_become_one_short_line(self) -> None:
        context = load_module(ROOT / "scripts" / "session_context.py", "session_context_many")
        lines = [
            f"- {number}: 상태 시작, 담당 dev, 막힘 없음, 마지막 로그 2026-11-26T00:00:00Z"
            for number in range(1, 80)
        ]
        board = self.root / ".team" / "board.md"
        board.parent.mkdir(parents=True)
        board.write_text("# 작업 현황\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
        text = context.render_start_context(self.root, "main")
        self.assertEqual(text, context.SHORTEN_LINE)


class ProbeStepsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        install_marker(self.root, "claude")
        install_marker(self.root, "codex")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_probe_steps_print_and_do_not_launch(self) -> None:
        done = run_orch(self.root, "probe-steps")
        self.assertEqual(done.returncode, 0, done.stderr)
        for phrase in (
            "버전과 로그인",
            "시험용 작업 폴더",
            "Claude Code 읽기 전용",
            "세션 재개",
            "Codex 읽기 전용",
            "커밋",
            "시작 시간",
            "정리",
            "실행하지 않는다",
            "결과: 아직 없음",
        ):
            self.assertIn(phrase, done.stdout)
        self.assertFalse((self.root / "marker.txt").exists())
        doc = (ROOT / "docs" / "milestones" / "m5b-hr-p-check.md").read_text(encoding="utf-8")
        self.assertIn("결과: 아직 없음", doc)
        self.assertIn("샌드박스를 끄지 않는다", doc)


if __name__ == "__main__":
    unittest.main()
