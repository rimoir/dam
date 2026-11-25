#!/usr/bin/env python3
"""작업 노트 네 파일과 board.md 한 줄을 만든다.

도구 전용 형식을 쓰지 않는다. 같은 작업ID로 다시 실행해도 노트를 덮어쓰지 않는다.
"""

from __future__ import annotations

import argparse
import fcntl
import re
import sys
from pathlib import Path

ISSUE_ID = re.compile(r"^[0-9]+$")
DATE_ID = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")
SESSION_NAME = re.compile(r"^[A-Za-z0-9._\-\uac00-\ud7a3]{1,40}$")


def repo_root() -> Path:
    import os

    override = os.environ.get("TEAM_ROOT")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[1]


def valid_work_id(work_id: str) -> bool:
    return bool(ISSUE_ID.fullmatch(work_id) or DATE_ID.fullmatch(work_id))


def templates(work_id: str) -> dict[str, str]:
    return {
        "task.md": (
            f"# 작업 {work_id}\n\n"
            "## 목표\n\n"
            "(한 줄)\n\n"
            "## 완료 기준\n\n"
            "- (관찰 가능한 조건)\n\n"
            "## 계획\n\n"
            "- (단계)\n"
        ),
        "state.md": (
            f"# 상태 {work_id}\n\n"
            "## 지금 상태\n\n"
            "시작\n\n"
            "## 결정\n\n"
            "- (아직 없음)\n\n"
            "## 다음 할 일\n\n"
            "task.md의 계획을 채운 뒤 사람의 go를 기다린다.\n"
        ),
        "log.md": (
            f"# 로그 {work_id}\n\n"
            "한 줄 형식: `YYYY-MM-DDTHH:MM:SSZ 종류 내용`\n\n"
            "종류는 시작, go, 종료, push, 재개 중 하나다.\n"
        ),
        "result.md": (
            f"# 결과 {work_id}\n\n"
            "## 결과\n\n"
            "(아직 없음)\n\n"
            "## 교훈 후보\n\n"
            "- (아직 없음)\n"
        ),
    }


def board_line(work_id: str, session: str) -> str:
    return f"- {work_id}: 상태 시작, 담당 {session}, 막힘 없음\n"


def ensure_board(root: Path, work_id: str, session: str) -> None:
    path = root / ".team" / "board.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    line = board_line(work_id, session)
    header = (
        "# 작업 현황\n\n"
        "한 줄 형식: `- <작업ID>: 상태 <상태>, 담당 <세션>, 막힘 <이유>`\n\n"
    )
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0)
        text = handle.read()
        marker = f"\n- {work_id}:"
        if text.startswith(f"- {work_id}:") or marker in text:
            return
        if not text:
            handle.write(header)
        elif not text.endswith("\n"):
            handle.write("\n")
        handle.write(line)
        handle.flush()


def create_session(root: Path, work_id: str, session: str) -> None:
    if not valid_work_id(work_id):
        raise SystemExit(f"작업ID 형식이 아니다: {work_id}")
    if not SESSION_NAME.fullmatch(session):
        raise SystemExit(f"담당 세션 형식이 아니다: {session}")
    folder = root / ".team" / "sessions" / work_id
    folder.mkdir(parents=True, exist_ok=True)
    for name, body in templates(work_id).items():
        path = folder / name
        if path.exists():
            continue
        path.write_text(body, encoding="utf-8")
    ensure_board(root, work_id, session)


LIMIT = 10000


def summary_text(root: Path, work_id: str) -> str:
    if not valid_work_id(work_id):
        raise SystemExit(f"작업ID 형식이 아니다: {work_id}")
    path = root / ".team" / "sessions" / work_id / "state.md"
    if not path.is_file():
        raise SystemExit(f"state.md가 없다: {work_id}")
    text = path.read_text(encoding="utf-8")
    if len(text) > LIMIT:
        raise SystemExit(f"세션 시작 요약이 {LIMIT}자를 넘는다: {len(text)}")
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="작업 노트 폴더를 만든다.")
    sub = parser.add_subparsers(dest="command", required=True)
    new = sub.add_parser("new", help="네 노트와 board 한 줄을 만든다.")
    new.add_argument("work_id")
    new.add_argument("--session", default="미정")
    summary = sub.add_parser("summary", help="세션 시작 요약으로 state.md만 출력한다.")
    summary.add_argument("work_id")
    args = parser.parse_args(argv)
    root = repo_root()
    if args.command == "new":
        create_session(root, args.work_id, args.session)
    elif args.command == "summary":
        sys.stdout.write(summary_text(root, args.work_id))
    return 0


if __name__ == "__main__":
    sys.exit(main())
