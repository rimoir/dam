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
class WorkView:
    issue_closed: bool
    pull_state: str
    checks: str


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
_PR_URL = re.compile(r"^https://github\.com/[^/\s]+/[^/\s]+/pull/[0-9]+$")
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


def _heading_sections(body: str) -> list[tuple[str, str]]:
    lines = body.splitlines()
    heads: list[tuple[int, int, str]] = []
    for index, line in enumerate(lines):
        match = _HEADING.match(line)
        if match:
            heads.append((index, len(match.group(1)), match.group(2).strip()))
    sections: list[tuple[str, str]] = []
    for pos, (index, level, title) in enumerate(heads):
        end = len(lines)
        for later, later_level, _title in heads[pos + 1 :]:
            if later_level <= level:
                end = later
                break
        sections.append((title, "\n".join(lines[index + 1 : end])))
    return sections


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


def _criteria_heading(title: str) -> bool:
    folded = title.casefold()
    return (
        "acceptance criteria" in folded
        or "완료 기준" in title
        or "완료 조건" in title
    )


def acceptance_from_body(body: str) -> tuple[str, ...]:
    for title, content in _heading_sections(body):
        if not _criteria_heading(title):
            continue
        items = _list_items(content)
        if items:
            return tuple(items)
    items: list[str] = []
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

    def issue_link(self, number: int) -> str:
        return f"https://github.com/{self.slug}/issues/{number}"

    def read_status(self, number: int) -> WorkView:
        issue = self._read_json(
            [
                "gh",
                "issue",
                "view",
                str(number),
                "--repo",
                self.slug,
                "--json",
                "state,closedByPullRequestsReferences",
            ],
            "이슈 상태가 아니다",
        )
        if not isinstance(issue, dict) or issue.get("state") not in ("OPEN", "CLOSED"):
            raise IssueTrackerError("이슈를 읽지 못했다: 이슈 상태가 아니다")
        prs = self._read_json(
            [
                "gh",
                "pr",
                "list",
                "--repo",
                self.slug,
                "--state",
                "all",
                "--limit",
                "50",
                "--search",
                str(number),
                "--json",
                "number,state,body,closingIssuesReferences",
            ],
            "PR 목록이 아니다",
        )
        if not isinstance(prs, list):
            raise IssueTrackerError("이슈를 읽지 못했다: PR 목록이 아니다")
        closed_by = issue.get("closedByPullRequestsReferences") or []
        chosen = _matching_pr(prs, number, closed_by if isinstance(closed_by, list) else [])
        closed = issue["state"] == "CLOSED"
        if chosen is None:
            return WorkView(issue_closed=closed, pull_state="none", checks="none")
        state = chosen.get("state")
        if state == "OPEN":
            return WorkView(
                issue_closed=closed,
                pull_state="open",
                checks=self._check_word(int(chosen["number"])),
            )
        if state == "MERGED":
            return WorkView(issue_closed=closed, pull_state="merged", checks="none")
        return WorkView(issue_closed=closed, pull_state="closed", checks="none")

    def _read_json(self, args: list[str], why: str):
        result = self.runner(args)
        if result.code != 0 and not (result.stdout or "").strip():
            reason = redact(result.stderr).strip() or "gh가 실패했다"
            raise IssueTrackerError(f"이슈를 읽지 못했다: {reason}")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            raise IssueTrackerError(f"이슈를 읽지 못했다: {why}") from None

    def _check_word(self, pr_number: int) -> str:
        result = self.runner(
            [
                "gh",
                "pr",
                "checks",
                str(pr_number),
                "--repo",
                self.slug,
                "--json",
                "name,bucket,state",
            ]
        )
        stdout = (result.stdout or "").strip()
        stderr = result.stderr or ""
        if not stdout and "no checks reported" in stderr.lower():
            return "pending"
        if result.code != 0 and not stdout:
            reason = redact(stderr).strip() or "gh가 실패했다"
            raise IssueTrackerError(f"이슈를 읽지 못했다: {reason}")
        try:
            rows = json.loads(result.stdout) if stdout else []
        except json.JSONDecodeError:
            raise IssueTrackerError("이슈를 읽지 못했다: 검사 결과가 아니다") from None
        if not isinstance(rows, list) or not rows:
            return "pending"
        buckets = {
            row.get("bucket")
            for row in rows
            if isinstance(row, dict) and row.get("bucket")
        }
        if "fail" in buckets or "cancel" in buckets:
            return "fail"
        if "pending" in buckets:
            return "pending"
        if "pass" in buckets:
            return "pass"
        return "pending"

    def open_pull_request(self, title: str, body: str, *, commanded: bool) -> str:
        result = self._write(
            ["gh", "pr", "create", "--repo", self.slug, "--title", title, "--body-file", "-"],
            commanded,
            stdin=body,
        )
        found = ""
        for line in redact(result.stdout).splitlines():
            candidate = line.strip()
            if _PR_URL.fullmatch(candidate):
                found = candidate
        if not found:
            raise IssueTrackerError("PR 주소를 읽지 못했다")
        return found

    def _write(self, args: list[str], commanded: bool, stdin: str | None = None) -> GhResult:
        if not commanded:
            raise IssueTrackerError("GitHub 쓰기는 사람이 그 동작을 직접 명령했을 때만 한다")
        result = self.runner(args, stdin)
        if result.code != 0:
            reason = redact(result.stderr).strip() or "gh가 실패했다"
            raise IssueTrackerError(f"GitHub에 쓰지 못했다: {reason}")
        return result


def _closes_issue(body: str, number: int) -> bool:
    return re.search(
        rf"(?i)(?:^|\s)(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#{number}(?!\d)",
        body,
    ) is not None


def _matching_pr(prs: list, number: int, closed_by: list | None = None) -> dict | None:
    closed_ids = {
        item.get("number")
        for item in (closed_by or [])
        if isinstance(item, dict)
    }
    matched: list[dict] = []
    for item in prs:
        if not isinstance(item, dict):
            continue
        refs = item.get("closingIssuesReferences") or []
        linked = any(isinstance(ref, dict) and ref.get("number") == number for ref in refs)
        body = item.get("body") or ""
        if (
            linked
            or item.get("number") in closed_ids
            or (isinstance(body, str) and _closes_issue(body, number))
        ):
            matched.append(item)
    for item in closed_by or []:
        if isinstance(item, dict) and item.get("number") not in {row.get("number") for row in matched}:
            merged = dict(item)
            merged.setdefault("state", "MERGED")
            matched.append(merged)
    rank = {"OPEN": 0, "MERGED": 1, "CLOSED": 2}
    best: dict | None = None
    best_rank = 9
    for item in matched:
        score = rank.get(str(item.get("state")), 9)
        if score < best_rank:
            best = item
            best_rank = score
    return best


def lock_tracker(notes_root: Path) -> str:
    path = notes_root / ".team" / "adapters.lock"
    if not path.is_file():
        return "github"
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
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
