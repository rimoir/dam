# 작업 82

## 목표

[M5b] 검증 결과를 PR 검토 코멘트로 올리고 헤드가 바뀌면 그 검증을 무효로 한다

https://github.com/rimoir/dam/issues/82

## 완료 기준

- PR에 헤드 SHA와 확인 방법과 증거를 적은 내용 있는 검토 코멘트로 올라가고, 이 코멘트는 머지 조건의 검토 기록으로 인정된다 (https://github.com/rimoir/dam/issues/58)
- 검증 뒤 PR 헤드가 바뀌면 그 검증은 무효이고 다시 검증해야 한다 (https://github.com/rimoir/dam/issues/58)
- 검증 코멘트에 검증한 세션 id와 헤드 SHA가 없으면 검토 기록이 아니다 (https://github.com/rimoir/dam/issues/58)

## 계획

- 실패 검사 | 없음 | scripts/session_context_test.py | python3 scripts/session_context_test.py VerifyCommentTest
- 구현 | 실패 검사 | scripts/verify_comment.py scripts/team-session.py scripts/issue_tracker.py docs/spec.md docs/adr/0013-verification-comment.md docs/adr/0007-worker-github-write-and-merge.md | python3 scripts/session_context_test.py
