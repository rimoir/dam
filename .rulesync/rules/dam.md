---
root: true
targets: ["claudecode", "codexcli"]
description: "dam 작업 노트와 피드백"
globs: ["**/*"]
---

.team/ 을 먼저 읽어라

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
- 계획을 task.md에 쓴 뒤 사람의 go를 기다린다. go 전에는 `git status`로 코드 파일이 바뀌지 않았는지 확인한다. 노트와 `.team/board.md`는 계획 단계에서 바뀌어도 된다.
- go, 시작, 종료, push는 log.md에 `YYYY-MM-DDTHH:MM:SSZ` 시각과 함께 한 줄로 남긴다.
- 작업 단위가 끝날 때마다 state.md의 지금 상태, 결정, 다음 할 일을 갱신한다.
- 작업이 끝나면 result.md의 결과와 교훈 후보를 채운다.
- 완료 조건을 가리킬 때 번호나 별칭을 쓰지 않는다. 조건 내용을 짧게 쓰고 에픽 링크를 붙인다. 예: /compact 뒤 첫 답에서 재개 한 줄 (https://github.com/rimoir/dam/issues/2).
