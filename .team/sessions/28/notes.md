# 이슈 28

#27이 main `04ef47c`에 들어간 뒤, 그 main에서 시험 pull request를 열어 세 검사를 확인했다. 실패 시험과 통과 시험 모두 병합하지 않고 닫았다. 브랜치는 지우지 않았다.

## 깨끗한 변경

https://github.com/rimoir/dam/pull/34 head `a343fc963238725c3c0ab3c7eb5086179ddad5b0`. 빈 커밋이라 트리는 main과 같다.

- python test: 통과. 2026-11-26T00:32:33Z 시작, 2026-11-26T00:32:40Z 종료. 7초.
- rulesync regen: 통과. 2026-11-26T00:32:33Z 시작, 2026-11-26T00:32:50Z 종료. 17초.
- gitleaks: 통과. 2026-11-26T00:32:34Z 시작, 2026-11-26T00:32:46Z 종료. 12초.

세 검사 모두 10분 안에 끝났다.

## 테스트 실패와 복구

https://github.com/rimoir/dam/pull/35

깨뜨린 head `e9c261faca3459934858bea36dd616dfbb28f952`. python test만 실패했다. 로그는 `test_new_writes_four_notes_and_one_board_line`에서 `AssertionError: '없는표식' not found`다. rulesync regen과 gitleaks는 통과했다.

되돌린 head `b76ac83df0a9f8c4732d24374a5c28c55055a8ca`. 세 검사 모두 통과했다. python test는 2026-11-26T00:33:48Z 시작, 2026-11-26T00:33:54Z 종료. 6초.

## rulesync

원본만 고친 https://github.com/rimoir/dam/pull/36 head `70a44fdfe6f4dff5c3e90d9e91c04ffbd79c713f`. rulesync regen만 실패했다. `git diff --exit-code -- CLAUDE.md AGENTS.md`가 차이로 종료했다. 나머지 둘은 통과했다.

생성물을 손으로 고친 https://github.com/rimoir/dam/pull/37 head `41d19e4f2b39763b6726b01033e23db0d9d6d686`. rulesync regen만 실패했다. 나머지 둘은 통과했다.

rulesync 43.14.0으로 다시 만든 https://github.com/rimoir/dam/pull/38 head `7626116316466c323468dd4bdc754e9f807d1500`. 세 검사 모두 통과했다.

## 가짜 비밀

AWS 문서의 예시 액세스 키는 gitleaks 8.30.1 기본 규칙의 `EXAMPLE` 허용 목록에 걸려 작업 트리 검사가 통과했다. 그래서 그 문자열은 시험에 쓰지 않았다.

대신 gitleaks v8.30.1 `detect/detect_test.go`의 sidekiq 가짜 값을 넣었다. 실제 비밀이 아니다. https://github.com/rimoir/dam/pull/39 head `6528c3d3e3c8c41fb29b698f98796334425b85a5`. gitleaks만 실패했다. 작업 트리 검사 로그는 `RuleID: sidekiq-secret`, `leaks found: 1`, 파일 `docs/fake-secret-test.txt`다. python test와 rulesync regen은 통과했다.

## 닫음

34, 35, 36, 37, 38, 39는 병합하지 않고 닫았다.
