# 작업 2026-11-26-ci-dispatch

## 목표

CI 워크플로를 손으로 다시 돌릴 수 있게 한다

## 완료 기준

- `.github/workflows/ci.yml`에 `workflow_dispatch`가 있고, 기존 `pull_request`(main)와 `push`(main)와 job 본문은 그대로다
- README 검사 절에 `gh workflow run ci.yml --ref <branch>` 한 줄이 있다
- pull request의 검사 세 개(python test, rulesync regen, gitleaks)가 통과한다

## 계획

- ci.yml에 workflow_dispatch를 더하고 README에 재실행 명령 한 줄을 적는다
