# 전체 설계

랩 설계 초안: '도구를 갈아끼우는 멀티 에이전트 하네스: 오케스트레이터 설계와 동작 흐름' https://cursor.com/canvas/store-ed6c6a42-9907-4aa3-b747-9b4cc62728b5/823ad43d-e8f0-477e-bbc0-2ad3db2ad38d .

아래 M4 절은 랩 초안 'dam M4 스펙 초안: 파일 레이어 읽기 계약과 강제 장치' https://cursor.com/canvas/store-ed6c6a42-9907-4aa3-b747-9b4cc62728b5/117296ee-29d6-4c10-9a05-5bb81c8ebfcc 의 본문이다. 초안을 에픽으로 다시 쪼개지 않는다. HR P가 훅 도입을 승인했다.

## issue-tracker

이슈 번호로 `python3 scripts/team-session.py new <번호>`를 실행하면 issue-tracker 어댑터가 제목, 이슈 링크, 완료 기준 목록을 읽어 `.team/sessions/<번호>/task.md`의 목표와 완료 기준에 넣는다. 날짜형 작업ID는 이슈를 읽지 않는다. 이미 있는 노트는 덮어쓰지 않는다. 읽기에 실패하면 이유를 알리고 노트를 만들지 않는다.

기본 구현은 github다. 호출은 사람이 이미 로그인한 gh CLI의 읽기다. 선택 결과는 `.team/adapters.lock`의 `issue-tracker` 키이고, 파일이 없으면 github다. 그 파일에 토큰을 적지 않는다. GitHub 명령은 `scripts/issue_tracker.py`에만 둔다. 쓰는 동작의 진입점도 그 파일이고, 사람이 그 동작을 직접 명령했을 때, 또는 ADR 0007 조건 안의 워커가 호출한다. 이 저장소의 작업 시작 명령은 읽기만 한다.

결정은 `docs/adr/0004-m3-scope.md`와 `docs/adr/0005-adapter-choice.md`다. CI와 머지 규칙은 `docs/adr/0003-ci-and-merge.md`다. 워커의 쓰기와 머지는 `docs/adr/0007-worker-github-write-and-merge.md`다.

## 세션 시작

`python3 scripts/team-session.py start-context`는 `.team/board.md`의 열린 줄과, 브랜치 이름이 이슈 번호로 끝날 때 그 작업 하나의 `state.md`만 낸다. 번호가 없으면 열린 줄만 낸다. 상태 `완료`와 `닫힘`은 열린 줄이 아니다. 도구를 바꿀 때는 `start-context --switch`로 그 로그의 마지막 5줄만 더하고, 로그 전체는 넣지 않는다. 시작 주입 4,000자 또는 상태 파일 2,000자를 넘으면 본문 대신 줄이라는 한 줄만 낸다. 이 값은 측정 전 임시 상한이다. `summary`는 state.md만 내는 호환 명령으로 남는다.

`python3 scripts/team-session.py rotate <작업ID>`는 log.md가 200줄을 넘으면 앞부분을 `.team/sessions/<작업ID>/log/001.md`로 옮기고, log.md에는 최근 줄과 `이전: log/001.md`만 남긴다. 옮긴 내용은 바꾸지 않는다. 다시 넘으면 `002.md`다. `python3 scripts/team-session.py check`는 상태 파일 2,000자, 시작 주입 4,000자, 로그 200줄을 넘기면 실패한다. `notes.md`만 있는 폴더는 보지 않는다. 로그 200줄도 측정 전 임시 상한이다.

## M4 파일 레이어

시작할 때 넣는 것은 board.md의 열린 줄과 그 작업의 state.md 하나다. 도구를 바꿀 때만 log.md 마지막 5줄을 더한다. log.md 전체, result.md, 닫힌 작업은 넣지 않는다.

파일 역할은 그대로다. task.md는 목표와 완료 기준과 계획이고 시작 때 읽지 않는다. state.md는 지금 상태, 결정, 다음 할 일을 덮어 쓰며 시작 때 열린 작업 하나만 읽는다. log.md는 한 줄씩 추가하고, 넘치면 log/로 옮긴다. result.md는 끝날 때 결과와 교훈 후보다. board.md는 작업당 한 줄이고 열린 줄만 읽는다.

읽기 계약: 새 세션, /compact, resume, clear는 같은 start-context다. 장치 매처는 `startup|resume|clear|compact`다. 열린 작업은 브랜치 끝 번호다. 번호가 없으면 열린 줄만 낸다. 상한을 넘으면 본문 대신 줄이라는 한 줄만 낸다.

줄이기: state.md는 세 칸만 덮어 쓴다. log.md 앞부분은 지우지 않고 log/로 옮긴다. 요약은 state.md, docs/adr, result.md, kb/ 중 내용에 맞는 곳에 두고 새 요약 파일은 만들지 않는다. 기존 notes.md 폴더는 옮기지 않는다.

강제: Claude Code `.claude/settings.json`과 Codex `.codex/hooks.json`의 SessionStart가 같은 명령을 임시 10초 제한으로 실행한다. 실패해도 세션 시작을 막지 않는다. PreCompact는 공통 장치로 쓰지 않는다. Codex는 훅 파일이 바뀔 때마다 README의 신뢰 검토를 거친다. 결정은 `docs/adr/0006-session-start-hooks.md`다.

사용성 예산의 임시값은 시작 주입 4,000자, state.md 2,000자, log.md 200줄, 훅 10초다. 측정 뒤 고친다. 출처로 확인된 도구 상한은 Claude Code 훅 주입 10,000자와 Codex 훅 약 2,500토큰, 기본 타임아웃 600초다. 이 임시값은 그 안에서 짧게 잡은 추정이다.

출처: https://code.claude.com/docs/en/hooks , https://developers.openai.com/codex/hooks . 이 환경에는 Codex CLI가 없어 사용자 PC의 0.172.0 여부는 확인하지 못했다.
