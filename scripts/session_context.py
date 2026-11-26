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
    original = state.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    replacement = f"모드: {name}\n"
    if lines and lines[0].startswith("모드:"):
        lines[0] = replacement
    else:
        lines.insert(0, replacement)
    state.write_text("".join(lines), encoding="utf-8")
    return replacement


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
