# 작업 85

## 목표

[M5b] 머지 조건 네 가지를 모두 확인해 squash 머지하고 하나라도 모자라면 이유와 함께 거부한다

https://github.com/rimoir/dam/issues/85

## 완료 기준

- 머지는 검사 세 개가 PR 헤드에서 성공했고, 같은 헤드에 만든 세션과 다른 세션의 검증 코멘트(헤드 SHA, 확인 방법, 증거)가 있고, PR을 연 지 1분이 지났을 때만 일어난다. 조건 하나가 모자랄 때마다 머지 시도가 거부되고 이유가 나온다 (https://github.com/rimoir/dam/issues/59)
- 머지는 되돌릴 수 있게 revert 가능한 방식(기존 squash)으로 한다 (https://github.com/rimoir/dam/issues/59)
- 머지 명령은 검증 세션이 작성 세션과 같거나, 세션 id가 없거나, 검증한 헤드가 PR 헤드와 다르면 거부하고, 머지는 그 명령으로만 한다 (https://github.com/rimoir/dam/issues/59)

## 계획

- 실패 검사 | 없음 | scripts/team-session_test.py | python3 scripts/team-session_test.py WorkerMergeTest WorkerSessionTest
- 구현 | 실패 검사 | scripts/verify_comment.py scripts/worker_merge.py scripts/issue_tracker.py scripts/team-session.py docs/spec.md docs/adr/0007-worker-github-write-and-merge.md | python3 -m pytest scripts
