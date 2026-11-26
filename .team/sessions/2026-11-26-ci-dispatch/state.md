모드: 작은 수정

# 상태 2026-11-26-ci-dispatch

## 지금 상태

ci.yml에 workflow_dispatch만 더했다. pull_request, push, job 본문은 그대로다. README 검사 절에 재실행 명령을 적었다. 로컬 테스트 4개 파일과 gitleaks 작업 트리 검사는 통과했다.

## 결정

- 트리거만 더한다. job 본문은 고치지 않는다. 수동 실행의 추가 커밋 검사는 범위 `..HEAD`로 커밋 0개이고 종료 코드 0이다. 작업 트리 검사는 그대로 돈다.
- README 검사 절에 재실행 명령 한 줄을 적는다.

## 다음 할 일

PR을 열고 검사 세 개와 workflow_dispatch 접수를 확인한다.
