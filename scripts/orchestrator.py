#!/usr/bin/env python3
"""워커 시작, 지켜보기, 수거. 이 파일만 orchestrator 키를 읽는다.

native는 PATH의 claude만 띄운다. fake는 띄우지 않는다.
Codex는 미검증이라 띄우지 않는다. 다섯 칸은 그대로다.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import select
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from issue_tracker import redact  # noqa: E402
from session_context import (  # noqa: E402
    _log_kind,
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
# Bash는 주지 않는다. 읽기와 쓰기는 Read, Edit, Write. ADR 0009.
_WORKER_TOOLS = "Read,Edit,Write"
_NOTE_SUFFIXES = {".md", ".txt", ".json"}
_NOTE_NAMES = ("state.md", "log.md")
_REASON_LINE_LIMIT = 200
_REASON_LINE_COUNT = 8


class OrchestratorError(Exception):
    pass


class Admission(dict[str, str]):
    """허용된 단위 이름 목록. 사람이 읽는 line을 다시 쪼개지 않는다."""

    units: tuple[str, ...]

    def __init__(
        self,
        ok: str,
        state: str,
        reason: str = "",
        units: tuple[str, ...] = (),
    ) -> None:
        super().__init__(
            blank(ok=ok, state=state, reason=reason, line=" ".join(units))
        )
        self.units = units


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


def _binary_problem(path: Path) -> str:
    if not path.is_file():
        return "실행 파일이 없다"
    if not os.access(path, os.X_OK):
        return "실행할 수 없다"
    return ""


def claude_problem() -> str:
    explicit = os.environ.get("ORCH_CLAUDE", "").strip()
    if explicit == "-":
        return ""
    if explicit:
        return _binary_problem(Path(explicit))
    found = shutil.which("claude")
    if not found:
        return "실행 파일이 없다"
    return _binary_problem(Path(found))


def resolve_claude() -> str | None:
    explicit = os.environ.get("ORCH_CLAUDE", "").strip()
    if explicit == "-":
        return None
    if explicit:
        path = Path(explicit)
        return str(path) if not _binary_problem(path) else None
    found = shutil.which("claude")
    if found and not _binary_problem(Path(found)):
        return found
    return None


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
    name, dep, files, _check = unit, "없음", "", ""
    work = ""
    if owner and owner != "*":
        work = owner
        task = root / ".team" / "sessions" / owner / "task.md"
        if task.is_file():
            try:
                units = read_plan_units(task.read_text(encoding="utf-8"))
            except (OSError, UnicodeError):
                units = ()
            for item in units:
                if item[0] == unit:
                    name, dep, files, _check = item
                    break
    where = f".team/sessions/{work}/result.md" if work else "result.md"
    return (
        f"단위: {name}\n"
        f"의존: {dep}\n"
        f"파일: {files}\n"
        f"결과 칸은 {where}의 ## 결과 절에만 쓴다. "
        "수정한 내용만 그 절에 적는다. "
        "그 절의 첫 줄은 PASS, ISSUES, BLOCKED 중 하나로 시작한다. "
        "결정 줄과 승인 줄은 바꾸지 않는다.\n"
    )


def trusted_check(root: Path, unit: str) -> str:
    owner = work_owning_unit(root, unit)
    if not owner or owner == "*":
        return ""
    text = _read_regular(root / ".team" / "sessions" / owner / "task.md") or ""
    try:
        units = read_plan_units(text)
    except (OSError, UnicodeError):
        return ""
    for name, _dep, _files, check in units:
        if name == unit:
            return check
    return ""


def _text(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def decision_body(text: str) -> str:
    return _named_section(text, "## 결정")


def approval_lines(text: str) -> tuple[str, ...]:
    found: list[str] = []
    for raw in text.splitlines():
        if _log_kind(raw.split()) == "go":
            found.append(raw.strip())
    return tuple(found)


def changed_note_lines(
    before_decisions: str,
    after_decisions: str,
    before_approvals: tuple[str, ...],
    after_approvals: tuple[str, ...],
) -> tuple[str, ...]:
    before_d = [line.strip() for line in before_decisions.splitlines() if line.strip()]
    after_d = [line.strip() for line in after_decisions.splitlines() if line.strip()]
    changed: list[str] = []
    for line in after_d:
        if line not in before_d:
            changed.append(line)
    for line in before_d:
        if line not in after_d:
            changed.append(line)
    for line in after_approvals:
        if line not in before_approvals:
            changed.append(line)
    for line in before_approvals:
        if line not in after_approvals:
            changed.append(line)
    return tuple(changed)


def replace_section(text: str, heading: str, body: str) -> str:
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip() == heading:
            start = index + 1
            break
    body_lines = body.splitlines()
    if start is None:
        extra = [heading, *body_lines]
        if lines and lines[-1] != "":
            lines.append("")
        lines.extend(extra)
    else:
        end = len(lines)
        for index in range(start, len(lines)):
            if lines[index].startswith("## "):
                end = index
                break
        lines = lines[:start] + body_lines + lines[end:]
    rendered = "\n".join(lines)
    if text.endswith("\n") or rendered:
        rendered += "\n"
    return rendered


def restore_approvals(text: str, approvals: tuple[str, ...]) -> str:
    kept = [raw for raw in text.splitlines() if _log_kind(raw.split()) != "go"]
    kept.extend(approvals)
    rendered = "\n".join(kept)
    if rendered:
        rendered += "\n"
    return rendered


def _capture_guard(root: Path, cwd: Path, work_id: str) -> dict[str, list[dict[str, object]]]:
    folders: list[Path] = []
    seen: set[str] = set()
    for folder in (
        root / ".team" / "sessions" / work_id,
        cwd / ".team" / "sessions" / work_id,
    ):
        key = str(folder)
        if key in seen:
            continue
        seen.add(key)
        folders.append(folder)
    files: list[dict[str, object]] = []
    for folder in folders:
        log = _text(folder / "log.md")
        files.append(
            {
                "dir": str(folder),
                "decisions": decision_body(_text(folder / "state.md")),
                "approvals": list(approval_lines(log)),
            }
        )
    return {"files": files}


def _group_alive(pid: str) -> bool:
    text = pid.strip()
    try:
        number = int(text)
    except ValueError:
        return False
    if number <= 0:
        return False
    proc = Path("/proc")
    if not proc.is_dir():
        try:
            os.kill(-number, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
        return True
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            raw = (entry / "stat").read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        end = raw.rfind(")")
        if end == -1:
            continue
        fields = raw[end + 2 :].split()
        if len(fields) < 3 or fields[0] == "Z":
            continue
        if fields[2] == str(number):
            return True
    return False


def _read_regular(path: Path) -> str | None:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks).decode("utf-8")
    except (OSError, UnicodeError):
        return None
    finally:
        os.close(fd)


def _write_regular(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if path.is_symlink():
            path.unlink()
    except OSError:
        return
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o644)
    except OSError:
        return
    try:
        os.write(fd, text.encode("utf-8"))
    finally:
        os.close(fd)


def _restore_guard(loaded: dict[str, str], root: Path) -> tuple[str, ...]:
    raw = loaded.get("guard", "")
    if not raw:
        return ()
    try:
        guard = json.loads(raw)
    except json.JSONDecodeError:
        return ()
    cwd = Path(loaded.get("cwd") or "")
    changed: list[str] = []
    for item in guard.get("files", []):
        folder = Path(str(item.get("dir", "")))
        if not str(folder):
            continue
        before_d = str(item.get("decisions", ""))
        before_a = tuple(str(line) for line in item.get("approvals", []))
        state_path = folder / "state.md"
        log_path = folder / "log.md"
        state = _read_regular(state_path) or ""
        log = _read_regular(log_path) or ""
        after_d = decision_body(state)
        after_a = approval_lines(log)
        changed.extend(changed_note_lines(before_d, after_d, before_a, after_a))
        if cwd and folder != root and _inside(folder, cwd):
            continue
        if not _inside(folder, root):
            continue
        if after_d != before_d:
            base = state if state else "# 상태\n\n## 결정\n"
            _write_regular(state_path, replace_section(base, "## 결정", before_d))
        if after_a != before_a:
            _write_regular(log_path, restore_approvals(log, before_a))
    return tuple(dict.fromkeys(changed))


def _fingerprint(path: Path) -> str:
    try:
        info = path.lstat()
    except OSError:
        return ""
    if stat.S_ISLNK(info.st_mode):
        try:
            return "link:" + os.readlink(path)
        except OSError:
            return ""
    if not stat.S_ISREG(info.st_mode):
        return ""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError:
        return ""
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return ""
        digest = hashlib.sha256()
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return ""
    finally:
        os.close(fd)


def _gitdir(cwd: Path) -> Path | None:
    pointer = cwd / ".git"
    try:
        info = pointer.lstat()
    except OSError:
        return None
    if stat.S_ISDIR(info.st_mode):
        return pointer
    if not stat.S_ISREG(info.st_mode):
        return None
    text = _read_regular(pointer)
    if not text:
        return None
    for raw in text.splitlines():
        if raw.startswith("gitdir:"):
            target = Path(raw.split(":", 1)[1].strip())
            if not target.is_absolute():
                target = (cwd / target).resolve()
            return target
    return None


def _commondir(gitdir: Path) -> Path | None:
    text = _read_regular(gitdir / "commondir")
    if text is None:
        return None
    raw = text.strip()
    if not raw or "\n" in raw or "\x00" in raw:
        return None
    target = Path(raw)
    target = target.resolve() if target.is_absolute() else (gitdir / target).resolve()
    try:
        info = target.lstat()
    except OSError:
        return None
    if not stat.S_ISDIR(info.st_mode):
        return None
    return target


def _hash_git_meta(files: dict[str, str], prefix: str, folder: Path) -> None:
    for rel in ("config", "config.worktree", "info/attributes"):
        files[f"{prefix}/{rel}"] = _fingerprint(folder / rel)
    hooks = folder / "hooks"
    try:
        info = hooks.lstat()
    except OSError:
        return
    if not stat.S_ISDIR(info.st_mode):
        return
    for dirpath, dirnames, filenames in os.walk(hooks, followlinks=False):
        dirnames[:] = [
            name for name in dirnames if not (Path(dirpath) / name).is_symlink()
        ]
        for name in filenames:
            path = Path(dirpath) / name
            rel = f"{prefix}/hooks/" + path.relative_to(hooks).as_posix()
            files[rel] = _fingerprint(path)


def snapshot_tree(cwd: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    if cwd.is_dir():
        for dirpath, dirnames, filenames in os.walk(cwd, followlinks=False):
            kept: list[str] = []
            for name in sorted(dirnames):
                path = Path(dirpath) / name
                if path.is_symlink():
                    files[path.relative_to(cwd).as_posix()] = _fingerprint(path)
                else:
                    kept.append(name)
            dirnames[:] = kept
            for name in sorted(filenames):
                path = Path(dirpath) / name
                files[path.relative_to(cwd).as_posix()] = _fingerprint(path)
    gitdir = _gitdir(cwd)
    if gitdir is not None:
        _hash_git_meta(files, "gitdir", gitdir)
        common = _commondir(gitdir)
        if common is not None and common != gitdir:
            _hash_git_meta(files, "common", common)
    return files


def tree_changes(before: dict[str, str], after: dict[str, str], allowed: str) -> tuple[str, ...]:
    changed: list[str] = []
    for path in sorted(set(before) | set(after)):
        if allowed and path == allowed:
            continue
        if before.get(path) != after.get(path):
            changed.append(path)
    return tuple(changed)


def _launch_claude(
    root: Path, handle: str, unit: str, cwd: Path
) -> tuple[int, str] | str | None:
    binary = resolve_claude()
    if binary is None:
        return None
    exit_path = _store(root) / f"{handle}.exit"
    out_path = _store(root) / f"{handle}.out"
    first_path = _store(root) / f"{handle}.first"
    wrapper = (
        'trap \'trap - TERM INT; kill -TERM -$$ 2>/dev/null\' TERM INT; '
        'start=$(date +%s.%N); '
        '"$ORCH_CLAUDE_BIN" "$@" > "$ORCH_OUT" 2>&1 & child=$!; '
        'while kill -0 "$child" 2>/dev/null; do '
        'if [ -s "$ORCH_OUT" ] && [ ! -f "$ORCH_FIRST" ]; then '
        'end=$(date +%s.%N); '
        'awk -v s="$start" -v e="$end" \'BEGIN{printf "%.3f\\n", e-s}\' > "$ORCH_FIRST"; '
        'fi; sleep 0.02; done; '
        'wait "$child"; echo $? > "$ORCH_EXIT"; '
        'if [ -s "$ORCH_OUT" ] && [ ! -f "$ORCH_FIRST" ]; then '
        'end=$(date +%s.%N); '
        'awk -v s="$start" -v e="$end" \'BEGIN{printf "%.3f\\n", e-s}\' > "$ORCH_FIRST"; '
        'fi'
    )
    env = os.environ.copy()
    env["ORCH_EXIT"] = str(exit_path)
    env["ORCH_OUT"] = str(out_path)
    env["ORCH_FIRST"] = str(first_path)
    env["ORCH_CLAUDE_BIN"] = binary
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
                "stream-json",
                "--verbose",
                "--permission-mode",
                "acceptEdits",
                "--permission-prompts",
                "none",
                "--max-turns",
                str(MAX_TURNS),
                "--tools",
                _WORKER_TOOLS,
                "--disallowedTools",
                "Bash",
                "--restricted",
                "--strict-mcp-config",
            ],
            cwd=cwd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return "claude를 띄우지 못했다"
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
) -> Admission:
    folder = root / ".team" / "sessions" / work_id
    task_path = folder / "task.md"
    if not task_path.is_file():
        return Admission("아니오", "거부", f"task.md가 없다: {work_id}")
    log_path = folder / "log.md"
    log_text = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
    if not log_has_go(log_text):
        return Admission("아니오", "거부", "go 없는 작업이다")
    units = read_plan_units(task_path.read_text(encoding="utf-8"))
    if not units:
        return Admission("아니오", "거부", "계획 단위가 없다")
    by_name = {item[0]: item for item in units}
    names = tuple(selected) if selected else tuple(item[0] for item in units)
    for name in names:
        if name not in by_name:
            return Admission("아니오", "거부", f"계획에 없는 단위다: {name}")
    file_sets = {name: _unit_files(by_name[name][2]) for name in names}
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            for left_file in file_sets[left]:
                for right_file in file_sets[right]:
                    if paths_overlap(left_file, right_file):
                        shown = _plan_path(left_file)
                        return Admission("아니오", "거부", f"건드릴 파일이 겹친다: {shown}")
    done = set(finished or [])
    for name in names:
        dep = by_name[name][1].strip()
        if not dep or dep == "없음" or dep in done:
            continue
        return Admission("아니오", "거부", f"앞 단위 결과가 입력이다: {dep}")
    if running + len(names) > WORKER_LIMIT:
        return Admission("아니오", "거부", f"동시 워커 상한 {WORKER_LIMIT}을 넘는다")
    return Admission("예", "허용", units=names)


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
    for name in decision.units:
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
    if name == "native":
        problem = claude_problem()
        if problem:
            return blank(ok="아니오", state="거부", reason=problem)
    folder = _store(root)
    number = 1 + sum(1 for _found in folder.glob(f"{name}-*.json"))
    record = blank(ok="예", handle=f"{name}-{number}", state="대기")
    extra: dict[str, str] = {"cwd": str(cwd)}
    owner = work_owning_unit(root, unit)
    if owner and owner != "*":
        extra["work"] = owner
        extra["guard"] = json.dumps(
            _capture_guard(root, cwd, owner),
            ensure_ascii=False,
        )
    if name == "native":
        extra["tree"] = json.dumps(snapshot_tree(cwd), ensure_ascii=False)
        extra["check"] = trusted_check(root, unit)
        if owner and owner != "*":
            _save_note_originals(root, record["handle"], cwd, owner)
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


def worker_phase(root: Path, loaded: dict[str, str]) -> str:
    """종료 파일과 세션 그룹으로 진행, 대기, 끝 중 하나만 낸다."""
    if loaded.get("tool") != "claude":
        return loaded.get("state", "")
    handle = loaded.get("handle", "")
    exit_path = _store(root) / f"{handle}.exit"
    ended = exit_path.is_file()
    if _group_alive(loaded.get("pid", "")):
        return "대기" if ended else "진행"
    if ended:
        return "끝"
    return "진행"


def poll(root: Path, handle: str) -> dict[str, str]:
    try:
        loaded = _load(root, handle)
    except OrchestratorError as exc:
        return blank(ok="아니오", state="거부", reason=str(exc))
    if loaded.get("tool") == "claude":
        phase = worker_phase(root, loaded)
        loaded["state"] = phase
        if phase == "끝":
            exit_path = _store(root) / f"{handle}.exit"
            loaded["exit"] = exit_path.read_text(encoding="utf-8").strip()
        _write(root, loaded)
    return blank(**{key: loaded.get(key, "") for key in FIELDS})


def _result_reason(cwd: Path, path: Path) -> str:
    try:
        return path.relative_to(cwd).as_posix()
    except ValueError:
        return "result.md"


def _state_text(root: Path, cwd: Path, owner: str) -> str:
    if not owner:
        return ""
    for folder in (
        cwd / ".team" / "sessions" / owner,
        root / ".team" / "sessions" / owner,
    ):
        text = _read_regular(folder / "state.md")
        if text is not None:
            return text
    return ""


def _note_dir(root: Path, handle: str) -> Path:
    return _store(root) / f"{handle}.notes"


def _save_note_originals(root: Path, handle: str, cwd: Path, owner: str) -> None:
    if not owner or owner == "*":
        return
    for name in _NOTE_NAMES:
        src = cwd / ".team" / "sessions" / owner / name
        text = ""
        try:
            info = src.lstat()
        except OSError:
            info = None
        if info is not None and stat.S_ISREG(info.st_mode):
            text = _read_regular(src) or ""
        _write_regular(_note_dir(root, handle) / name, text)


def _escape_reason_line(text: str) -> str:
    out: list[str] = []
    for ch in text:
        code = ord(ch)
        if ch == "\\":
            out.append("\\\\")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif code < 32 or code == 127:
            out.append(f"\\x{code:02x}")
        else:
            out.append(ch)
    rendered = "".join(out)
    if len(rendered) > _REASON_LINE_LIMIT:
        return rendered[:_REASON_LINE_LIMIT]
    return rendered


def _changed_lines(before: str, after: str) -> list[str]:
    found: list[str] = []
    for raw in difflib.ndiff(before.splitlines(), after.splitlines()):
        if not raw.startswith(("+ ", "- ")):
            continue
        line = raw[2:]
        if not line.strip():
            continue
        found.append(line)
    return found


def _read_worker_note(path: Path) -> str | None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return ""
    except OSError:
        return None
    if not stat.S_ISREG(info.st_mode):
        return None
    return _read_regular(path)


def _change_reason(
    root: Path, handle: str, cwd: Path, owner: str, moved: tuple[str, ...]
) -> str:
    notes = {}
    if owner and owner != "*":
        notes = {
            f".team/sessions/{owner}/{name}": name for name in _NOTE_NAMES
        }
    pieces = list(moved)
    budget = _REASON_LINE_COUNT
    saved = _note_dir(root, handle)
    for rel, name in notes.items():
        if rel not in moved or budget <= 0:
            continue
        before = _read_regular(saved / name) or ""
        after = _read_worker_note(cwd / rel)
        if after is None:
            continue
        for line in _changed_lines(before, after):
            if budget <= 0:
                break
            pieces.append(_escape_reason_line(line))
            budget -= 1
    return " ".join(pieces)


def _problem(root: Path, loaded: dict[str, str], handle: str, reason: str) -> dict[str, str]:
    record = blank(ok="예", handle=handle, state="문제", line="", reason=reason)
    loaded.update(record)
    _write(root, loaded)
    return record


def _read_bytes(path: Path) -> bytes | None:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    except OSError:
        return None
    finally:
        os.close(fd)


def _write_bytes(path: Path, data: bytes) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o644)
    except OSError:
        return False
    try:
        os.write(fd, data)
        return True
    except OSError:
        return False
    finally:
        os.close(fd)


def _copyable(rel: str) -> bool:
    if not rel or rel.startswith("/") or rel.startswith("gitdir/") or rel.startswith("common/"):
        return False
    parts = PurePosixPath(rel).parts
    if ".." in parts or rel == ".git" or rel.startswith(".git/"):
        return False
    return True


def materialize_snapshot(cwd: Path, snapshot: dict[str, str], dest: Path) -> str | None:
    """검사한 작업 폴더만 복사한다. 해시가 달라지면 이유를 돌려준다."""
    for rel, digest in snapshot.items():
        if not _copyable(rel):
            continue
        src = cwd / rel
        if _fingerprint(src) != digest:
            return "검사한 내용이 바뀌었다"
        target = dest / rel
        if digest.startswith("link:"):
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.symlink(digest[len("link:") :], target)
            except OSError:
                return "검사한 내용이 바뀌었다"
            continue
        if not digest:
            continue
        data = _read_bytes(src)
        if data is None or hashlib.sha256(data).hexdigest() != digest:
            return "검사한 내용이 바뀌었다"
        if not _write_bytes(target, data):
            return "검사한 내용이 바뀌었다"
    if snapshot_tree(cwd) != snapshot:
        return "검사한 내용이 바뀌었다"
    return None


def _isolate_script(ready_fd: int) -> str:
    return (
        "#!/bin/sh\n"
        "set -e\n"
        "copy=$1\n"
        "shift\n"
        "mount --make-rprivate / || exit 77\n"
        "root=$(mktemp -d)\n"
        "mount -t tmpfs -o mode=755 tmpfs \"$root\" || exit 79\n"
        "mkdir -p \"$root/usr\" \"$root/proc\" \"$root/tmp\" \"$root/dev\" \"$root/mnt/copy\"\n"
        "mount --bind /usr \"$root/usr\" || exit 79\n"
        "mount -o remount,bind,ro \"$root/usr\" || exit 79\n"
        "for name in bin lib lib64 sbin; do\n"
        "  if [ -L \"/$name\" ]; then\n"
        "    ln -s \"$(readlink \"/$name\")\" \"$root/$name\"\n"
        "  elif [ -d \"/$name\" ]; then\n"
        "    mkdir -p \"$root/$name\"\n"
        "    mount --bind \"/$name\" \"$root/$name\" || exit 79\n"
        "    mount -o remount,bind,ro \"$root/$name\" || exit 79\n"
        "  fi\n"
        "done\n"
        "for node in null zero urandom; do\n"
        "  touch \"$root/dev/$node\"\n"
        "  mount --bind \"/dev/$node\" \"$root/dev/$node\" || exit 79\n"
        "done\n"
        "mount -t tmpfs -o mode=1777 tmpfs \"$root/tmp\" || exit 79\n"
        "mount --bind \"$copy\" \"$root/mnt/copy\" || exit 79\n"
        f"printf r >&{ready_fd} || exit 81\n"
        f"exec {ready_fd}>&-\n"
        "exec unshare -fp --mount-proc -R \"$root\" -w /mnt/copy -U --map-root-user "
        "setpriv --no-new-privs --inh-caps=-all --bounding-set=-all -- "
        "env -i PATH=/usr/bin:/bin HOME=/mnt/copy/empty-home TMPDIR=/tmp \"$@\"\n"
    )


def _locked_command(copy: Path, command: str) -> tuple[int, str, str]:
    """마운트를 잠근 뒤에만 명령을 돌린다. 준비에 실패하면 음수 코드."""
    read_fd, write_fd = os.pipe()
    os.set_inheritable(write_fd, True)
    wrapper = copy / "isolate"
    wrapper.write_text(_isolate_script(write_fd), encoding="utf-8")
    wrapper.chmod(0o755)
    proc = subprocess.Popen(
        [
            "timeout",
            "-k",
            "2",
            "30",
            "unshare",
            "-rmn",
            str(wrapper),
            str(copy),
            "sh",
            "-c",
            command,
        ],
        cwd=copy,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        pass_fds=(write_fd,),
    )
    os.close(write_fd)
    try:
        ready, _, _ = select.select([read_fd], [], [], 10)
        got = os.read(read_fd, 1) if ready else b""
        if got != b"r":
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                pass
            proc.communicate(timeout=5)
            return -1, "", ""
        try:
            out, err = proc.communicate(timeout=40)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.communicate()
            return 124, "", ""
        return proc.returncode or 0, out or "", err or ""
    finally:
        os.close(read_fd)


def run_disposable_check(
    cwd: Path,
    command: str,
    owner: str = "",
    snapshot: dict[str, str] | None = None,
) -> tuple[str, str]:
    del owner
    text = command.strip()
    if not text or "\x00" in text:
        return "검증 실패", "검증 명령이 없다"
    if snapshot is None:
        snapshot = snapshot_tree(cwd)
    copy = Path(tempfile.mkdtemp(prefix="orch-verify-"))
    try:
        problem = materialize_snapshot(cwd, snapshot, copy)
        if problem:
            return "검증 실패", problem
        if shutil.which("unshare") is None or shutil.which("timeout") is None:
            return "검증 실패", "네트워크를 막을 수 없다"
        probe = subprocess.run(
            ["unshare", "-rmn", "true"],
            text=True,
            capture_output=True,
            check=False,
        )
        if probe.returncode != 0 or shutil.which("setpriv") is None:
            return "검증 실패", "네트워크를 막을 수 없다" if probe.returncode != 0 else "잠그지 못했다"
        empty_home = copy / "empty-home"
        if empty_home.exists() and not empty_home.is_dir():
            return "검증 실패", "잠그지 못했다"
        empty_home.mkdir(exist_ok=True)
        code, out, err = _locked_command(copy, text)
        if code < 0:
            return "검증 실패", "잠그지 못했다"
        if code == 124:
            return "검증 실패", "시간이 다 됐다"
        if code == 0:
            return "검증 통과", ""
        tail = _escape_reason_line(out + err)
        return "검증 실패", tail or "검증이 실패했다"
    finally:
        shutil.rmtree(copy, ignore_errors=True)


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
    allowed = f".team/sessions/{owner}/result.md" if owner else ""
    before: dict[str, str] | None
    if "tree" not in loaded:
        before = None
    else:
        try:
            parsed = json.loads(loaded.get("tree") or "{}")
        except json.JSONDecodeError:
            parsed = {}
        before = parsed if isinstance(parsed, dict) else {}
    if before is not None:
        after = snapshot_tree(cwd)
        moved = tree_changes(
            {str(key): str(value) for key, value in before.items()},
            after,
            allowed,
        )
        if moved:
            _restore_guard(loaded, root)
            return _problem(
                root,
                loaded,
                handle,
                _change_reason(root, handle, cwd, owner, moved),
            )
    result_path = (
        cwd / ".team" / "sessions" / owner / "result.md" if owner else cwd / "result.md"
    )
    try:
        result_info = result_path.lstat()
    except FileNotFoundError:
        result_info = None
    except OSError:
        return _problem(root, loaded, handle, _result_reason(cwd, result_path))
    if result_info is not None and not stat.S_ISREG(result_info.st_mode):
        return _problem(root, loaded, handle, _result_reason(cwd, result_path))
    raw = _read_regular(result_path) if result_info is not None else ""
    if result_info is not None and raw is None:
        return _problem(root, loaded, handle, _result_reason(cwd, result_path))
    line = result_section_line(redact_secret(raw or ""))
    try:
        code = int(loaded.get("exit", "0") or "0")
    except ValueError:
        code = 1
    kind = judge(code, line, next_action_updated(_state_text(root, cwd, owner)))
    reason = ""
    if kind == "성공":
        inspected = after if before is not None else snapshot_tree(cwd)
        kind, reason = run_disposable_check(
            cwd, loaded.get("check", ""), owner, inspected
        )
    stamp = _read_regular(_store(root) / f"{handle}.first")
    if stamp and stamp.strip():
        loaded["first_event"] = stamp.strip()
    record = blank(ok="예", handle=handle, state=kind, line=line, reason=reason)
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
    try:
        info = folder.lstat()
    except OSError:
        return
    if not stat.S_ISDIR(info.st_mode):
        return
    for path in folder.iterdir():
        if path.suffix not in _NOTE_SUFFIXES:
            continue
        raw = _read_regular(path)
        if raw is None:
            continue
        cleaned = redact(raw)
        if cleaned != raw:
            _write_regular(path, cleaned)


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
    raw = _read_regular(result_path) or ""
    cleaned = redact_secret(raw)
    if raw and cleaned != raw:
        _write_regular(result_path, cleaned)
    line = result_section_line(cleaned)
    try:
        folder_info = folder.lstat()
    except OSError:
        folder_info = None
    if folder_info is not None and stat.S_ISDIR(folder_info.st_mode):
        _write_regular(folder / "worker-out.txt", line + "\n")
    state = _read_regular(state_path) or ""
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
