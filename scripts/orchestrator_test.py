#!/usr/bin/env python3
"""오케스트레이터 어댑터의 실패 우선 검사."""

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
SCRIPT = ROOT / "scripts" / "orchestrator.py"
SESSION = ROOT / "scripts" / "team-session.py"
FIELDS = ("ok", "handle", "state", "line", "reason")


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
        native = module.start(self.root, "72")
        self.write_lock("orchestrator: fake\n")
        other = Path(self.tmp.name) / "fake-root"
        other.mkdir()
        (other / ".team").mkdir()
        (other / ".team" / "adapters.lock").write_text(
            "orchestrator: fake\n", encoding="utf-8"
        )
        fake = module.start(other, "72")
        self.assertEqual(tuple(native), FIELDS)
        self.assertEqual(tuple(fake), FIELDS)
        self.assertEqual(native["ok"], "예")
        self.assertEqual(fake["ok"], "예")
        self.assertEqual(native["state"], "대기")
        self.assertEqual(fake["state"], "대기")
        self.assertTrue(native["handle"].startswith("native-"))
        self.assertTrue(fake["handle"].startswith("fake-"))
        polled = module.poll(self.root, native["handle"])
        collected = module.collect(self.root, native["handle"])
        self.assertEqual(tuple(polled), FIELDS)
        self.assertEqual(tuple(collected), FIELDS)

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
            self.assertEqual(started.returncode, 0, started.stderr)
            parsed = parse_record(started.stdout)
            self.assertEqual(tuple(parsed), FIELDS)
            self.assertEqual(parsed["ok"], "예")
            self.assertTrue(parsed["handle"].startswith(f"{name}-"))
            polled = run_orch(root, "poll", "--handle", parsed["handle"])
            collected = run_orch(root, "collect", "--handle", parsed["handle"])
            self.assertEqual(polled.returncode, 0, polled.stderr)
            self.assertEqual(collected.returncode, 0, collected.stderr)
            self.assertEqual(tuple(parse_record(polled.stdout)), FIELDS)
            self.assertEqual(tuple(parse_record(collected.stdout)), FIELDS)
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


if __name__ == "__main__":
    unittest.main()
