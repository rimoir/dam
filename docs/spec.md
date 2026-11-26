# 전체 설계

랩 설계 초안: '도구를 갈아끼우는 멀티 에이전트 하네스: 오케스트레이터 설계와 동작 흐름' https://cursor.com/canvas/store-ed6c6a42-9907-4aa3-b747-9b4cc62728b5/823ad43d-e8f0-477e-bbc0-2ad3db2ad38d . 본문 옮기기는 HR P 확인 뒤.

## issue-tracker

이슈 번호로 `python3 scripts/team-session.py new <번호>`를 실행하면 issue-tracker 어댑터가 제목, 이슈 링크, 완료 기준 목록을 읽어 `.team/sessions/<번호>/task.md`의 목표와 완료 기준에 넣는다. 날짜형 작업ID는 이슈를 읽지 않는다. 이미 있는 노트는 덮어쓰지 않는다. 읽기에 실패하면 이유를 알리고 노트를 만들지 않는다.

기본 구현은 github다. 호출은 사람이 이미 로그인한 gh CLI의 읽기다. 선택 결과는 `.team/adapters.lock`의 `issue-tracker` 키이고, 파일이 없으면 github다. 그 파일에 토큰을 적지 않는다. GitHub 명령은 `scripts/issue_tracker.py`에만 둔다. 쓰는 동작의 진입점도 그 파일이고, 사람이 그 동작을 직접 명령했을 때만 호출한다. 이 저장소의 작업 시작 명령은 읽기만 한다.

결정은 `docs/adr/0004-m3-scope.md`와 `docs/adr/0005-adapter-choice.md`다. CI와 머지 규칙은 `docs/adr/0003-ci-and-merge.md`다.

## 세션 시작

`python3 scripts/team-session.py start-context`는 `.team/board.md`의 열린 줄과, 브랜치 이름이 이슈 번호로 끝날 때 그 작업 하나의 `state.md`만 낸다. 번호가 없으면 열린 줄만 낸다. 상태 `완료`와 `닫힘`은 열린 줄이 아니다. 도구를 바꿀 때는 `start-context --switch`로 그 로그의 마지막 5줄만 더하고, 로그 전체는 넣지 않는다. 시작 주입 4,000자 또는 상태 파일 2,000자를 넘으면 본문 대신 줄이라는 한 줄만 낸다. 이 값은 측정 전 임시 상한이다. `summary`는 state.md만 내는 호환 명령으로 남는다.

`python3 scripts/team-session.py rotate <작업ID>`는 log.md가 200줄을 넘으면 앞부분을 `.team/sessions/<작업ID>/log/001.md`로 옮기고, log.md에는 최근 줄과 `이전: log/001.md`만 남긴다. 옮긴 내용은 바꾸지 않는다. 다시 넘으면 `002.md`다. `python3 scripts/team-session.py check`는 상태 파일 2,000자, 시작 주입 4,000자, 로그 200줄을 넘기면 실패한다. `notes.md`만 있는 폴더는 보지 않는다. 로그 200줄도 측정 전 임시 상한이다.
