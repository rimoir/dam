# 작업 78

## 목표

[M5b] native 어댑터로 실제 워커를 띄우고 시작 시간을 작업 노트에 기록한다

https://github.com/rimoir/dam/issues/78

## 완료 기준

- 워커에게 처음부터 push, PR, 머지 도구가 주어진다 (https://github.com/rimoir/dam/issues/57)
- 워커 시작 시간 중간값(명령부터 첫 이벤트까지, 두 도구 각 5회)이 작업 노트에 기록된다 (https://github.com/rimoir/dam/issues/57)

## 계획

- 멈춤 계획 | 없음 | docs/milestones/m5b-native-start-stop.md | python3 scripts/orchestrator_test.py
- Claude 시작 | 멈춤 계획 | scripts/orchestrator.py, scripts/orchestrator_test.py, docs/milestones/m5b-native-start-stop.md | python3 scripts/orchestrator_test.py
- 시작 경계 | Claude 시작 | scripts/orchestrator.py, scripts/orchestrator_test.py, docs/milestones/m5b-native-start-stop.md | python3 scripts/orchestrator_test.py
