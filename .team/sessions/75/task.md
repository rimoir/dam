# 작업 75

## 목표

[M5b] 워커 끝남을 성공, 문제, 실패, 미완 넷으로 판정하고 멈춤 의심을 알리며 result.md 결과 한 줄만 거둔다

https://github.com/rimoir/dam/issues/75

## 완료 기준

- 워커 끝남이 성공, 문제(ISSUES 또는 BLOCKED), 실패, 미완 넷으로 갈리고(종료 0인데 결과 칸이 비면 미완), 가짜 워커로 네 경우를 테스트가 확인한다 (https://github.com/rimoir/dam/issues/57)
- 로그 시각이 오래된 살아 있는 워커는 멈춤 의심으로 사람에게 알린다 (https://github.com/rimoir/dam/issues/57)
- 메인 세션이 읽는 것은 각 result.md 결과 칸 한 줄뿐이다 (https://github.com/rimoir/dam/issues/57)

## 계획

- 실패 검사 | 없음 | scripts/orchestrator_test.py | python3 scripts/orchestrator_test.py
- 판정 | 실패 검사 | scripts/orchestrator.py | python3 scripts/orchestrator_test.py
