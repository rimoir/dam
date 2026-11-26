#!/usr/bin/env python3
"""세션 시작 출력. 현황판의 열린 줄과 작업 하나의 state.md만 낸다."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

INJECT_LIMIT = 4000
STATE_LIMIT = 2000
SHORTEN_LINE = "상한을 넘었다. 상태 파일 또는 시작 주입을 줄여라.\n"
CLOSED = frozenset({"완료", "닫힘"})
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


def render_start_context(root: Path, branch: str, switch: bool = False) -> str:
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
    if state_text:
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
    body = "".join(chunks)
    if len(state_text) > STATE_LIMIT or len(body) > INJECT_LIMIT:
        return SHORTEN_LINE
    return body
