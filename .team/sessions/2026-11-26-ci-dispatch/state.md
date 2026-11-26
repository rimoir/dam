모드: 작은 수정

# 상태 2026-11-26-ci-dispatch

## 지금 상태

ci.yml에 workflow_dispatch만 더했다. pull_request, push, job 본문은 그대로다. PR https://github.com/rimoir/dam/pull/112 head `69bc47a`에서 python test, rulesync regen, gitleaks가 통과했다. workflow_dispatch API는 403이다.

## 결정

- 트리거만 더한다. job 본문은 고치지 않는다. 수동 실행의 추가 커밋 검사는 범위 `..HEAD`로 커밋 0개이고 종료 코드 0이다. 작업 트리 검사는 그대로 돈다.
- README 검사 절에 재실행 명령 한 줄을 적는다.

## 다음 할 일

열린 PR에서 멈춘다. 머지하지 않는다.
