# 전체 설계

랩 설계 초안: '도구를 갈아끼우는 멀티 에이전트 하네스: 오케스트레이터 설계와 동작 흐름' https://cursor.com/canvas/store-ed6c6a42-9907-4aa3-b747-9b4cc62728b5/823ad43d-e8f0-477e-bbc0-2ad3db2ad38d . 본문 옮기기는 HR P 확인 뒤.

## issue-tracker

이슈 번호로 `python3 scripts/team-session.py new <번호>`를 실행하면 issue-tracker 어댑터가 제목, 이슈 링크, 완료 기준 목록을 읽어 `.team/sessions/<번호>/task.md`의 목표와 완료 기준에 넣는다. 날짜형 작업ID는 이슈를 읽지 않는다. 이미 있는 노트는 덮어쓰지 않는다. 읽기에 실패하면 이유를 알리고 노트를 만들지 않는다.

기본 구현은 github다. 호출은 사람이 이미 로그인한 gh CLI의 읽기다. 선택 결과는 `.team/adapters.lock`의 `issue-tracker` 키이고, 파일이 없으면 github다. 그 파일에 토큰을 적지 않는다. GitHub 명령은 `scripts/issue_tracker.py`에만 둔다. 쓰는 동작의 진입점도 그 파일이고, 사람이 그 동작을 직접 명령했을 때만 호출한다. 이 저장소의 작업 시작 명령은 읽기만 한다.

결정은 `docs/adr/0004-m3-scope.md`와 `docs/adr/0005-adapter-choice.md`다. CI와 머지 규칙은 `docs/adr/0003-ci-and-merge.md`다.
