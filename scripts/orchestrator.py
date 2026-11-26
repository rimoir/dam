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
from pathlib import Path, PurePosixPath

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from session_context import _plan_path, log_has_go, read_plan_units  # noqa: E402

FIELDS = ("ok", "handle", "state", "line", "reason")
KNOWN = frozenset({"native", "fake"})
HANDLE = re.compile(r"^(native|fake)-[0-9]+$")
WORKER_LIMIT = 3  # 임시. 측정 뒤 고친다.


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


def paths_overlap(left: str, right: str) -> bool:
    left_path = PurePosixPath(_plan_path(left))
    right_path = PurePosixPath(_plan_path(right))
    if str(left_path) in ("", ".") or str(right_path) in ("", "."):
        return False
    if left_path == right_path:
        return True
    try:
        left_path.relative_to(right_path)
        return True
    except ValueError:
        pass
    try:
        right_path.relative_to(left_path)
        return True
    except ValueError:
        return False


def _unit_files(files: str) -> tuple[str, ...]:
    return tuple(piece for piece in files.replace(",", " ").split() if piece)


def admit_work(
    root: Path,
    work_id: str,
    running: int = 0,
    selected: list[str] | None = None,
    finished: list[str] | None = None,
) -> dict[str, str]:
    folder = root / ".team" / "sessions" / work_id
    task_path = folder / "task.md"
    if not task_path.is_file():
        return blank(ok="아니오", state="거부", reason=f"task.md가 없다: {work_id}")
    log_path = folder / "log.md"
    log_text = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
    if not log_has_go(log_text):
        return blank(ok="아니오", state="거부", reason="go 없는 작업이다")
    units = read_plan_units(task_path.read_text(encoding="utf-8"))
    if not units:
        return blank(ok="아니오", state="거부", reason="계획 단위가 없다")
    by_name = {item[0]: item for item in units}
    names = list(selected) if selected else [item[0] for item in units]
    for name in names:
        if name not in by_name:
            return blank(ok="아니오", state="거부", reason=f"계획에 없는 단위다: {name}")
    file_sets = {name: _unit_files(by_name[name][2]) for name in names}
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            for left_file in file_sets[left]:
                for right_file in file_sets[right]:
                    if paths_overlap(left_file, right_file):
                        shown = _plan_path(left_file)
                        return blank(
                            ok="아니오",
                            state="거부",
                            reason=f"건드릴 파일이 겹친다: {shown}",
                        )
    done = set(finished or [])
    for name in names:
        dep = by_name[name][1].strip()
        if not dep or dep == "없음" or dep in done:
            continue
        return blank(
            ok="아니오",
            state="거부",
            reason=f"앞 단위 결과가 입력이다: {dep}",
        )
    if running + len(names) > WORKER_LIMIT:
        return blank(
            ok="아니오",
            state="거부",
            reason=f"동시 워커 상한 {WORKER_LIMIT}을 넘는다",
        )
    return blank(ok="예", state="허용", line=" ".join(names))


def _ready_names(root: Path, work_id: str, finished: list[str] | None) -> list[str] | dict[str, str]:
    folder = root / ".team" / "sessions" / work_id
    task_path = folder / "task.md"
    if not task_path.is_file():
        return blank(ok="아니오", state="거부", reason=f"task.md가 없다: {work_id}")
    log_path = folder / "log.md"
    log_text = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
    if not log_has_go(log_text):
        return blank(ok="아니오", state="거부", reason="go 없는 작업이다")
    units = read_plan_units(task_path.read_text(encoding="utf-8"))
    if not units:
        return blank(ok="아니오", state="거부", reason="계획 단위가 없다")
    done = set(finished or [])
    ready: list[str] = []
    blocked = ""
    for name, dep, _files, _check in units:
        if name in done:
            continue
        dep = dep.strip()
        if dep and dep != "없음" and dep not in done:
            blocked = f"앞 단위 결과가 입력이다: {dep}"
            continue
        ready.append(name)
    if not ready:
        return blank(ok="아니오", state="거부", reason=blocked or "계획 단위가 없다")
    return ready


def work_owning_unit(root: Path, unit: str) -> str | None:
    sessions = root / ".team" / "sessions"
    if not sessions.is_dir():
        return None
    found: list[str] = []
    for folder in sorted(path for path in sessions.iterdir() if path.is_dir()):
        task = folder / "task.md"
        if not task.is_file():
            continue
        try:
            text = task.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for name, _dep, _files, _check in read_plan_units(text):
            if name == unit:
                found.append(folder.name)
                break
    if len(found) > 1:
        return "*"
    if len(found) == 1:
        return found[0]
    return None


def start_work(
    root: Path,
    work_id: str,
    running: int = 0,
    selected: list[str] | None = None,
    finished: list[str] | None = None,
) -> dict[str, str]:
    if selected is None:
        ready = _ready_names(root, work_id, finished)
        if isinstance(ready, dict):
            return ready
        selected = ready
    decision = admit_work(
        root,
        work_id,
        running=running,
        selected=selected,
        finished=finished,
    )
    if decision["ok"] != "예":
        return decision
    handles: list[str] = []
    for name in decision["line"].split():
        record = start(root, name)
        if record["ok"] != "예":
            return record
        handles.append(record["handle"])
    decision["handle"] = ",".join(handles)
    return decision


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
    start_cmd.add_argument("--unit", default="")
    start_cmd.add_argument("--work", default="")
    start_cmd.add_argument("--running", type=int, default=0)
    start_cmd.add_argument("--finished", action="append", default=[])
    admit_cmd = sub.add_parser("admit", help="시작 전 검사를 읽고 허용 또는 거부를 낸다.")
    admit_cmd.add_argument("--work", required=True)
    admit_cmd.add_argument("--running", type=int, default=0)
    admit_cmd.add_argument("--unit", action="append", default=[])
    admit_cmd.add_argument("--finished", action="append", default=[])
    poll_cmd = sub.add_parser("poll", help="핸들의 상태를 읽는다.")
    poll_cmd.add_argument("--handle", required=True)
    collect_cmd = sub.add_parser("collect", help="결과 한 줄을 읽는다.")
    collect_cmd.add_argument("--handle", required=True)
    args = parser.parse_args(argv)
    root = notes_root(args.root or None)
    try:
        if args.command == "start" and args.work:
            chosen = [args.unit] if args.unit else None
            record = start_work(
                root,
                args.work,
                running=args.running,
                selected=chosen,
                finished=args.finished or None,
            )
        elif args.command == "start":
            owner = work_owning_unit(root, args.unit) if args.unit else None
            if owner == "*":
                record = blank(ok="아니오", state="거부", reason="단위가 여러 작업에 있다")
            elif owner:
                record = start_work(
                    root,
                    owner,
                    running=args.running,
                    selected=[args.unit],
                    finished=args.finished or None,
                )
            else:
                record = start(root, args.unit)
        elif args.command == "admit":
            record = admit_work(
                root,
                args.work,
                running=args.running,
                selected=args.unit or None,
                finished=args.finished or None,
            )
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
