#!/usr/bin/env python3
"""검증 세션을 훅이 없는 일회용 복사본에서 띄운다."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

_HOOKS = (
    Path(".claude/settings.json"),
    Path(".codex/hooks.json"),
)


def isolation_available() -> bool:
    if shutil.which("unshare") is None or shutil.which("timeout") is None:
        return False
    if shutil.which("setpriv") is None:
        return False
    probe = subprocess.run(
        ["unshare", "-rmn", "true"],
        text=True,
        capture_output=True,
        check=False,
    )
    return probe.returncode == 0


def _drop_hook_settings(copy: Path) -> None:
    for rel in _HOOKS:
        path = copy / rel
        if path.is_file() and not path.is_symlink():
            path.unlink()


def open_verify_session(root: Path, prompt: str) -> tuple[int, str, str]:
    if "\x00" in prompt or not prompt.strip():
        return 1, "", "검증 입력이 없다"
    if not isolation_available():
        return 1, "", "unshare가 없다"
    from orchestrator import _locked_command, materialize_snapshot, snapshot_tree

    copy = Path(tempfile.mkdtemp(prefix="verify-session-"))
    try:
        problem = materialize_snapshot(root, snapshot_tree(root), copy)
        if problem:
            return 1, "", problem
        _drop_hook_settings(copy)
        (copy / ".verify-input").write_text(prompt, encoding="utf-8")
        code, out, err = _locked_command(
            copy,
            "cat .verify-input; printf '\\n---ENV---\\n'; env",
        )
        wrapper = copy / "isolate"
        if wrapper.is_file():
            wrapper.unlink()
        if code < 0:
            return 1, "", "잠그지 못했다"
        return 0 if code == 0 else code, out or "", err or ""
    finally:
        shutil.rmtree(copy, ignore_errors=True)
