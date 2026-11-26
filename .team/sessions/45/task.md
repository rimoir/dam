# 작업 45

## 목표

[M4] SessionStart 훅과 훅 도입 결정 기록을 넣는다

https://github.com/rimoir/dam/issues/45

## 완료 기준

- 두 도구에 SessionStart 훅(compact 포함)을 쓰는 결정이 결정 기록(ADR)에 남아 있고, Codex에서 훅이 바뀔 때 필요한 신뢰 검토 절차가 README에 적혀 있다 (https://github.com/rimoir/dam/issues/42)

## 계획

- 훅 설정 실패 검사를 먼저 둔다
- 저장소 안 두 파일만 두고 실패해도 종료 0이 되게 한다
- ADR 0006과 README 신뢰 검토, 규칙 재생성을 같은 PR에 둔다
