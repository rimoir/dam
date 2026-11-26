#!/usr/bin/env python3
"""작업 노트 네 파일과 board.md 한 줄을 만든다.

도구 전용 형식을 쓰지 않는다. 같은 작업ID로 다시 실행해도 노트를 덮어쓰지 않는다.
"""

from __future__ import annotations

import argparse
import fcntl
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from issue_tracker import (  # noqa: E402
    IssueRecord,
    IssueTrackerError,
    WorkView,
    load_tracker,
    redact,
)
from session_context import (  # noqa: E402
    current_branch,
    limit_errors,
    render_start_context,
    rotate_log,
    set_mode,
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
            "모드:\n\n"
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
    if not created_folder:
        return
    try:
        folder.rmdir()
    except OSError:
        return
    try:
        folder.parent.rmdir()
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
            created_files.append(path)
            path.write_text(body, encoding="utf-8")
        ensure_board(root, work_id, session)
    except Exception:
        _drop_created(folder, created_folder, created_files)
        raise


_BOARD_ISSUE = re.compile(r"^(- [0-9]+: 상태 [^,\n]+, 담당 [^,\n]+, 막힘 [^,\n]+)")


def github_clause(view: WorkView) -> str:
    if view.issue_closed:
        return "GitHub 닫힘"
    if view.pull_state == "open":
        word = {"pass": "통과", "fail": "실패", "pending": "아직 안 돎"}.get(
            view.checks, "아직 안 돎"
        )
        return f"GitHub 검토 중, 검사 {word}"
    if view.pull_state == "merged":
        return "GitHub 완료"
    return "GitHub 열림"


def _refresh_text(original: str, active) -> str:
    pieces: list[str] = []
    for line in original.splitlines(keepends=True):
        match = _BOARD_ISSUE.match(line.rstrip("\n"))
        if match is None:
            pieces.append(line)
            continue
        prefix = match.group(1)
        number = prefix.split(":", 1)[0][2:]
        view = active.read_status(int(number))
        ending = "\n" if line.endswith("\n") else ""
        pieces.append(f"{prefix}, {github_clause(view)}{ending}")
    return "".join(pieces)


def refresh_board(root: Path, tracker=None) -> None:
    path = root / ".team" / "board.md"
    if not path.is_file():
        raise SystemExit("board.md가 없다")
    active = tracker if tracker is not None else load_tracker(root)
    with path.open("r+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        original = handle.read()
        updated = _refresh_text(original, active)
        if updated == original:
            return
        handle.seek(0)
        handle.write(updated)
        handle.truncate()


def open_work_pr(root: Path, work_id: str, title: str, tool: str, tracker=None) -> str:
    if tool not in ("Claude Code", "Codex"):
        raise SystemExit("도구는 Claude Code 또는 Codex다")
    if not ISSUE_ID.fullmatch(work_id):
        raise SystemExit("작업ID가 이슈 번호가 아니다")
    if not title.strip():
        raise SystemExit("제목이 없다")
    log_path = root / ".team" / "sessions" / work_id / "log.md"
    if not log_path.is_file():
        raise SystemExit(f"log.md가 없다: {work_id}")
    active = tracker if tracker is not None else load_tracker(root)
    body = f"{active.issue_link(int(work_id))}\n"
    url = active.open_pull_request(title.strip(), body, commanded=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    text = log_path.read_text(encoding="utf-8")
    if text and not text.endswith("\n"):
        text += "\n"
    text += f"{stamp} {tool} push {url}\n"
    log_path.write_text(text, encoding="utf-8")
    return url


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
    start = sub.add_parser(
        "start-context",
        help="현황판의 열린 줄과 작업 하나의 state.md를 낸다.",
    )
    start.add_argument(
        "--switch",
        action="store_true",
        help="도구를 바꿀 때 로그 마지막 5줄을 더한다.",
    )
    pull = sub.add_parser("pull", help="사람이 명령했을 때만 PR을 연다.")
    pull.add_argument("work_id")
    pull.add_argument("--title", required=True)
    pull.add_argument("--tool", required=True)
    sub.add_parser("board", help="현황판을 읽기로 갱신한다.")
    rotate = sub.add_parser("rotate", help="로그가 상한을 넘으면 앞부분을 log/로 옮긴다.")
    rotate.add_argument("work_id")
    sub.add_parser("check", help="상태 파일과 로그와 시작 주입 상한을 검사한다.")
    mode = sub.add_parser("mode", help="열린 작업 상태 파일 첫 줄의 모드만 바꾼다.")
    mode.add_argument("name")
    args = parser.parse_args(argv)
    root = repo_root()
    try:
        if args.command == "new":
            create_session(root, args.work_id, args.session)
        elif args.command == "summary":
            sys.stdout.write(summary_text(root, args.work_id))
        elif args.command == "start-context":
            sys.stdout.write(render_start_context(root, current_branch(root), args.switch))
        elif args.command == "pull":
            sys.stdout.write(open_work_pr(root, args.work_id, args.title, args.tool) + "\n")
        elif args.command == "board":
            refresh_board(root)
        elif args.command == "rotate":
            rotate_log(root, args.work_id)
        elif args.command == "mode":
            sys.stdout.write(set_mode(root, current_branch(root), args.name))
        elif args.command == "check":
            errors = limit_errors(root, current_branch(root))
            if errors:
                print("\n".join(errors), file=sys.stderr)
                return 1
    except IssueTrackerError as exc:
        print(redact(str(exc)), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
