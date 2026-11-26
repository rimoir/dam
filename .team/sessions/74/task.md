# 작업 74

## 목표

[M5b] 단위마다 노트 폴더, 브랜치, 격리된 작업 폴더를 따로 만들고 읽기 계약대로만 시작하게 한다

https://github.com/rimoir/dam/issues/74

## 완료 기준

- 단위마다 노트 폴더, 브랜치(끝이 이슈 번호), 격리된 작업 폴더가 하나씩 따로 생기고, 워커는 그 작업의 task.md와 상태 파일만 읽고 시작하며 다른 작업 폴더의 파일을 덮어쓰지 않는다 (https://github.com/rimoir/dam/issues/57)
- 작업 폴더 생성 시간이 작업 노트에 기록된다 (https://github.com/rimoir/dam/issues/57)

## 계획

- 실패 검사 | 없음 | scripts/orchestrator_test.py | python3 scripts/orchestrator_test.py
- 준비 | 실패 검사 | scripts/orchestrator.py | python3 scripts/orchestrator_test.py
