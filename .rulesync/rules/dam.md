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
