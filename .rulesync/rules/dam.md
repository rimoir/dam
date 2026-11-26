---
root: true
targets: ["claudecode", "codexcli"]
description: "dam 작업 노트와 피드백"
globs: ["**/*"]
---

세션을 시작하거나 compact 뒤에는 현황판의 열린 줄과 열린 작업 하나의 state.md만 읽어라

이 파일은 rulesync 생성물이다. 손으로 고치지 말고 .rulesync/ 원본을 고친 뒤 다시 생성한다.

# 작업 노트와 피드백

- 새 작업이 열리면 먼저 목표와 빠진 점을 질문한다. 바로 구현하지 않는다.
- 합의된 목표, 완료 기준, 제약은 .team/sessions/<이슈번호>/task.md에 쌓는다. 프롬프트를 세션 대화에만 두지 않는다.
- writing-plans의 계획 경로는 .team/sessions/<이슈번호>/task.md 다. superpowers 파일은 고치지 않는다.
- 피드백으로 정한 결정은 같은 폴더의 state.md에 적는다.
- 질문이 3~4번을 넘거나 방향이 바뀌면, state.md를 갱신한 뒤 세션을 닫는다(/clear 또는 새 세션). 다음 세션의 첫 일은 task.md와 state.md를 읽고 이어가는 것이다.
- 계획과 구현은 세션을 나눈다. 계획은 사람의 go에서 멈춘다.
- 새 작업을 시작하면 폴더를 손으로 만들지 말고 `python3 scripts/team-session.py new <작업ID>`를 실행한다. 작업ID는 GitHub 이슈 번호다. 이슈가 없으면 `YYYY-MM-DD-짧은이름`이다.
- 생성기가 task.md, state.md, log.md, result.md와 board.md 한 줄을 만든다. 목표, 완료 기준, 계획은 task.md에 채운다.
- 작업ID가 이슈 번호이면 같은 생성기가 issue-tracker 어댑터로 이슈를 읽는다. 제목과 이슈 링크는 task.md 목표에, 완료 기준 목록은 완료 기준 칸에 넣는다. 날짜형 작업ID는 이슈를 읽지 않는다. 이미 있는 노트는 덮어쓰지 않는다. 이슈를 읽지 못하면 이유를 알리고 노트를 만들지 않는다.
- GitHub 명령은 issue-tracker 어댑터 한 곳에만 둔다. 기본 선택은 github이고, 사람이 이미 로그인한 gh CLI만 쓴다. 새 토큰은 만들지 않는다. GitHub에 쓰는 동작은 사람이 그 동작을 직접 명령했을 때만 그 어댑터를 통한다.
- PR은 자동으로 열지 않는다. 사람이 `python3 scripts/team-session.py pull <이슈번호> --title <제목> --tool Codex`를 실행했을 때만 연다. 본문에 이슈 링크가 들어가고, log.md에 PR URL이 도구 칸과 함께 한 줄로 남는다. 도구는 `Claude Code` 또는 `Codex`다.
- 현황판 갱신은 `python3 scripts/team-session.py board`이고 읽기만 한다. 상태, 담당, 막힘 칸은 유지한다. 열린 PR은 검토 중과 검사 결과, 머지되면 완료, 이슈가 닫히면 닫힘이다. 실패하면 기존 줄을 바꾸지 않는다.
- 계획을 task.md에 쓴 뒤 사람의 go를 기다린다. go 전에는 `git status`로 코드 파일이 바뀌지 않았는지 확인한다. 노트와 `.team/board.md`는 계획 단계에서 바뀌어도 된다.
- go, 시작, 종료, push, 재개는 log.md에 `YYYY-MM-DDTHH:MM:SSZ 도구 종류 내용` 한 줄로 남긴다. 도구는 `Claude Code` 또는 `Codex`다. Claude Code와 Codex가 같은 형식을 쓴다.
- 작업 단위가 끝날 때마다 state.md의 지금 상태, 결정, 다음 할 일을 갱신한다.
- 작업이 끝나면 result.md의 결과와 교훈 후보를 채운다.
- 완료 조건을 가리킬 때 번호나 별칭을 쓰지 않는다. 조건 내용을 짧게 쓰고 에픽 링크를 붙인다. 예: /compact 뒤 첫 답에서 재개 한 줄 (https://github.com/rimoir/dam/issues/2).
- 세션을 시작하거나 compact 뒤에는 `.team/board.md`와 열린 작업의 state.md만 읽는다. log.md 전체를 시작 컨텍스트에 넣지 않는다.
- 첫 답변은 열린 작업 이름과 state.md의 다음 할 일을 말한다.
- 재개도 위와 같은 log.md 한 줄이다. 도구 칸에 `Claude Code` 또는 `Codex`를 적는다.
- 세션 시작 출력은 `python3 scripts/team-session.py start-context`다. 브랜치 끝 이슈 번호의 작업 하나만 고르고, 번호가 없으면 현황판의 열린 줄만 낸다. 도구를 바꿀 때는 `start-context --switch`로 그 로그의 마지막 5줄만 더한다. 로그 전체는 넣지 않는다. 시작 주입이 4,000자를 넘거나 상태 파일이 2,000자를 넘으면 본문 대신 줄이라는 한 줄만 낸다. `summary <작업ID>`는 state.md만 내는 호환 명령으로 남고, 10,000자를 넘으면 실패한다 (https://github.com/rimoir/dam/issues/2).
- Codex에서 새 작업을 시작할 때도 `python3 scripts/team-session.py new <작업ID>`를 쓴다. Codex 전용 생성기는 없다.
- Codex도 계획을 task.md에 쓴 뒤 사람의 go를 기다린다. go 전에는 `git status`로 코드 파일이 바뀌지 않았는지 확인한다. 그 go 줄의 도구 칸은 `Codex`다.
- Codex가 남기는 state.md와 log.md는 Claude Code와 같은 칸이다 (https://github.com/rimoir/dam/issues/3).
- Codex를 열면 `.team/board.md`와 열린 작업의 state.md를 읽고, 첫 답에 작업 이름과 state.md의 다음 할 일을 말한다. 재개 줄의 도구는 `Codex`다.
- 그 다음 Claude Code로 다시 열어도 같다. 첫 답은 작업 이름과 state.md의 다음 할 일이다. 재개 줄의 도구는 `Claude Code`다.
- 이 이어받기는 README의 Codex 절만으로 된다. 훅 파일을 추가하지 않는다 (https://github.com/rimoir/dam/issues/3).
