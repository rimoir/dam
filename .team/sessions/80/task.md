# 작업 80

## 목표

[M5b] 검증은 읽기 전용이고 결과는 PASS, ISSUES, BLOCKED로 시작하며 증거가 없으면 통과로 치지 않는다

https://github.com/rimoir/dam/issues/80

## 완료 기준

- 검증은 읽기 전용이고 검증 중 코드 파일이 바뀌면 그 검증은 실패로 처리된다 (https://github.com/rimoir/dam/issues/58)
- 검증 결과는 PASS, ISSUES, BLOCKED 중 하나로 시작하고, 헤드 SHA와 실행한 확인 방법과 증거 요약이 없으면 통과로 치지 않는다 (https://github.com/rimoir/dam/issues/58)

## 계획

- 문서 | 없음 | docs/spec.md docs/adr/0011-verification-verdict.md | python3 scripts/team-session.py check
- 실패 검사 | 문서 | scripts/session_context_test.py | python3 scripts/session_context_test.py
- 구현 | 실패 검사 | scripts/verify_report.py scripts/team-session.py | python3 scripts/session_context_test.py
