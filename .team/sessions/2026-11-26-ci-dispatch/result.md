# 결과 2026-11-26-ci-dispatch

## 결과

ci.yml에 `workflow_dispatch`를 더했다. `pull_request`(main), `push`(main), job 본문은 그대로다. README 검사 절에 `gh workflow run ci.yml --ref <branch>`를 적었다.

로컬에서 gitleaks 8.30.1 작업 트리는 no leaks found다. 수동 실행처럼 `before`를 빈 문자열로 두면 추가 커밋 범위는 `..HEAD`이고, 커밋 0개, 종료 코드 0이다. `python3 scripts/team-session_test.py` 46개, `session_context_test.py` 56개, `session_hook_test.py` 3개, `orchestrator_test.py` 28개, `team-session.py check`가 통과했다.

PR https://github.com/rimoir/dam/pull/112 head `69bc47a4f149589918149d782e3bb1faac1a7220`의 pull_request 실행 https://github.com/rimoir/dam/actions/runs/45803173991 에서 python test, rulesync regen, gitleaks가 통과했다.

`gh workflow run ci.yml --ref cursor/ci-workflow-dispatch-6861`는 HTTP 403이다. 응답은 `Resource not accessible by integration`이고, 서버가 요구한 권한은 `actions=write`다. 기본 브랜치에 트리거가 없어 거절됐는지는 이 403 때문에 보지 못했다. 세 job의 workflow_dispatch 실행은 없다.

## 교훈 후보

- 수동 실행에는 `github.event.before`가 없다. gitleaks 추가 커밋 범위가 `..HEAD`가 되어 커밋 0개를 보고 통과한다. job은 깨지지 않고, 작업 트리 검사(`--no-git`)는 돈다.
