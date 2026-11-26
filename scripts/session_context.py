#!/usr/bin/env python3
"""세션 시작 출력. 현황판의 열린 줄과 작업 하나의 state.md만 낸다."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

INJECT_LIMIT = 4000
STATE_LIMIT = 2000
LOG_LINE_LIMIT = 200
RULE_LINE_LIMIT = 50
COMMAND_LINE_LIMIT = 40
RULE_REL = Path(".rulesync/rules/dam.md")
COMMAND_RELS = (
    Path(".claude/commands/mode.md"),
    Path(".agents/skills/mode/SKILL.md"),
)
SHORTEN_LINE = "상한을 넘었다. 상태 파일 또는 시작 주입을 줄여라.\n"
WORK_ID = re.compile(
    r"^(?:[0-9]+|[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9]+(?:-[a-z0-9]+)*)$"
)
CLOSED = frozenset({"완료", "닫힘"})
MODES = ("조사", "작은 수정", "기능", "이어받기")
BOARD_LINE = re.compile(
    r"^- (?P<id>\S+): 상태 (?P<status>[^,]+), 담당 [^,]+, 막힘 .*$"
)
ISSUE_AT_END = re.compile(r"([0-9]+)$")


def issue_id_from_branch(branch: str) -> str | None:
    name = branch.strip().replace("\\", "/").split("/")[-1]
    found = ISSUE_AT_END.search(name)
    if found is None:
        return None
    return found.group(1)


def current_branch(root: Path) -> str:
    ref = os.environ.get("GITHUB_HEAD_REF", "").strip()
    if ref:
        return ref
    try:
        done = subprocess.run(
            ["git", "-C", str(root), "branch", "--show-current"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return ""
    if done.returncode != 0:
        return ""
    return done.stdout.strip()


def open_board_lines(root: Path) -> list[tuple[str, str]]:
    path = root / ".team" / "board.md"
    if not path.is_file():
        return []
    found: list[tuple[str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        match = BOARD_LINE.fullmatch(raw)
        if match is None:
            continue
        if match.group("status").strip() in CLOSED:
            continue
        if raw.endswith(", GitHub 닫힘") or raw.endswith(", GitHub 완료"):
            continue
        found.append((match.group("id"), raw))
    return found


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def assembled_start_context(root: Path, branch: str, switch: bool = False) -> tuple[str, int]:
    lines = open_board_lines(root)
    open_ids = {work_id for work_id, _line in lines}
    issue_id = issue_id_from_branch(branch)
    selected = issue_id if issue_id in open_ids else None
    state_text = ""
    if selected is not None:
        state_text = _read_text(root / ".team" / "sessions" / selected / "state.md")
    chunks: list[str] = []
    if lines:
        chunks.append("\n".join(line for _work_id, line in lines) + "\n")
    if selected is None:
        chunks.append(f"작업: 없음 (열린 줄 {len(lines)})\n")
    elif state_text:
        chunks.append(state_text)
        if not state_text.endswith("\n"):
            chunks.append("\n")
    if switch and selected is not None:
        log_text = _read_text(root / ".team" / "sessions" / selected / "log.md")
        tail_lines = log_text.splitlines(keepends=True)[-5:]
        tail = "".join(tail_lines)
        if tail:
            if chunks and not "".join(chunks).endswith("\n"):
                chunks.append("\n")
            chunks.append(tail if tail.endswith("\n") else tail + "\n")
    return "".join(chunks), len(state_text)


def render_start_context(root: Path, branch: str, switch: bool = False) -> str:
    body, state_len = assembled_start_context(root, branch, switch)
    if state_len > STATE_LIMIT or len(body) > INJECT_LIMIT:
        return SHORTEN_LINE
    return body


def rotate_log(root: Path, work_id: str) -> Path | None:
    if WORK_ID.fullmatch(work_id) is None:
        raise SystemExit(f"작업ID 형식이 아니다: {work_id}")
    path = root / ".team" / "sessions" / work_id / "log.md"
    if not path.is_file():
        raise SystemExit(f"log.md가 없다: {work_id}")
    original = path.read_bytes()
    lines = original.decode("utf-8").splitlines(keepends=True)
    if len(lines) <= LOG_LINE_LIMIT:
        return None
    keep = LOG_LINE_LIMIT - 1
    moved = "".join(lines[:-keep]).encode("utf-8")
    kept = "".join(lines[-keep:])
    if original != moved + kept.encode("utf-8"):
        raise SystemExit("로그 앞부분을 그대로 옮기지 못한다")
    archive_dir = path.parent / "log"
    archive_dir.mkdir(exist_ok=True)
    number = 1
    while (archive_dir / f"{number:03d}.md").exists():
        number += 1
    archive = archive_dir / f"{number:03d}.md"
    archive.write_bytes(moved)
    path.write_text(f"이전: log/{number:03d}.md\n{kept}", encoding="utf-8")
    return archive


def _split_first_line(raw: bytes) -> tuple[bytes, bytes, bytes]:
    crlf = raw.find(b"\r\n")
    lf = raw.find(b"\n")
    if crlf != -1 and (lf == -1 or crlf < lf):
        return raw[:crlf], b"\r\n", raw[crlf + 2 :]
    if lf != -1:
        return raw[:lf], b"\n", raw[lf + 1 :]
    return raw, b"\n", b""


def set_mode(root: Path, branch: str, name: str) -> str:
    if name not in MODES:
        raise SystemExit(f"모드 이름이 아니다: {name}")
    issue_id = issue_id_from_branch(branch)
    open_ids = {work_id for work_id, _line in open_board_lines(root)}
    if issue_id is None or issue_id not in open_ids:
        return "열린 작업이 없다\n"
    state = root / ".team" / "sessions" / issue_id / "state.md"
    if not state.is_file():
        return "상태 파일이 없다\n"
    _first, ending, rest = _split_first_line(state.read_bytes())
    state.write_bytes(f"모드: {name}".encode("utf-8") + ending + rest)
    return f"모드: {name}\n"


def _status_path(line: str) -> str:
    body = line[3:]
    if " -> " in body:
        body = body.split(" -> ", 1)[1]
    if len(body) >= 2 and body.startswith('"') and body.endswith('"'):
        body = body[1:-1]
    return body


def code_dirty_paths(root: Path) -> list[str]:
    try:
        done = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise SystemExit(f"git status가 실패했다: {exc}") from exc
    if done.returncode != 0:
        raise SystemExit("git status가 실패했다")
    found: list[str] = []
    for line in done.stdout.splitlines():
        if len(line) < 4:
            continue
        path = _status_path(line)
        if path == ".team" or path.startswith(".team/"):
            continue
        found.append(path)
    return found


def append_result(root: Path, branch: str, text: str) -> bool:
    issue_id = issue_id_from_branch(branch)
    open_ids = {work_id for work_id, _line in open_board_lines(root)}
    if issue_id is None or issue_id not in open_ids:
        return False
    path = root / ".team" / "sessions" / issue_id / "result.md"
    if not path.is_file():
        return False
    original = path.read_text(encoding="utf-8")
    if original and not original.endswith("\n"):
        original += "\n"
    path.write_text(original + text, encoding="utf-8")
    return True


PLAN_SCREEN = 40
_PLAN_ROW = re.compile(r"^-\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*$")


def _named_section(text: str, heading: str) -> str:
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip() == heading:
            start = index + 1
            break
    if start is None:
        return ""
    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break
    return "\n".join(lines[start:end])


def _plan_section(text: str) -> str:
    return _named_section(text, "## 계획")


def _has_go(log_text: str) -> bool:
    for line in log_text.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[2] == "go":
            return True
    return False


def plan_check(root: Path, work_id: str) -> tuple[list[str], str]:
    if re.fullmatch(r"[0-9]+", work_id) is None:
        return [f"작업ID가 이슈 번호가 아니다: {work_id}"], ""
    task = root / ".team" / "sessions" / work_id / "task.md"
    if not task.is_file():
        return [f"task.md가 없다: {work_id}"], ""
    body = task.read_text(encoding="utf-8")
    section = _plan_section(body)
    outside = _named_section(body, "## 계획 밖")
    errors: list[str] = []
    allowed: set[str] = set()
    found = 0
    for raw in section.splitlines():
        line = raw.strip()
        if "|" not in line or not line.startswith("-"):
            continue
        match = _PLAN_ROW.match(line)
        if match is None:
            errors.append(f"계획 줄 형식이 아니다: {line}")
            continue
        name, dep, files, check = (part.strip() for part in match.groups())
        found += 1
        label = name or "(이름 없음)"
        for field, value in (("단위", name), ("의존", dep), ("파일", files), ("검증", check)):
            if not value:
                errors.append(f"{label}의 {field}이 없다")
        for piece in files.replace(",", " ").split():
            if piece:
                allowed.add(piece)
    if found == 0:
        errors.append("계획 단위가 없다")
    for raw in outside.splitlines():
        line = raw.strip()
        match = _PLAN_ROW.match(line) if line.startswith("-") else None
        if match is None:
            continue
        name = match.group(1).strip() or "(이름 없음)"
        errors.append(f"계획 밖 단위다: {name}")
    notices: list[str] = []
    if len(section.splitlines()) > PLAN_SCREEN:
        notices.append("계획이 한 화면을 넘었다. 계획을 줄여라.")
    log_path = root / ".team" / "sessions" / work_id / "log.md"
    log_text = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
    if not _has_go(log_text):
        for path in code_dirty_paths(root):
            errors.append(f"go 전에 코드가 바뀌었다: {path}")
    elif allowed:
        for path in code_dirty_paths(root):
            if path not in allowed and not path.startswith(".team/"):
                notices.append(f"파일 목록 밖이다: {path}")
    notice = "".join(item + "\n" for item in notices)
    return errors, notice


def text_line_errors(root: Path) -> list[str]:
    errors: list[str] = []
    rule = root / RULE_REL
    if rule.is_file():
        count = len(rule.read_text(encoding="utf-8").splitlines())
        if count > RULE_LINE_LIMIT:
            errors.append(f"규칙 원본이 {RULE_LINE_LIMIT}줄을 넘는다: {count}")
    bodies: list[str] = []
    for rel in COMMAND_RELS:
        path = root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        bodies.append(text)
        count = len(text.splitlines())
        if count > COMMAND_LINE_LIMIT:
            errors.append(f"모드 명령 본문이 {COMMAND_LINE_LIMIT}줄을 넘는다: {rel.as_posix()} ({count})")
    if len(bodies) == 2 and bodies[0] != bodies[1]:
        errors.append("두 도구의 모드 명령 본문이 다르다")
    return errors


def limit_errors(root: Path, branch: str) -> list[str]:
    errors: list[str] = []
    sessions = root / ".team" / "sessions"
    if sessions.is_dir():
        for folder in sorted(path for path in sessions.iterdir() if path.is_dir()):
            state = folder / "state.md"
            if not state.is_file():
                continue
            text = state.read_text(encoding="utf-8")
            if len(text) > STATE_LIMIT:
                errors.append(
                    f"상태 파일이 {STATE_LIMIT}자를 넘는다: {folder.name} ({len(text)})"
                )
            log = folder / "log.md"
            if log.is_file():
                count = len(log.read_text(encoding="utf-8").splitlines())
                if count > LOG_LINE_LIMIT:
                    errors.append(
                        f"로그가 {LOG_LINE_LIMIT}줄을 넘는다: {folder.name} ({count})"
                    )
    body, _state_len = assembled_start_context(root, branch, False)
    if len(body) > INJECT_LIMIT:
        errors.append(f"시작 주입이 {INJECT_LIMIT}자를 넘는다: {len(body)}")
    return errors
