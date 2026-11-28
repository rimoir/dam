#!/usr/bin/env python3
"""검증 코멘트가 검토 기록인지 판정한다. 문자열과 기대 헤드만 본다."""

from __future__ import annotations

import re

_SHA = re.compile(r"^[0-9a-f]{40}$")
_SESSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_LABELS = ("세션 id", "헤드 SHA", "확인 방법", "증거 요약")


def render_verify_comment(session: str, head: str, method: str, evidence: str) -> str:
    return (
        f"세션 id: {session}\n"
        f"헤드 SHA: {head}\n"
        f"확인 방법: {method}\n"
        f"증거 요약: {evidence}\n"
    )


def _fields(text: str) -> dict[str, str] | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) != len(_LABELS):
        return None
    found: dict[str, str] = {}
    for line, label in zip(lines, _LABELS):
        prefix = label + ":"
        if not line.startswith(prefix):
            return None
        value = line[len(prefix) :].strip()
        if not value:
            return None
        found[label] = value
    return found


def valid_session_id(value: str) -> bool:
    return _SESSION.fullmatch(value) is not None


def verify_comment_session(text: str, expected_head: str) -> str | None:
    if judge_verify_comment(text, expected_head) != "검토 기록":
        return None
    fields = _fields(text)
    if fields is None:
        return None
    return fields["세션 id"]


def judge_verify_comment(text: str, expected_head: str) -> str:
    fields = _fields(text)
    if fields is None:
        return "아님"
    if _SESSION.fullmatch(fields["세션 id"]) is None:
        return "아님"
    if not fields["확인 방법"] or not fields["증거 요약"]:
        return "아님"
    head = fields["헤드 SHA"]
    expected = expected_head.strip()
    if _SHA.fullmatch(head) is None or _SHA.fullmatch(expected) is None:
        return "아님"
    if head != expected:
        return "무효"
    return "검토 기록"
