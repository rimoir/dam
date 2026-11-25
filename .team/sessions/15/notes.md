# 이슈 15

log.md 한 줄에 도구 칸을 더했다. 도구는 Claude Code 또는 Codex다. 시각과 종류(시작, go, 종료, push, 재개)는 그대로다. Claude Code와 Codex가 같은 형식을 쓰도록 규칙 원본을 고치고 rulesync 43.14.0으로 다시 만들었다.

README Codex 절은 세션을 열 때 AGENTS.md를 읽고, `.codex/hooks.json`은 두지 않는다고 적는다. Codex CLI 0.172.0의 `codex debug prompt-input`이 그 규칙을 프롬프트에 넣었다. 기록은 `codex-prompt.txt`.

실패하던 검사는 `tdd-fail.txt`. 통과는 `tdd-pass.txt`.
