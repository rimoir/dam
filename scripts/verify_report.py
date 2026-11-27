#!/usr/bin/env python3
"""검증 결과 판정. 문자열과 작업 폴더 스냅샷만 본다."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

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


_SKIP = frozenset({".git", ".team"})


@dataclass(frozen=True)
class FileStamp:
    path: str
    kind: str
    mode: int
    size: int
    ino: int
    mtime_ns: int
    ctime_ns: int
    payload: str


def compare_stamps(before: tuple[FileStamp, ...], after: tuple[FileStamp, ...]) -> str:
    if before == after:
        return "깨끗"
    return "실패"


def changed_stamp_paths(before: tuple[FileStamp, ...], after: tuple[FileStamp, ...]) -> tuple[str, ...]:
    old = {item.path: item for item in before}
    new = {item.path: item for item in after}
    names = sorted(set(old) | set(new))
    return tuple(name for name in names if old.get(name) != new.get(name))


def snapshot_outside(root: Path, snapshot: Path) -> bool:
    if snapshot.is_symlink():
        return False
    parent = snapshot.parent
    if not parent.is_dir() or parent.is_symlink():
        return False
    root_r = root.resolve()
    try:
        parent.resolve().relative_to(root_r)
        return False
    except ValueError:
        pass
    if snapshot.exists():
        try:
            snapshot.resolve().relative_to(root_r)
            return False
        except ValueError:
            return True
    return True


def _sha256(path: Path) -> str:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags)
    try:
        digest = hashlib.sha256()
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        return digest.hexdigest()
    finally:
        os.close(fd)


def _stamp(root: Path, path: Path) -> FileStamp:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        kind = "link"
        payload = os.readlink(path)
    elif stat.S_ISREG(info.st_mode):
        kind = "file"
        payload = _sha256(path)
    else:
        kind = "other"
        payload = ""
    return FileStamp(
        path.relative_to(root).as_posix(),
        kind,
        info.st_mode,
        info.st_size,
        info.st_ino,
        info.st_mtime_ns,
        info.st_ctime_ns,
        payload,
    )


def take_snapshot(root: Path) -> tuple[FileStamp, ...]:
    base = root.resolve()
    found: list[FileStamp] = []
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        current = Path(dirpath)
        kept: list[str] = []
        for name in dirnames:
            candidate = current / name
            if name in _SKIP:
                continue
            if candidate.is_symlink():
                found.append(_stamp(base, candidate))
                continue
            kept.append(name)
        dirnames[:] = kept
        for name in filenames:
            if name in _SKIP and current == base:
                continue
            found.append(_stamp(base, current / name))
    found.sort(key=lambda item: item.path)
    return tuple(found)


def dump_snapshot(stamps: tuple[FileStamp, ...]) -> str:
    body = {
        "files": [
            {
                "ctime_ns": item.ctime_ns,
                "ino": item.ino,
                "kind": item.kind,
                "mode": item.mode,
                "mtime_ns": item.mtime_ns,
                "path": item.path,
                "payload": item.payload,
                "size": item.size,
            }
            for item in stamps
        ],
        "version": 1,
    }
    return json.dumps(body, ensure_ascii=False, sort_keys=True)


def load_snapshot(text: str) -> tuple[FileStamp, ...] | None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or data.get("version") != 1:
        return None
    files = data.get("files")
    if not isinstance(files, list):
        return None
    found: list[FileStamp] = []
    for item in files:
        if not isinstance(item, dict):
            return None
        try:
            stamp = FileStamp(
                path=item["path"],
                kind=item["kind"],
                mode=int(item["mode"]),
                size=int(item["size"]),
                ino=int(item["ino"]),
                mtime_ns=int(item["mtime_ns"]),
                ctime_ns=int(item["ctime_ns"]),
                payload=item["payload"],
            )
        except (KeyError, TypeError, ValueError):
            return None
        if not isinstance(stamp.path, str) or not isinstance(stamp.kind, str):
            return None
        if not isinstance(stamp.payload, str):
            return None
        parts = Path(stamp.path).parts
        if not stamp.path or stamp.path.startswith("/") or ".." in parts:
            return None
        found.append(stamp)
    found.sort(key=lambda item: item.path)
    return tuple(found)
