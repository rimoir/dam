#!/usr/bin/env python3
"""워커 시작, 지켜보기, 수거. 이 파일만 orchestrator 키를 읽는다.

실제 도구를 띄우는 코드는 없다. native와 fake는 같은 다섯 칸을 돌려준다.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

FIELDS = ("ok", "handle", "state", "line", "reason")
KNOWN = frozenset({"native", "fake"})
HANDLE = re.compile(r"^(native|fake)-[0-9]+$")


class OrchestratorError(Exception):
    pass


def notes_root(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit)
    override = os.environ.get("TEAM_ROOT")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[1]


def blank(**over: str) -> dict[str, str]:
    record = {key: "" for key in FIELDS}
    record.update(over)
    return record


def render(record: dict[str, str]) -> str:
    return "".join(f"{key}: {record[key]}\n" for key in FIELDS)


def lock_name(root: Path) -> str:
    path = root / ".team" / "adapters.lock"
    if not path.is_file():
        return "native"
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        raise OrchestratorError("adapters.lock을 읽지 못했다") from None
    selected = ""
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip() != "orchestrator":
            continue
        selected = value.strip().strip('"').strip("'")
    return selected or "native"


def _store(root: Path) -> Path:
    folder = root / ".team" / "orchestrator"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _path(root: Path, handle: str) -> Path:
    if HANDLE.fullmatch(handle) is None:
        raise OrchestratorError("핸들이 없다")
    return root / ".team" / "orchestrator" / f"{handle}.json"


def _write(root: Path, record: dict[str, str]) -> None:
    path = _path(root, record["handle"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")


def _read(root: Path, handle: str) -> dict[str, str]:
    path = _path(root, handle)
    if not path.is_file():
        return blank(ok="아니오", state="거부", reason="핸들이 없다")
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return blank(ok="아니오", state="거부", reason="핸들을 읽지 못했다")
    return blank(**{key: str(loaded.get(key, "")) for key in FIELDS})


def start(root: Path, unit: str) -> dict[str, str]:
    if not unit.strip():
        return blank(ok="아니오", state="거부", reason="단위가 없다")
    name = lock_name(root)
    if name not in KNOWN:
        return blank(
            ok="아니오",
            state="거부",
            reason=f"orchestrator 선택을 모른다: {name}",
        )
    folder = _store(root)
    number = 1 + sum(1 for _found in folder.glob(f"{name}-*.json"))
    record = blank(ok="예", handle=f"{name}-{number}", state="대기")
    _write(root, record)
    return _read(root, record["handle"])


def poll(root: Path, handle: str) -> dict[str, str]:
    try:
        return _read(root, handle)
    except OrchestratorError as exc:
        return blank(ok="아니오", state="거부", reason=str(exc))


def collect(root: Path, handle: str) -> dict[str, str]:
    return poll(root, handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="워커 시작과 수거 어댑터.")
    parser.add_argument("--root", default="")
    sub = parser.add_subparsers(dest="command", required=True)
    start_cmd = sub.add_parser("start", help="단위를 받아 핸들을 만든다.")
    start_cmd.add_argument("--unit", required=True)
    poll_cmd = sub.add_parser("poll", help="핸들의 상태를 읽는다.")
    poll_cmd.add_argument("--handle", required=True)
    collect_cmd = sub.add_parser("collect", help="결과 한 줄을 읽는다.")
    collect_cmd.add_argument("--handle", required=True)
    args = parser.parse_args(argv)
    root = notes_root(args.root or None)
    try:
        if args.command == "start":
            record = start(root, args.unit)
        elif args.command == "poll":
            record = poll(root, args.handle)
        else:
            record = collect(root, args.handle)
    except OrchestratorError as exc:
        record = blank(ok="아니오", state="거부", reason=str(exc))
    sys.stdout.write(render(record))
    return 0 if record["ok"] == "예" else 1


if __name__ == "__main__":
    sys.exit(main())
