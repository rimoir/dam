# 작업 81

## 목표

[M5b] 검증 결과를 result.md와 도구·모델이 적힌 log.md 한 줄에 남긴다

https://github.com/rimoir/dam/issues/81

## 완료 기준

- 검증 결과가 그 작업의 result.md와, 검증한 도구와 모델이 적힌 log.md 한 줄에 남는다 (https://github.com/rimoir/dam/issues/58)

## 계획

- 실패 검사 | 없음 | scripts/session_context_test.py | python3 scripts/session_context_test.py VerifyRecordTest
- 구현 | 실패 검사 | scripts/session_context.py scripts/team-session.py docs/spec.md docs/adr/0012-verification-record.md | python3 scripts/session_context_test.py
