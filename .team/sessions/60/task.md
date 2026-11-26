# 작업 60

## 목표

[M5a] 워커의 GitHub 쓰기와 머지 범위, 두 보안 결정을 ADR 0007로 남기고 충돌하는 줄을 대체한다

https://github.com/rimoir/dam/issues/60

## 완료 기준

- 워커가 계획 go 뒤 자기 브랜치에 push하고, PR을 열고, 조건이 맞으면 머지하는 범위와 두 보안 결정(워커에게 처음부터 push, PR, 머지 도구를 준다, 다른 세션의 검증 코멘트는 헤드 SHA, 확인 방법, 증거가 있으면 검토 기록으로 친다)이 규칙 원본과 ADR에 기록된다 (https://github.com/rimoir/dam/issues/55)

## 계획

- 실패 검사로 ADR 0007과 대체 문장이 있는지 본다.
- `docs/adr/0007-worker-github-write-and-merge.md`를 쓰고, 규칙 원본, ADR 0003, ADR 0005, `docs/spec.md`, README의 충돌 줄을 대체한다.
- `docs/conventions.md` 역할 표는 그대로 두고 ADR에 한 문장으로 구분한다.
- rulesync 43.14.0으로 CLAUDE.md와 AGENTS.md를 다시 만든다.
- PR만 열고 머지하지 않는다. HR P 직접 확인을 기다린다.
