# 작업 73

## 목표

[M5b] go 확인과 겹침, 순차 의존, 동시 워커 상한 검사를 만들어 시작을 거부하고 이유를 낸다

https://github.com/rimoir/dam/issues/73

## 완료 기준

- 계획에 사람의 go가 log.md에 없는 작업에는 워커가 뜨지 않고 이유가 나온다 (https://github.com/rimoir/dam/issues/57)
- 건드릴 파일이 겹치거나 앞 단위 결과가 입력인 단위는 병렬 시작이 거부되고 순차로 가며, 동시 워커가 상한(기본 3, 임시)을 넘으면 시작이 거부되고 이유가 나온다 (https://github.com/rimoir/dam/issues/57)

## 계획

- 실패 검사 | 없음 | scripts/orchestrator_test.py | python3 scripts/orchestrator_test.py
- 검사 | 실패 검사 | scripts/orchestrator.py scripts/session_context.py | python3 scripts/orchestrator_test.py
