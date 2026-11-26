# 결과 2026-11-26-ci-dispatch

## 결과

ci.yml에 `workflow_dispatch`를 더했다. README 검사 절에 `gh workflow run ci.yml --ref <branch>`를 적었다.

수동 실행의 gitleaks 추가 커밋 검사는 `..HEAD`라 커밋 0개, 종료 코드 0이었다. 이력에만 남은 sidekiq 시험 값으로 다시 보니 고친 뒤에는 종료 코드 1이다. 브랜치이면 범위는 `origin/main..HEAD`이고, HEAD가 `origin/main`과 같으면 범위는 `HEAD`다. `pull_request`와 `push`는 고치기 전과 같이 종료 코드 1이고, before가 0이면 범위 `-1`, 종료 코드 0이다. checkout `fetch-depth: 0`은 브랜치 전부를 `origin/*`로 가져와서 `origin/main`이 있다.

`gh workflow run`은 HTTP 403이다. 응답은 `Resource not accessible by integration`이고, 서버가 요구한 권한은 `actions=write`다. 세 job의 workflow_dispatch 실행은 없다.

로그 도구 칸은 세션 72부터 76까지와 같이 `Codex`다.

## 교훈 후보

- 수동 실행에는 `github.event.before`가 없다. 빈 범위를 그대로 두면 추가 커밋 검사가 커밋 0개로 통과한다.
