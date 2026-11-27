#!/usr/bin/env python3
"""검증 결과 판정. 문자열과 경로 목록만 본다."""

from __future__ import annotations

import re
from dataclasses import dataclass

_KINDS = frozenset({"PASS", "ISSUES", "BLOCKED"})
_SHA = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class VerifyReport:
    kind: str
    head: str
    method: str
    evidence: str

    def __post_init__(self) -> None:
        if self.kind not in _KINDS:
            raise ValueError("검증 결과 형식이 아니다")
        if _SHA.fullmatch(self.head) is None:
            raise ValueError("헤드 SHA가 아니다")
        if not self.method or self.method != self.method.strip():
            raise ValueError("확인 방법이 없다")
        if not self.evidence or self.evidence != self.evidence.strip():
            raise ValueError("증거 요약이 없다")


def _field(line: str, label: str) -> str | None:
    prefix = label + ":"
    if not line.startswith(prefix):
        return None
    return line[len(prefix) :].strip()


def parse_verify_report(text: str) -> VerifyReport | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) != 4 or lines[0] not in _KINDS:
        return None
    head = _field(lines[1], "헤드 SHA")
    method = _field(lines[2], "확인 방법")
    evidence = _field(lines[3], "증거 요약")
    if head is None or method is None or evidence is None:
        return None
    if not method or not evidence or _SHA.fullmatch(head) is None:
        return None
    return VerifyReport(lines[0], head, method, evidence)


def judge_verify(report: VerifyReport, expected_head: str) -> str:
    if report.head != expected_head:
        return "실패"
    return report.kind


def verdict_word(text: str, expected_head: str) -> str:
    expected = expected_head.strip()
    if _SHA.fullmatch(expected) is None:
        return "실패"
    report = parse_verify_report(text)
    if report is None:
        return "실패"
    return judge_verify(report, expected)


def paths_from_text(text: str) -> tuple[str, ...]:
    return tuple(line.strip() for line in text.splitlines() if line.strip())


def judge_readonly(start: tuple[str, ...], end: tuple[str, ...]) -> str:
    if start or end:
        return "실패"
    return "깨끗"
