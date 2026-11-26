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

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from issue_tracker import (  # noqa: E402
    IssueRecord,
    IssueTrackerError,
    load_tracker,
    redact,
)

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


def render_task(work_id: str, issue: IssueRecord | None) -> str:
    if issue is None:
        goal = "(한 줄)"
        criteria = "- (관찰 가능한 조건)\n"
    else:
        goal = f"{issue.title}\n\n{issue.url}"
        if issue.acceptance:
            criteria = "".join(f"- {item}\n" for item in issue.acceptance)
        else:
            criteria = "- (없음)\n"
    return (
        f"# 작업 {work_id}\n\n"
        "## 목표\n\n"
        f"{goal}\n\n"
        "## 완료 기준\n\n"
        f"{criteria}\n"
        "## 계획\n\n"
        "- (단계)\n"
    )


def templates(work_id: str) -> dict[str, str]:
    return {
        "task.md": render_task(work_id, None),
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
            "한 줄 형식: `YYYY-MM-DDTHH:MM:SSZ 도구 종류 내용`\n\n"
            "도구는 `Claude Code` 또는 `Codex`다.\n"
            "종류는 시작, go, 종료, push, 재개 중 하나다.\n\n"
            "예: `2026-11-26T00:00:00Z Codex go 계획 승인`\n"
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


def _drop_created(folder: Path, created_folder: bool, created_files: list[Path]) -> None:
    for path in created_files:
        path.unlink(missing_ok=True)
    if created_folder:
        try:
            folder.rmdir()
        except OSError:
            return


def create_session(root: Path, work_id: str, session: str, tracker=None) -> None:
    if not valid_work_id(work_id):
        raise SystemExit(f"작업ID 형식이 아니다: {work_id}")
    if not SESSION_NAME.fullmatch(session):
        raise SystemExit(f"담당 세션 형식이 아니다: {session}")
    folder = root / ".team" / "sessions" / work_id
    task_path = folder / "task.md"
    bodies = templates(work_id)
    if ISSUE_ID.fullmatch(work_id) and not task_path.exists():
        active = tracker if tracker is not None else load_tracker(root)
        issue = active.read_issue(int(work_id))
        bodies["task.md"] = render_task(work_id, issue)
    created_folder = False
    created_files: list[Path] = []
    try:
        if not folder.exists():
            folder.mkdir(parents=True)
            created_folder = True
        for name, body in bodies.items():
            path = folder / name
            if path.exists():
                continue
            path.write_text(body, encoding="utf-8")
            created_files.append(path)
        ensure_board(root, work_id, session)
    except Exception:
        _drop_created(folder, created_folder, created_files)
        raise


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
    try:
        if args.command == "new":
            create_session(root, args.work_id, args.session)
        elif args.command == "summary":
            sys.stdout.write(summary_text(root, args.work_id))
    except IssueTrackerError as exc:
        print(redact(str(exc)), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
