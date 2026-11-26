# 작업 76

## 목표

[M5b] 현황판에 병렬 작업 줄을 보여 주고 메인 세션을 닫아도 현황판과 상태 파일만으로 이어받게 한다

https://github.com/rimoir/dam/issues/76

## 완료 기준

- 현황판이 병렬 작업마다 한 줄에 상태, 담당 세션, 막힘 이유, 마지막 로그 시각을 보여 준다 (https://github.com/rimoir/dam/issues/57)
- 메인 세션을 닫고 새로 열어도 현황판과 각 상태 파일만으로 이어받는다 (https://github.com/rimoir/dam/issues/57)

## 계획

- 실패 검사 | 없음 | scripts/orchestrator_test.py scripts/team-session_test.py | python3 scripts/team-session_test.py
- 현황판 | 실패 검사 | scripts/orchestrator.py scripts/team-session.py | python3 scripts/orchestrator_test.py
