# 작업 30

## 목표

[M3b] issue-tracker 어댑터와 이슈로 작업 시작을 넣는다

https://github.com/rimoir/dam/issues/30

## 완료 기준

- 이슈 #N으로 작업을 시작하면 task.md에 이슈 제목, 이슈 링크, 완료 기준 목록이 들어가고, Claude Code와 Codex가 같은 결과이며, 같은 이슈로 다시 시작해도 이미 쓴 노트를 덮어쓰지 않는다 (https://github.com/rimoir/dam/issues/4)
- GitHub 전용 지식은 issue-tracker 어댑터 한 곳에만 있고, 시험용 가짜 어댑터로 바꿔 끼워도 작업 시작이 같은 형식의 결과로 나온다 (https://github.com/rimoir/dam/issues/4)
- GitHub에 닿지 못하거나 로그인이 안 된 상태에서 작업 시작을 하면 이유를 알려 주는 오류가 나오고, 반쯤 만들어진 노트가 남지 않는다 (https://github.com/rimoir/dam/issues/4)
- 작업 시작은 GitHub에 아무것도 쓰지 않는다. 토큰이나 비밀번호가 노트, 저장소, 로그에 남지 않고, 사람이 이미 로그인한 gh CLI 인증만 쓴다 (https://github.com/rimoir/dam/issues/4)

## 계획

- 실패하는 검사를 먼저 둔다. 사용자가 보는 것은 task.md 칸, 종료 코드, 노트 유무, gh에 넘어가는 인자다.
- issue-tracker 어댑터를 `scripts/issue_tracker.py` 한 곳에 두고, 이슈 번호로 `new`를 하면 제목과 링크를 목표에, 완료 기준 목록을 완료 기준 칸에 넣는다.
- 날짜형 작업ID는 이슈를 읽지 않는다. 이미 있는 노트는 덮어쓰지 않는다. 읽기 실패면 노트를 만들지 않는다.
- ADR 0004와 0005, `docs/spec.md`, 규칙 원본을 같은 변경에 넣는다. PR 본문 링크와 현황판 갱신은 넣지 않는다.
