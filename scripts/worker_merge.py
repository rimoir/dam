#!/usr/bin/env python3
"""머지 조건. gh JSON은 경계에서 풀고, 판정은 순수 함수다."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from verify_comment import judge_verify_comment, valid_session_id, verify_comment_session

CHECK_NAMES = ("python test", "rulesync regen", "gitleaks")
_ISSUE_URL = re.compile(r"^https://github\.com/[^/\s]+/[^/\s]+/issues/[0-9]+$")
_SHA = re.compile(r"^[0-9a-f]{40}$")


def author_session_from_body(body: str) -> str | None:
    lines = body.splitlines()
    for index, line in enumerate(lines):
        if not _ISSUE_URL.fullmatch(line.strip()):
            continue
        if index + 1 >= len(lines):
            return None
        nxt = lines[index + 1]
        prefix = "세션 id:"
        if not nxt.startswith(prefix):
            return None
        value = nxt[len(prefix) :].strip()
        if not valid_session_id(value):
            return None
        return value
    return None


def _check_word(row: dict) -> str:
    state = str(row.get("state") or "").upper()
    bucket = str(row.get("bucket") or "").lower()
    if state == "SUCCESS" or bucket == "pass":
        return "success"
    if state in {"PENDING", "QUEUED", "IN_PROGRESS", "WAITING"} or bucket == "pending":
        return "pending"
    return "failure"


def checks_refusal(rows: list[dict]) -> str | None:
    found: dict[str, list[str]] = {name: [] for name in CHECK_NAMES}
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        if name in found:
            found[name].append(_check_word(row))
    for name in CHECK_NAMES:
        words = found[name]
        if not words:
            return f"검사가 하나 빠졌다: {name}"
        if any(word == "failure" for word in words):
            return f"검사가 실패했다: {name}"
        if any(word == "pending" for word in words):
            return f"검사가 진행 중이다: {name}"
    return None


def _comment_refusal(comments: list[str], head: str, author: str) -> str | None:
    if not comments:
        return "검증 기록이 없다"
    saw_same = False
    saw_wrong_head = False
    saw_no_session = False
    saw_other = False
    for body in comments:
        word = judge_verify_comment(body, head)
        if word == "검토 기록":
            session = verify_comment_session(body, head)
            if session == author:
                saw_same = True
            elif session:
                return None
            else:
                saw_other = True
            continue
        if word == "무효":
            saw_wrong_head = True
            continue
        if not any(line.strip().startswith("세션 id:") for line in body.splitlines()):
            saw_no_session = True
        else:
            saw_other = True
    if saw_same:
        return "검증 세션이 만든 세션과 같다"
    if saw_wrong_head:
        return "검증한 헤드가 PR 헤드와 다르다"
    if saw_no_session:
        return "검증 코멘트에 세션 id가 없다"
    if saw_other:
        return "판정이 검토 기록이 아니다"
    return "검증 기록이 없다"


def merge_refusal(
    *,
    author_session: str | None,
    checks: list[dict],
    comments: list[str],
    head: str,
    created_at: datetime,
    now: datetime,
    mergeable: str,
) -> str | None:
    if not author_session or not valid_session_id(author_session):
        return "만든 세션 id가 없다"
    if _SHA.fullmatch(head) is None:
        return "PR 헤드가 아니다"
    blocked = checks_refusal(checks)
    if blocked:
        return blocked
    if mergeable != "MERGEABLE":
        return "충돌이 있어 머지할 수 없다"
    if now - created_at < timedelta(minutes=1):
        return "PR을 연 지 1분이 지나지 않았다"
    return _comment_refusal(comments, head, author_session)


def parse_created(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    found = datetime.fromisoformat(text)
    if found.tzinfo is None:
        found = found.replace(tzinfo=timezone.utc)
    return found.astimezone(timezone.utc)
