# 작업 84

## 목표

[M5b] 승인이 있는 계획의 워커 결과만 그 작업 브랜치로 push하고 PR을 열어 log.md에 URL을 남긴다

https://github.com/rimoir/dam/issues/84

## 완료 기준

- 승인이 있는 계획의 워커 결과만 push되고 push 대상은 그 작업의 브랜치뿐이며, main이나 다른 브랜치로의 push와 force push는 거부된다 (https://github.com/rimoir/dam/issues/59)
- PR 본문에 이슈 링크가 있고 log.md에 PR URL이 도구 칸과 함께 한 줄로 남으며, PR 열기에 실패하면 log.md는 바뀌지 않는다 (https://github.com/rimoir/dam/issues/59)

## 계획

- 실패 검사 | 없음 | scripts/team-session_test.py | python3 scripts/team-session_test.py WorkerPushTest
- 구현 | 실패 검사 | scripts/session_context.py scripts/team-session.py docs/spec.md docs/adr/0007-worker-github-write-and-merge.md | python3 scripts/team-session_test.py WorkerPushTest
