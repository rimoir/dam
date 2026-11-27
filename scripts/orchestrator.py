#!/usr/bin/env python3
"""워커 시작, 지켜보기, 수거. 이 파일만 orchestrator 키를 읽는다.

native는 PATH의 claude만 띄운다. fake는 띄우지 않는다.
Codex는 미검증이라 띄우지 않는다. 다섯 칸은 그대로다.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from issue_tracker import redact  # noqa: E402
from session_context import (  # noqa: E402
    _named_section,
    _plan_path,
    log_has_go,
    open_board_lines,
    read_plan_units,
)

FIELDS = ("ok", "handle", "state", "line", "reason")
KNOWN = frozenset({"native", "fake"})
HANDLE = re.compile(r"^(native|fake)-[0-9]+$")
WORKER_LIMIT = 3  # 임시. 측정 뒤 고친다.
STALL_LIMIT_SECONDS = 900  # 임시. 측정 뒤 고친다.
MAX_TURNS = 40  # 임시. 측정 뒤 고친다.
# ADR 0007 제안의 push, PR, 머지를 넘기는 자리다. 이 문자열이 경계는 아니다.
ALLOWED_TOOLS = (
    "Bash(git status *) Bash(git diff *) Bash(git add *) Bash(git commit *) "
    "Bash(git push *) Bash(gh pr create *) Bash(gh pr comment *) "
    "Bash(gh pr merge *) Bash(python3 scripts/*)"
)
_NOTE_SUFFIXES = {".md", ".txt", ".json"}


class OrchestratorError(Exception):
    pass


def notes_root(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit)
    override = os.environ.get("TEAM_ROOT")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[1]


def blank(**over: str) -> dict[str, str]:
    record = {key: "" for key in FIELDS}
    record.update(over)
    return record


def render(record: dict[str, str]) -> str:
    return "".join(f"{key}: {record[key]}\n" for key in FIELDS)


def lock_name(root: Path) -> str:
    path = root / ".team" / "adapters.lock"
    if not path.is_file():
        return "native"
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        raise OrchestratorError("adapters.lock을 읽지 못했다") from None
    selected = ""
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip() != "orchestrator":
            continue
        selected = value.strip().strip('"').strip("'")
    return selected or "native"


def _store(root: Path) -> Path:
    folder = root / ".team" / "orchestrator"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _path(root: Path, handle: str) -> Path:
    if HANDLE.fullmatch(handle) is None:
        raise OrchestratorError("핸들이 없다")
    return root / ".team" / "orchestrator" / f"{handle}.json"


def _write(root: Path, record: dict[str, str]) -> None:
    path = _path(root, record["handle"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")


def _load(root: Path, handle: str) -> dict[str, str]:
    path = _path(root, handle)
    if not path.is_file():
        raise OrchestratorError("핸들이 없다")
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise OrchestratorError("핸들을 읽지 못했다") from None
    if not isinstance(loaded, dict):
        raise OrchestratorError("핸들을 읽지 못했다")
    return {str(key): str(value) for key, value in loaded.items()}


def _read(root: Path, handle: str) -> dict[str, str]:
    try:
        loaded = _load(root, handle)
    except OrchestratorError as exc:
        return blank(ok="아니오", state="거부", reason=str(exc))
    return blank(**{key: loaded.get(key, "") for key in FIELDS})


def _tool_choice() -> str:
    return os.environ.get("ORCH_TOOL", "claude").strip() or "claude"


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def resolve_claude() -> str | None:
    explicit = os.environ.get("ORCH_CLAUDE", "").strip()
    if explicit == "-":
        return None
    if explicit:
        path = Path(explicit)
        return str(path) if path.is_file() else None
    return shutil.which("claude")


def worker_cwd(root: Path, unit: str) -> Path | str:
    owner = work_owning_unit(root, unit)
    if not owner:
        return "계획에 없는 단위다"
    if owner == "*":
        return "단위가 여러 작업에 있다"
    if re.fullmatch(r"[0-9]+", owner) is None:
        return "작업ID가 이슈 번호가 아니다"
    dest = (root.resolve().parent / f"dam-{owner}").resolve()
    if not dest.is_dir():
        return "작업 폴더가 없다"
    notes = root.resolve()
    if dest == notes or _inside(notes, dest):
        return "작업 폴더가 노트 루트다"
    return dest


def worker_prompt(root: Path, unit: str) -> str:
    owner = work_owning_unit(root, unit)
    brief = unit
    if owner and owner != "*":
        try:
            brief = worker_brief(root, owner)
        except OrchestratorError:
            brief = unit
    return (
        brief
        + "\n끝이면 result.md의 결과 칸을 PASS, ISSUES, BLOCKED 중 하나로 시작해 채워라.\n"
        + "push와 PR과 머지는 이 작업 브랜치에서만 한다.\n"
    )


def _launch_claude(root: Path, handle: str, unit: str, cwd: Path) -> tuple[int, str] | str | None:
    binary = resolve_claude()
    if binary is None:
        return None
    exit_path = _store(root) / f"{handle}.exit"
    out_path = _store(root) / f"{handle}.out"
    wrapper = '"$ORCH_CLAUDE_BIN" "$@"; echo $? > "$ORCH_EXIT"'
    env = os.environ.copy()
    env["ORCH_EXIT"] = str(exit_path)
    env["ORCH_CLAUDE_BIN"] = binary
    out = out_path.open("w", encoding="utf-8")
    try:
        proc = subprocess.Popen(
            [
                "sh",
                "-c",
                wrapper,
                "sh",
                "-p",
                worker_prompt(root, unit),
                "--output-format",
                "json",
                "--permission-mode",
                "acceptEdits",
                "--permission-prompts",
                "none",
                "--max-turns",
                str(MAX_TURNS),
                "--allowedTools",
                ALLOWED_TOOLS,
            ],
            cwd=cwd,
            env=env,
            stdout=out,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    except OSError:
        return "claude를 띄우지 못했다"
    finally:
        out.close()
    return proc.pid, str(cwd)


def paths_overlap(left: str, right: str) -> bool:
    left_path = PurePosixPath(_plan_path(left))
    right_path = PurePosixPath(_plan_path(right))
    if str(left_path) in ("", ".") or str(right_path) in ("", "."):
        return False
    if left_path == right_path:
        return True
    try:
        left_path.relative_to(right_path)
        return True
    except ValueError:
        pass
    try:
        right_path.relative_to(left_path)
        return True
    except ValueError:
        return False


def _unit_files(files: str) -> tuple[str, ...]:
    return tuple(piece for piece in files.replace(",", " ").split() if piece)


def admit_work(
    root: Path,
    work_id: str,
    running: int = 0,
    selected: list[str] | None = None,
    finished: list[str] | None = None,
) -> dict[str, str]:
    folder = root / ".team" / "sessions" / work_id
    task_path = folder / "task.md"
    if not task_path.is_file():
        return blank(ok="아니오", state="거부", reason=f"task.md가 없다: {work_id}")
    log_path = folder / "log.md"
    log_text = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
    if not log_has_go(log_text):
        return blank(ok="아니오", state="거부", reason="go 없는 작업이다")
    units = read_plan_units(task_path.read_text(encoding="utf-8"))
    if not units:
        return blank(ok="아니오", state="거부", reason="계획 단위가 없다")
    by_name = {item[0]: item for item in units}
    names = list(selected) if selected else [item[0] for item in units]
    for name in names:
        if name not in by_name:
            return blank(ok="아니오", state="거부", reason=f"계획에 없는 단위다: {name}")
    file_sets = {name: _unit_files(by_name[name][2]) for name in names}
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            for left_file in file_sets[left]:
                for right_file in file_sets[right]:
                    if paths_overlap(left_file, right_file):
                        shown = _plan_path(left_file)
                        return blank(
                            ok="아니오",
                            state="거부",
                            reason=f"건드릴 파일이 겹친다: {shown}",
                        )
    done = set(finished or [])
    for name in names:
        dep = by_name[name][1].strip()
        if not dep or dep == "없음" or dep in done:
            continue
        return blank(
            ok="아니오",
            state="거부",
            reason=f"앞 단위 결과가 입력이다: {dep}",
        )
    if running + len(names) > WORKER_LIMIT:
        return blank(
            ok="아니오",
            state="거부",
            reason=f"동시 워커 상한 {WORKER_LIMIT}을 넘는다",
        )
    return blank(ok="예", state="허용", line=" ".join(names))


def _ready_names(root: Path, work_id: str, finished: list[str] | None) -> list[str] | dict[str, str]:
    folder = root / ".team" / "sessions" / work_id
    task_path = folder / "task.md"
    if not task_path.is_file():
        return blank(ok="아니오", state="거부", reason=f"task.md가 없다: {work_id}")
    log_path = folder / "log.md"
    log_text = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
    if not log_has_go(log_text):
        return blank(ok="아니오", state="거부", reason="go 없는 작업이다")
    units = read_plan_units(task_path.read_text(encoding="utf-8"))
    if not units:
        return blank(ok="아니오", state="거부", reason="계획 단위가 없다")
    done = set(finished or [])
    ready: list[str] = []
    blocked = ""
    for name, dep, _files, _check in units:
        if name in done:
            continue
        dep = dep.strip()
        if dep and dep != "없음" and dep not in done:
            blocked = f"앞 단위 결과가 입력이다: {dep}"
            continue
        ready.append(name)
    if not ready:
        return blank(ok="아니오", state="거부", reason=blocked or "계획 단위가 없다")
    return ready


def work_owning_unit(root: Path, unit: str) -> str | None:
    sessions = root / ".team" / "sessions"
    if not sessions.is_dir():
        return None
    found: list[str] = []
    for folder in sorted(path for path in sessions.iterdir() if path.is_dir()):
        task = folder / "task.md"
        if not task.is_file():
            continue
        try:
            text = task.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for name, _dep, _files, _check in read_plan_units(text):
            if name == unit:
                found.append(folder.name)
                break
    if len(found) > 1:
        return "*"
    if len(found) == 1:
        return found[0]
    return None


def start_work(
    root: Path,
    work_id: str,
    running: int = 0,
    selected: list[str] | None = None,
    finished: list[str] | None = None,
) -> dict[str, str]:
    if selected is None:
        ready = _ready_names(root, work_id, finished)
        if isinstance(ready, dict):
            return ready
        selected = ready
    decision = admit_work(
        root,
        work_id,
        running=running,
        selected=selected,
        finished=finished,
    )
    if decision["ok"] != "예":
        return decision
    handles: list[str] = []
    for name in decision["line"].split():
        record = start(root, name)
        if record["ok"] != "예":
            return record
        handles.append(record["handle"])
    decision["handle"] = ",".join(handles)
    return decision


def start(root: Path, unit: str) -> dict[str, str]:
    if not unit.strip():
        return blank(ok="아니오", state="거부", reason="단위가 없다")
    name = lock_name(root)
    if name not in KNOWN:
        return blank(
            ok="아니오",
            state="거부",
            reason=f"orchestrator 선택을 모른다: {name}",
        )
    if _tool_choice() == "codex":
        return blank(ok="아니오", state="거부", reason="Codex는 미검증이다")
    cwd = worker_cwd(root, unit)
    if isinstance(cwd, str):
        return blank(ok="아니오", state="거부", reason=cwd)
    folder = _store(root)
    number = 1 + sum(1 for _found in folder.glob(f"{name}-*.json"))
    record = blank(ok="예", handle=f"{name}-{number}", state="대기")
    extra: dict[str, str] = {"cwd": str(cwd)}
    owner = work_owning_unit(root, unit)
    if owner and owner != "*":
        extra["work"] = owner
    if name == "native":
        launched = _launch_claude(root, record["handle"], unit, cwd)
        if isinstance(launched, str):
            return blank(ok="아니오", state="거부", reason=launched)
        if launched is not None:
            pid, _cwd = launched
            record["state"] = "진행"
            extra["tool"] = "claude"
            extra["pid"] = str(pid)
    _write(root, {**record, **extra})
    return _read(root, record["handle"])


def poll(root: Path, handle: str) -> dict[str, str]:
    try:
        loaded = _load(root, handle)
    except OrchestratorError as exc:
        return blank(ok="아니오", state="거부", reason=str(exc))
    if loaded.get("tool") == "claude":
        exit_path = _store(root) / f"{handle}.exit"
        if exit_path.is_file():
            loaded["state"] = "끝"
            loaded["exit"] = exit_path.read_text(encoding="utf-8").strip()
        else:
            loaded["state"] = "진행"
        _write(root, loaded)
    return blank(**{key: loaded.get(key, "") for key in FIELDS})


def collect(root: Path, handle: str) -> dict[str, str]:
    polled = poll(root, handle)
    if polled["ok"] != "예" or polled["state"] != "끝":
        return polled
    try:
        loaded = _load(root, handle)
    except OrchestratorError as exc:
        return blank(ok="아니오", state="거부", reason=str(exc))
    cwd = Path(loaded.get("cwd") or root)
    owner = loaded.get("work", "")
    candidates = [cwd / "result.md"]
    if owner:
        candidates.append(cwd / ".team" / "sessions" / owner / "result.md")
        candidates.append(root / ".team" / "sessions" / owner / "result.md")
    result_path = next((path for path in candidates if path.is_file()), candidates[0])
    raw = result_path.read_text(encoding="utf-8") if result_path.is_file() else ""
    cleaned = redact_secret(raw)
    if result_path.is_file() and cleaned != raw:
        result_path.write_text(cleaned, encoding="utf-8")
    line = result_section_line(cleaned)
    try:
        code = int(loaded.get("exit", "0") or "0")
    except ValueError:
        code = 1
    state_text = ""
    if owner:
        for folder in (
            cwd / ".team" / "sessions" / owner,
            root / ".team" / "sessions" / owner,
        ):
            state_path = folder / "state.md"
            if state_path.is_file():
                state_text = state_path.read_text(encoding="utf-8")
            scrub_notes(folder)
    kind = judge(code, line, next_action_updated(state_text))
    record = blank(ok="예", handle=handle, state=kind, line=line)
    loaded.update(record)
    _write(root, loaded)
    return record


def _git(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def prepare_unit(repo: Path, work_id: str, session: str = "cursor") -> dict[str, str]:
    if re.fullmatch(r"[0-9]+", work_id) is None:
        return blank(ok="아니오", state="거부", reason=f"작업ID가 이슈 번호가 아니다: {work_id}")
    destination = repo.resolve().parent / f"dam-{work_id}"
    if destination.exists():
        return blank(ok="아니오", state="거부", reason="작업 폴더가 이미 있다")
    branch = f"worker/{work_id}"
    if _git(repo, ["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"]).returncode == 0:
        return blank(ok="아니오", state="거부", reason="브랜치가 이미 있다")
    env = os.environ.copy()
    env["TEAM_ROOT"] = str(repo)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    created = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("team-session.py")),
            "new",
            work_id,
            "--session",
            session,
        ],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if created.returncode != 0:
        return blank(ok="아니오", state="거부", reason="노트를 만들지 못했다")
    started = time.perf_counter()
    added = _git(repo, ["worktree", "add", "-b", branch, str(destination), "HEAD"])
    elapsed = time.perf_counter() - started
    if added.returncode != 0:
        return blank(ok="아니오", state="거부", reason="작업 폴더를 만들지 못했다")
    state = repo / ".team" / "sessions" / work_id / "state.md"
    text = state.read_text(encoding="utf-8") if state.is_file() else ""
    if text and not text.endswith("\n"):
        text += "\n"
    text += f"작업 폴더 생성: {elapsed:.3f}초\n"
    state.write_text(text, encoding="utf-8")
    return blank(ok="예", handle=branch, state="준비", line=str(destination))


def worker_brief(repo: Path, work_id: str) -> str:
    folder = repo / ".team" / "sessions" / work_id
    chunks: list[str] = []
    for name in ("task.md", "state.md"):
        path = folder / name
        if not path.is_file():
            raise OrchestratorError(f"{name}가 없다")
        chunks.append(name + "\n" + path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


_STAMP = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\b")
_BOARD_PREFIX = re.compile(r"^(- \S+: 상태 [^,]+, 담당 [^,]+, 막힘 [^,]+)")


def last_log_stamp(text: str) -> str:
    found = ""
    for raw in text.splitlines():
        match = _STAMP.match(raw.strip())
        if match:
            found = match.group(1)
    return found


def record_parallel(root: Path, work_id: str) -> dict[str, str]:
    folder = root / ".team" / "sessions" / work_id
    log_path = folder / "log.md"
    log_text = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
    stamp = last_log_stamp(log_text)
    if not stamp:
        return blank(ok="아니오", state="거부", reason="로그 시각이 없다")
    state_path = folder / "state.md"
    state = state_path.read_text(encoding="utf-8") if state_path.is_file() else ""
    marker = f"마지막 로그: {stamp}"
    if marker not in state:
        if state and not state.endswith("\n"):
            state += "\n"
        state_path.write_text(state + marker + "\n", encoding="utf-8")
    board_path = root / ".team" / "board.md"
    text = board_path.read_text(encoding="utf-8") if board_path.is_file() else ""
    prefix = f"- {work_id}:"
    found = False
    lines: list[str] = []
    for raw in text.splitlines():
        if raw.startswith(prefix):
            found = True
            match = _BOARD_PREFIX.match(raw)
            base = match.group(1) if match else raw.split(", 마지막 로그", 1)[0].split(", GitHub", 1)[0]
            github = ""
            github_at = raw.find(", GitHub ")
            if github_at != -1:
                github = raw[github_at:]
            lines.append(f"{base}, 마지막 로그 {stamp}{github}")
        else:
            lines.append(raw)
    if not found:
        lines.append(f"- {work_id}: 상태 시작, 담당 cursor, 막힘 없음, 마지막 로그 {stamp}")
    board_path.parent.mkdir(parents=True, exist_ok=True)
    board_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return blank(ok="예", state="적음", line=stamp)


def resume_parallel(root: Path) -> str:
    kept: list[str] = []
    for work_id, raw in open_board_lines(root):
        if "마지막 로그" not in raw:
            continue
        state_path = root / ".team" / "sessions" / work_id / "state.md"
        if not state_path.is_file():
            continue
        state = state_path.read_text(encoding="utf-8")
        match = re.search(r"마지막 로그 ([^,]+)", raw)
        if match and match.group(1).strip() in state:
            kept.append(raw)
    if not kept:
        return ""
    return "\n".join(kept) + "\n"


def redact_secret(text: str) -> str:
    return redact(text)


def scrub_notes(folder: Path) -> None:
    if not folder.is_dir():
        return
    for path in folder.iterdir():
        if not path.is_file() or path.suffix not in _NOTE_SUFFIXES:
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        cleaned = redact(raw)
        if cleaned != raw:
            path.write_text(cleaned, encoding="utf-8")


def judge(
    exit_code: int,
    result_line: str,
    next_updated: bool,
    turn_failed: bool = False,
) -> str:
    if exit_code != 0 or turn_failed:
        return "실패"
    line = result_line.strip()
    if line.startswith("ISSUES") or line.startswith("BLOCKED"):
        return "문제"
    if not line or line == "(아직 없음)":
        return "미완"
    if line.startswith("PASS") and next_updated:
        return "성공"
    return "미완"


def stall_notice(alive: bool, last_log: datetime, now: datetime) -> str:
    if alive and (now - last_log).total_seconds() > STALL_LIMIT_SECONDS:
        return "멈춤 의심"
    return ""


def result_section_line(text: str) -> str:
    for raw in _named_section(text, "## 결과").splitlines():
        line = raw.strip()
        if line:
            return line
    return ""


def next_action_updated(state_text: str) -> bool:
    section = _named_section(state_text, "## 다음 할 일").strip()
    if not section or "계획을 채운 뒤" in section:
        return False
    return True


def collect_work(root: Path, work_id: str, exit_code: int = 0) -> dict[str, str]:
    folder = root / ".team" / "sessions" / work_id
    result_path = folder / "result.md"
    state_path = folder / "state.md"
    raw = result_path.read_text(encoding="utf-8") if result_path.is_file() else ""
    cleaned = redact_secret(raw)
    if result_path.is_file() and cleaned != raw:
        result_path.write_text(cleaned, encoding="utf-8")
    line = result_section_line(cleaned)
    if folder.is_dir():
        (folder / "worker-out.txt").write_text(line + "\n", encoding="utf-8")
    state = state_path.read_text(encoding="utf-8") if state_path.is_file() else ""
    kind = judge(exit_code, line, next_action_updated(state))
    scrub_notes(folder)
    return blank(ok="예", state=kind, line=line)


def guarded_write(worktree: Path, relative: str, data: str) -> dict[str, str]:
    root = worktree.resolve()
    target = (root / relative).resolve()
    if not root.is_dir():
        return blank(ok="아니오", state="거부", reason="작업 폴더가 없다")
    try:
        target.relative_to(root)
    except ValueError:
        return blank(ok="아니오", state="거부", reason="다른 작업 폴더다")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(data, encoding="utf-8")
    return blank(ok="예", state="썼다")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="워커 시작과 수거 어댑터.")
    parser.add_argument("--root", default="")
    sub = parser.add_subparsers(dest="command", required=True)
    start_cmd = sub.add_parser("start", help="단위를 받아 핸들을 만든다.")
    start_cmd.add_argument("--unit", default="")
    start_cmd.add_argument("--work", default="")
    start_cmd.add_argument("--running", type=int, default=0)
    start_cmd.add_argument("--finished", action="append", default=[])
    admit_cmd = sub.add_parser("admit", help="시작 전 검사를 읽고 허용 또는 거부를 낸다.")
    admit_cmd.add_argument("--work", required=True)
    admit_cmd.add_argument("--running", type=int, default=0)
    admit_cmd.add_argument("--unit", action="append", default=[])
    admit_cmd.add_argument("--finished", action="append", default=[])
    prepare_cmd = sub.add_parser("prepare", help="노트, 브랜치, 작업 폴더를 만든다.")
    prepare_cmd.add_argument("--work", required=True)
    prepare_cmd.add_argument("--session", default="cursor")
    brief_cmd = sub.add_parser("brief", help="task.md와 상태 파일만 낸다.")
    brief_cmd.add_argument("--work", required=True)
    judge_cmd = sub.add_parser("judge", help="끝남 넷 중 하나를 낸다.")
    judge_cmd.add_argument("--exit", type=int, required=True)
    judge_cmd.add_argument("--line", default="")
    judge_cmd.add_argument("--next-updated", action="store_true")
    judge_cmd.add_argument("--turn-failed", action="store_true")
    collect_cmd = sub.add_parser("collect-work", help="결과 칸 한 줄만 거둔다.")
    collect_cmd.add_argument("--work", required=True)
    stall_cmd = sub.add_parser("stall", help="살아 있는데 로그가 오래되면 알린다.")
    stall_cmd.add_argument("--last", required=True)
    stall_cmd.add_argument("--now", required=True)
    stall_cmd.add_argument("--alive", action="store_true")
    parallel_cmd = sub.add_parser("parallel", help="현황판에 마지막 로그 시각을 적는다.")
    parallel_cmd.add_argument("--work", required=True)
    resume_cmd = sub.add_parser("resume-parallel", help="현황판과 상태 파일만으로 줄을 다시 읽는다.")
    sub.add_parser("probe-steps", help="HR P PC 확인 절차를 인쇄만 한다.")
    poll_cmd = sub.add_parser("poll", help="핸들의 상태를 읽는다.")
    poll_cmd.add_argument("--handle", required=True)
    collect_cmd = sub.add_parser("collect", help="결과 한 줄을 읽는다.")
    collect_cmd.add_argument("--handle", default="")
    collect_cmd.add_argument("--work", default="")
    args = parser.parse_args(argv)
    root = notes_root(args.root or None)
    try:
        if args.command == "start" and args.work:
            chosen = [args.unit] if args.unit else None
            record = start_work(
                root,
                args.work,
                running=args.running,
                selected=chosen,
                finished=args.finished or None,
            )
        elif args.command == "start":
            owner = work_owning_unit(root, args.unit) if args.unit else None
            if owner == "*":
                record = blank(ok="아니오", state="거부", reason="단위가 여러 작업에 있다")
            elif owner:
                record = start_work(
                    root,
                    owner,
                    running=args.running,
                    selected=[args.unit],
                    finished=args.finished or None,
                )
            else:
                record = start(root, args.unit)
        elif args.command == "admit":
            record = admit_work(
                root,
                args.work,
                running=args.running,
                selected=args.unit or None,
                finished=args.finished or None,
            )
        elif args.command == "prepare":
            record = prepare_unit(root, args.work, args.session)
        elif args.command == "brief":
            text = worker_brief(root, args.work)
            sys.stdout.write(text if text.endswith("\n") else text + "\n")
            return 0
        elif args.command == "probe-steps":
            path = Path(__file__).resolve().parents[1] / "docs" / "milestones" / "m5b-hr-p-check.md"
            sys.stdout.write(path.read_text(encoding="utf-8"))
            sys.stdout.write("이 명령은 도구를 실행하지 않는다.\n")
            return 0
        elif args.command == "parallel":
            record = record_parallel(root, args.work)
        elif args.command == "resume-parallel":
            sys.stdout.write(resume_parallel(root))
            return 0
        elif args.command == "judge":
            kind = judge(args.exit, args.line, args.next_updated, args.turn_failed)
            record = blank(ok="예", state=kind, line=redact_secret(args.line))
        elif args.command == "stall":
            last = datetime.fromisoformat(args.last.replace("Z", "+00:00"))
            now = datetime.fromisoformat(args.now.replace("Z", "+00:00"))
            notice = stall_notice(args.alive, last, now)
            record = blank(ok="예", state=notice or "괜찮음", line=notice)
        elif args.command == "collect-work" or (args.command == "collect" and args.work):
            record = collect_work(root, args.work)
        elif args.command == "poll":
            record = poll(root, args.handle)
        else:
            record = collect(root, args.handle)
    except OrchestratorError as exc:
        record = blank(ok="아니오", state="거부", reason=str(exc))
    sys.stdout.write(render(record))
    return 0 if record["ok"] == "예" else 1


if __name__ == "__main__":
    sys.exit(main())
