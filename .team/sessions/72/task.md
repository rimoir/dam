# 작업 72

## 목표

[M5b] 워커 시작과 수거 명령을 어댑터 한 곳에 두고 가짜 어댑터로 바꿔 끼워도 같은 형식의 결과가 나오게 한다

https://github.com/rimoir/dam/issues/72

## 완료 기준

- 워커 시작과 수거 명령이 orchestrator 어댑터 한 곳에만 있고(선택 결과는 `.team/adapters.lock`, 기본 native) 가짜 어댑터로 바꿔 끼워도 같은 형식의 결과가 나온다 (https://github.com/rimoir/dam/issues/57)

## 계획

- 실패 검사 | 없음 | scripts/orchestrator_test.py | python3 scripts/orchestrator_test.py
- 어댑터 | 실패 검사 | scripts/orchestrator.py docs/adr/0005-adapter-choice.md .github/workflows/ci.yml | python3 scripts/orchestrator_test.py
