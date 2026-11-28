# 작업 79

## 목표

[M5b] 검증 세션이 시작 때 받는 입력을 완료 기준, BASE와 HEAD 커밋 SHA, 검사 명령으로 제한한다

https://github.com/rimoir/dam/issues/79

## 완료 기준

- 검증 세션이 만든 세션과 다른 세션이고 시작 때 받는 입력이 완료 기준, BASE와 HEAD 커밋 SHA, 검사 명령으로 제한되며, 작성자의 결정 메모가 검증 세션의 시작 출력에 들어가지 않는 것을 테스트가 확인한다 (https://github.com/rimoir/dam/issues/58)

## 계획

- 문서 | 없음 | docs/spec.md docs/adr/0010-verification-session-input.md | python3 scripts/team-session.py check
- 실패 검사 | 문서 | scripts/session_context_test.py scripts/session_hook_test.py | python3 scripts/session_context_test.py
- 구현 | 실패 검사 | scripts/session_context.py scripts/team-session.py | python3 scripts/session_context_test.py
