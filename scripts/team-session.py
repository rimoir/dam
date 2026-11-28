#!/usr/bin/env python3
"""작업 노트 네 파일과 board.md 한 줄을 만든다.

도구 전용 형식을 쓰지 않는다. 같은 작업ID로 다시 실행해도 노트를 덮어쓰지 않는다.
"""

from __future__ import annotations

import argparse
import fcntl
import os
import re
import subprocess
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
from verify_report import (  # noqa: E402
    changed_stamp_paths,
    compare_stamps,
    digest_ok,
    dump_snapshot,
    expect_matches,
    load_snapshot,
    parse_verify_report,
    run_isolated_readonly,
    snapshot_digest,
    snapshot_outside,
    take_snapshot,
    verdict_word,
)
from verify_comment import judge_verify_comment, valid_session_id  # noqa: E402
from worker_merge import (  # noqa: E402
    author_session_from_body,
    merge_refusal,
    parse_created,
)
from verify_session import open_verify_session  # noqa: E402
from session_context import (  # noqa: E402
    current_branch,
    limit_errors,
    render_start_context,
    render_verify_start,
    render_recorded_result,
    rotate_log,
    verification_log_line,
    verify_start_or_none,
    code_dirty_paths,
    begin_resume,
    end_resume,
    plan_check,
    set_mode,
    text_line_errors,
    worker_push_block,
    worker_push_refspec,
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
_LAST_LOG = re.compile(r", 마지막 로그 ([^,\n]+)")


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
        rest = line.rstrip("\n")[match.end() :]
        last = _LAST_LOG.search(rest)
        last_clause = f", 마지막 로그 {last.group(1).strip()}" if last else ""
        pieces.append(f"{prefix}{last_clause}, {github_clause(view)}{ending}")
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


def run_worker_merge(root: Path, number: int) -> str:
    tracker = load_tracker(root)
    view = tracker.read_pull_request(number)
    head = view.get("headRefOid")
    created = view.get("createdAt")
    mergeable = view.get("mergeable")
    body = view.get("body") or ""
    raw_comments = view.get("comments") or []
    if not isinstance(head, str) or not isinstance(created, str) or not isinstance(mergeable, str):
        raise SystemExit("PR을 읽지 못했다")
    if not isinstance(body, str) or not isinstance(raw_comments, list):
        raise SystemExit("PR을 읽지 못했다")
    comments: list[str] = []
    for item in raw_comments:
        if isinstance(item, dict) and isinstance(item.get("body"), str):
            comments.append(item["body"])
        elif isinstance(item, str):
            comments.append(item)
        else:
            raise SystemExit("PR을 읽지 못했다")
    try:
        opened = parse_created(created)
    except ValueError as exc:
        raise SystemExit("PR을 읽지 못했다") from exc
    reason = merge_refusal(
        author_session=author_session_from_body(body),
        checks=tracker.read_pull_checks(number),
        comments=comments,
        head=head.strip(),
        created_at=opened,
        now=datetime.now(timezone.utc),
        mergeable=mergeable,
    )
    if reason:
        raise SystemExit(reason)
    tracker.merge_squash(number, head.strip(), commanded=True)
    return f"머지 {head.strip()}\n"


def run_worker_push(
    root: Path,
    work_id: str,
    title: str,
    tool: str,
    target: str,
    force: bool,
) -> str:
    if tool not in ("Claude Code", "Codex"):
        raise SystemExit("도구는 Claude Code 또는 Codex다")
    if not ISSUE_ID.fullmatch(work_id):
        raise SystemExit("작업ID가 이슈 번호가 아니다")
    if not title.strip():
        raise SystemExit("제목이 없다")
    log_path = root / ".team" / "sessions" / work_id / "log.md"
    if not log_path.is_file():
        raise SystemExit(f"log.md가 없다: {work_id}")
    branch = current_branch(root).strip()
    reason = worker_push_block(
        log_path.read_text(encoding="utf-8"),
        branch,
        work_id,
        target,
        force,
    )
    if reason:
        raise SystemExit(reason)
    session = os.environ.get("DAM_SESSION_ID", "").strip()
    if not valid_session_id(session):
        raise SystemExit("세션 id가 없거나 형식이 아니다")
    done = subprocess.run(
        ["git", "-C", str(root), "push", "origin", worker_push_refspec(branch)],
        check=False,
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        detail = (done.stderr or done.stdout or "git push가 실패했다").strip()
        raise SystemExit(detail or "git push가 실패했다")
    return open_work_pr(root, work_id, title, tool, author_session=session)


def open_work_pr(
    root: Path,
    work_id: str,
    title: str,
    tool: str,
    tracker=None,
    author_session: str | None = None,
) -> str:
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
    if author_session is not None:
        if not valid_session_id(author_session):
            raise SystemExit("세션 id가 없거나 형식이 아니다")
        body += f"세션 id: {author_session}\n"
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


def record_verification(
    root: Path,
    work_id: str,
    tool: str,
    model: str,
    head: str,
    text: str,
) -> tuple[int, str]:
    if tool not in ("Claude Code", "Codex"):
        return 1, "실패\n"
    model_text = model.strip()
    if not model_text or "\n" in model or "\r" in model:
        return 1, "실패\n"
    if not valid_work_id(work_id):
        return 1, "실패\n"
    folder = root / ".team" / "sessions" / work_id
    result_path = folder / "result.md"
    log_path = folder / "log.md"
    if not result_path.is_file() or not log_path.is_file():
        return 1, "실패\n"
    word = verdict_word(text, head)
    if word != "PASS":
        return 1, word + "\n"
    report = parse_verify_report(text)
    if report is None:
        return 1, "실패\n"
    safe_model = redact(model_text).strip()
    safe_evidence = redact(report.evidence).strip()
    if not safe_model or not safe_evidence or "\n" in safe_model or "\n" in safe_evidence:
        return 1, "실패\n"
    rendered = render_recorded_result(
        result_path.read_text(encoding="utf-8"),
        f"PASS 헤드 {report.head[:7]} 모델 {safe_model}",
        safe_evidence,
    )
    if rendered is None:
        return 1, "실패\n"
    log_raw = log_path.read_text(encoding="utf-8")
    if log_raw and not log_raw.endswith("\n"):
        log_raw += "\n"
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = verification_log_line(stamp, tool, safe_model, report.head)
    result_path.write_text(rendered, encoding="utf-8")
    log_path.write_text(log_raw + line + "\n", encoding="utf-8")
    rotate_log(root, work_id)
    return 0, "남김\n"


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
    start.add_argument("--role", default=None)
    start.add_argument("--criteria", default=None)
    start.add_argument("--base", default=None)
    start.add_argument("--head", default=None)
    start.add_argument("--checks", default=None)
    verify_session = sub.add_parser("verify-session", help="훅 없는 복사본에서 검증 세션을 띄운다.")
    verify_session.add_argument("--criteria", required=True)
    verify_session.add_argument("--base", required=True)
    verify_session.add_argument("--head", required=True)
    verify_session.add_argument("--checks", required=True)
    merge = sub.add_parser("worker-merge", help="조건을 모두 확인한 뒤에만 squash 머지한다.")
    merge.add_argument("number")
    ship = sub.add_parser("worker-push", help="승인된 작업 브랜치로만 push하고 PR을 연다.")
    ship.add_argument("work_id")
    ship.add_argument("--title", required=True)
    ship.add_argument("--tool", required=True)
    ship.add_argument("--target", default="")
    ship.add_argument("--force", action="store_true")
    pull = sub.add_parser("pull", help="사람이 명령했을 때만 PR을 연다.")
    pull.add_argument("work_id")
    pull.add_argument("--title", required=True)
    pull.add_argument("--tool", required=True)
    sub.add_parser("board", help="현황판을 읽기로 갱신한다.")
    rotate = sub.add_parser("rotate", help="로그가 상한을 넘으면 앞부분을 log/로 옮긴다.")
    rotate.add_argument("work_id")
    sub.add_parser("check", help="상태 파일과 로그와 시작 주입 상한을 검사한다.")
    mode = sub.add_parser("mode", help="열린 작업 상태 파일 첫 줄의 모드만 바꾼다.")
    mode.add_argument("name", nargs="+")
    sub.add_parser("code-clean", help="코드 파일이 바뀌지 않았는지 읽기만 한다.")
    record = sub.add_parser("verify-record", help="통과한 검증 결과를 노트에 남긴다.")
    record.add_argument("--work", required=True)
    record.add_argument("--tool", required=True)
    record.add_argument("--model", required=True)
    record.add_argument("--head", required=True)
    record.add_argument("--text", required=True)
    comment = sub.add_parser("verify-comment", help="검증 코멘트가 검토 기록인지 판정한다.")
    comment.add_argument("--head", required=True)
    comment.add_argument("--text", required=True)
    judge = sub.add_parser("verify-judge", help="검증 결과 문자열을 판정한다.")
    judge.add_argument("--head", required=True)
    judge.add_argument("--text", required=True)
    readonly = sub.add_parser("verify-readonly", help="작업 폴더 스냅샷을 찍거나 비교한다.")
    readonly.add_argument("--begin", action="store_true")
    readonly.add_argument("--end", action="store_true")
    readonly.add_argument("--isolated", action="store_true")
    readonly.add_argument("--snapshot", default="")
    readonly.add_argument("--expect", default="")
    readonly.add_argument("--command", dest="verify_command", default="")
    plan = sub.add_parser("plan-check", help="기능 계획의 네 칸을 읽기만 한다.")
    plan.add_argument("work_id")
    resume = sub.add_parser("resume", help="이어받기 모드로 바꾸거나 이전 모드로 돌린다.")
    resume.add_argument("step", choices=("begin", "end"))
    args = parser.parse_args(argv)
    root = repo_root()
    try:
        if args.command == "new":
            create_session(root, args.work_id, args.session)
        elif args.command == "summary":
            sys.stdout.write(summary_text(root, args.work_id))
        elif args.command == "start-context":
            try:
                selected = verify_start_or_none(
                    args.role,
                    args.criteria,
                    args.base,
                    args.head,
                    args.checks,
                    args.switch,
                )
            except ValueError as exc:
                raise SystemExit(str(exc)) from exc
            if selected is None:
                sys.stdout.write(render_start_context(root, current_branch(root), args.switch))
            else:
                sys.stdout.write(render_verify_start(selected))
        elif args.command == "verify-session":
            try:
                selected = verify_start_or_none(
                    "검증",
                    args.criteria,
                    args.base,
                    args.head,
                    args.checks,
                    False,
                )
            except ValueError as exc:
                raise SystemExit(str(exc)) from exc
            if selected is None:
                raise SystemExit("검증 입력이 없다")
            code, out, err = open_verify_session(root, render_verify_start(selected))
            sys.stdout.write(out)
            if err:
                sys.stderr.write(err if err.endswith("\n") else err + "\n")
            return code
        elif args.command == "worker-merge":
            if not ISSUE_ID.fullmatch(args.number):
                raise SystemExit("PR 번호가 아니다")
            sys.stdout.write(run_worker_merge(root, int(args.number)))
        elif args.command == "worker-push":
            url = run_worker_push(
                root,
                args.work_id,
                args.title,
                args.tool,
                args.target,
                args.force,
            )
            sys.stdout.write(url + "\n")
        elif args.command == "pull":
            sys.stdout.write(open_work_pr(root, args.work_id, args.title, args.tool) + "\n")
        elif args.command == "board":
            refresh_board(root)
        elif args.command == "rotate":
            rotate_log(root, args.work_id)
        elif args.command == "mode":
            sys.stdout.write(set_mode(root, current_branch(root), " ".join(args.name)))
        elif args.command == "code-clean":
            dirty = code_dirty_paths(root)
            if dirty:
                print("\n".join(dirty), file=sys.stderr)
                return 1
        elif args.command == "verify-record":
            code, out = record_verification(
                root,
                args.work,
                args.tool,
                args.model,
                args.head,
                args.text,
            )
            sys.stdout.write(out)
            return code
        elif args.command == "verify-comment":
            word = judge_verify_comment(args.text, args.head)
            sys.stdout.write(word + "\n")
            return 0 if word == "검토 기록" else 1
        elif args.command == "verify-judge":
            word = verdict_word(args.text, args.head)
            sys.stdout.write(word + "\n")
            return 0 if word == "PASS" else 1
        elif args.command == "verify-readonly":
            if args.isolated:
                if args.begin or args.end or not args.verify_command.strip() or not args.snapshot:
                    sys.stdout.write("실패\n")
                    return 1
                word = run_isolated_readonly(root, args.verify_command, Path(args.snapshot))
                sys.stdout.write(word + "\n")
                return 0 if word == "깨끗" else 1
            if args.begin == args.end or not args.snapshot:
                sys.stdout.write("실패\n")
                return 1
            snap = Path(args.snapshot)
            if not snapshot_outside(root, snap):
                sys.stdout.write("실패\n")
                return 1
            if args.begin:
                try:
                    data = dump_snapshot(take_snapshot(root)).encode("utf-8")
                except OSError:
                    sys.stdout.write("실패\n")
                    return 1
                snap.write_bytes(data)
                sys.stdout.write(snapshot_digest(data) + "\n")
                return 0
            if not digest_ok(args.expect.strip()):
                sys.stdout.write("실패\n")
                return 1
            if not snap.is_file():
                sys.stdout.write("실패\n")
                return 1
            try:
                raw_bytes = snap.read_bytes()
            except OSError:
                sys.stdout.write("실패\n")
                return 1
            if not expect_matches(raw_bytes, args.expect.strip()):
                sys.stdout.write("실패\n")
                return 1
            try:
                raw = raw_bytes.decode("utf-8")
            except UnicodeError:
                sys.stdout.write("실패\n")
                return 1
            before = load_snapshot(raw)
            if before is None:
                sys.stdout.write("실패\n")
                return 1
            try:
                after = take_snapshot(root)
            except OSError:
                sys.stdout.write("실패\n")
                return 1
            word = compare_stamps(before, after)
            sys.stdout.write(word + "\n")
            if word == "실패":
                names = changed_stamp_paths(before, after)
                if names:
                    print("\n".join(names), file=sys.stderr)
            return 0 if word == "깨끗" else 1
        elif args.command == "plan-check":
            errors, notice = plan_check(root, args.work_id)
            if notice:
                sys.stdout.write(notice)
            if errors:
                print("\n".join(errors), file=sys.stderr)
                return 1
        elif args.command == "resume":
            if args.step == "begin":
                sys.stdout.write(begin_resume(root, current_branch(root)))
            else:
                sys.stdout.write(end_resume(root, current_branch(root)))
        elif args.command == "check":
            errors = limit_errors(root, current_branch(root))
            errors.extend(text_line_errors(root))
            if errors:
                print("\n".join(errors), file=sys.stderr)
                return 1
    except IssueTrackerError as exc:
        print(redact(str(exc)), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
