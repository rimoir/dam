#!/usr/bin/env python3
"""issue-tracker 어댑터.

GitHub 명령은 이 파일에만 둔다. 작업 시작은 gh issue view로 읽기만 한다.
코멘트, 라벨, 이슈 닫기, PR 열기는 사람이 commanded=True로 명령했을 때만 이 함수들이 gh를 부른다.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol


class IssueTrackerError(Exception):
    """이슈를 읽거나 쓰지 못한 이유. 노트에 쓰기 전에 올린다."""


@dataclass(frozen=True)
class IssueRecord:
    number: int
    title: str
    url: str
    acceptance: tuple[str, ...]


@dataclass(frozen=True)
class GhResult:
    code: int
    stdout: str
    stderr: str


Runner = Callable[..., GhResult]

_TOKEN = re.compile(
    r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"
)
_USERINFO = re.compile(r"https://[^/\s]+@")
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_ITEM = re.compile(r"^\s*[-*]\s+(?:\[[ xX]\]\s+)?(.+?)\s*$")
_COVERS = re.compile(r"^\s*(?:[-*]\s+)?Covers:\s*(.+?)\s*$")
_ISSUE_URL = re.compile(r"^https://github\.com/[^/\s]+/[^/\s]+/issues/[0-9]+$")
_SLUGS = (
    re.compile(r"^https://github\.com/([^/\s]+)/([^/\s]+?)(?:\.git)?/?$"),
    re.compile(r"^git@github\.com:([^/\s]+)/([^/\s]+?)(?:\.git)?$"),
    re.compile(r"^ssh://git@github\.com/([^/\s]+)/([^/\s]+?)(?:\.git)?/?$"),
)


def redact(text: str) -> str:
    text = _USERINFO.sub("https://", text)
    return _TOKEN.sub("***", text)


def github_slug(remote_url: str) -> str | None:
    url = _USERINFO.sub("https://", remote_url.strip())
    for pattern in _SLUGS:
        match = pattern.fullmatch(url)
        if not match:
            continue
        owner, repo = match.group(1), match.group(2)
        if owner and repo and "/" not in owner and "/" not in repo:
            return f"{owner}/{repo}"
    return None


def _section(body: str, title: str) -> str | None:
    lines = body.splitlines()
    start = None
    level = 0
    wanted = title.casefold()
    for index, line in enumerate(lines):
        match = _HEADING.match(line)
        if match and match.group(2).strip().casefold() == wanted:
            start = index + 1
            level = len(match.group(1))
            break
    if start is None:
        return None
    end = len(lines)
    for index in range(start, len(lines)):
        match = _HEADING.match(lines[index])
        if match and len(match.group(1)) <= level:
            end = index
            break
    return "\n".join(lines[start:end])


def _list_items(section: str | None) -> list[str]:
    if not section:
        return []
    items: list[str] = []
    for line in section.splitlines():
        match = _ITEM.match(line)
        if not match:
            continue
        text = match.group(1).strip()
        if text:
            items.append(text)
    return items


def acceptance_from_body(body: str) -> tuple[str, ...]:
    items = _list_items(_section(body, "Acceptance Criteria"))
    if not items:
        items = _list_items(_section(body, "완료 기준"))
    if not items:
        items = []
        for line in body.splitlines():
            match = _COVERS.match(line)
            if match and match.group(1).strip():
                items.append(match.group(1).strip())
    return tuple(items)


def one_line(text: str) -> str:
    return redact(text).replace("\r", " ").replace("\n", " ").strip()


def default_runner(args: list[str], stdin: str | None = None) -> GhResult:
    try:
        proc = subprocess.run(
            args,
            input=stdin,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return GhResult(1, "", "gh 응답이 없었다")
    except OSError:
        return GhResult(1, "", "gh CLI가 없다")
    return GhResult(proc.returncode, proc.stdout, proc.stderr)


class IssueReader(Protocol):
    def read_issue(self, number: int) -> IssueRecord:
        """이슈 번호로 제목, 링크, 완료 기준 목록을 읽는다."""


class GithubIssueTracker:
    def __init__(self, slug: str, runner: Runner | None = None) -> None:
        self.slug = slug
        self.runner = runner or default_runner

    def read_issue(self, number: int) -> IssueRecord:
        if number < 1:
            raise IssueTrackerError("이슈를 읽지 못했다: 이슈 번호가 아니다")
        result = self.runner(
            [
                "gh",
                "issue",
                "view",
                str(number),
                "--repo",
                self.slug,
                "--json",
                "title,url,body",
            ]
        )
        if result.code != 0:
            reason = redact(result.stderr).strip() or "gh가 실패했다"
            raise IssueTrackerError(f"이슈를 읽지 못했다: {reason}")
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            raise IssueTrackerError("이슈를 읽지 못했다: gh 출력이 JSON이 아니다") from None
        if not isinstance(data, dict):
            raise IssueTrackerError("이슈를 읽지 못했다: gh 출력이 JSON이 아니다")
        title = data.get("title")
        url = data.get("url")
        body = data.get("body") or ""
        if not isinstance(title, str):
            raise IssueTrackerError("이슈를 읽지 못했다: 제목이 없다")
        if not isinstance(url, str):
            raise IssueTrackerError("이슈를 읽지 못했다: 이슈 링크가 아니다")
        if not isinstance(body, str):
            body = ""
        title_line = one_line(title)
        url_line = one_line(url)
        if not title_line:
            raise IssueTrackerError("이슈를 읽지 못했다: 제목이 없다")
        if not _ISSUE_URL.fullmatch(url_line):
            raise IssueTrackerError("이슈를 읽지 못했다: 이슈 링크가 아니다")
        criteria = tuple(
            item for item in (one_line(piece) for piece in acceptance_from_body(body)) if item
        )
        return IssueRecord(
            number=number,
            title=title_line,
            url=url_line,
            acceptance=criteria,
        )

    def comment(self, number: int, body: str, *, commanded: bool) -> None:
        self._write(
            ["gh", "issue", "comment", str(number), "--repo", self.slug, "--body-file", "-"],
            commanded,
            stdin=body,
        )

    def add_label(self, number: int, label: str, *, commanded: bool) -> None:
        self._write(
            ["gh", "issue", "edit", str(number), "--repo", self.slug, "--add-label", label],
            commanded,
        )

    def close_issue(self, number: int, *, commanded: bool) -> None:
        self._write(
            ["gh", "issue", "close", str(number), "--repo", self.slug],
            commanded,
        )

    def open_pull_request(self, title: str, body: str, *, commanded: bool) -> None:
        self._write(
            ["gh", "pr", "create", "--repo", self.slug, "--title", title, "--body-file", "-"],
            commanded,
            stdin=body,
        )

    def _write(self, args: list[str], commanded: bool, stdin: str | None = None) -> None:
        if not commanded:
            raise IssueTrackerError("GitHub 쓰기는 사람이 그 동작을 직접 명령했을 때만 한다")
        result = self.runner(args, stdin)
        if result.code != 0:
            reason = redact(result.stderr).strip() or "gh가 실패했다"
            raise IssueTrackerError(f"GitHub에 쓰지 못했다: {reason}")


def lock_tracker(notes_root: Path) -> str:
    path = notes_root / ".team" / "adapters.lock"
    if not path.is_file():
        return "github"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        raise IssueTrackerError("이슈를 읽지 못했다: adapters.lock을 읽지 못했다") from None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip() != "issue-tracker":
            continue
        selected = value.strip().strip('"').strip("'")
        return selected or "github"
    return "github"


def repo_slug(repo_root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "remote", "get-url", "origin"],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise IssueTrackerError("이슈를 읽지 못했다: GitHub 저장소를 찾지 못했다") from None
    if proc.returncode != 0:
        raise IssueTrackerError("이슈를 읽지 못했다: GitHub 저장소를 찾지 못했다")
    slug = github_slug(proc.stdout.strip())
    if not slug:
        raise IssueTrackerError("이슈를 읽지 못했다: GitHub 저장소를 찾지 못했다")
    return slug


def load_tracker(notes_root: Path, repo_root: Path | None = None) -> GithubIssueTracker:
    selected = lock_tracker(notes_root)
    if selected != "github":
        raise IssueTrackerError(
            f"이슈를 읽지 못했다: issue-tracker 선택을 모른다: {selected}"
        )
    root = repo_root or Path(__file__).resolve().parents[1]
    return GithubIssueTracker(repo_slug(root))
