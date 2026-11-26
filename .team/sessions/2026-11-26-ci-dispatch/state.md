모드: 작은 수정

# 상태 2026-11-26-ci-dispatch

## 지금 상태

수동 실행의 gitleaks 추가 커밋 범위는 HEAD가 origin/main과 같으면 HEAD, 아니면 origin/main..HEAD다. pull_request와 push 분기는 그대로다. 로그 도구 칸은 Cursor다.

## 결정

- workflow_dispatch만 범위를 바꾼다. checkout fetch-depth 0이 origin/main을 가져온다.
- 이 세션의 로그 도구는 Cursor다. 규칙과 log.md 머리글은 Claude Code 또는 Codex만 적는다. 규칙 변경은 별도다.

## 다음 할 일

이 커밋의 검사 세 개를 확인하고 열린 PR에서 멈춘다. 머지하지 않는다.
