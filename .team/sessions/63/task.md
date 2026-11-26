# 작업 63

## 목표

[M5a] 모드 바꾸기 명령을 두 도구에 같은 본문으로 두고 상태 파일 첫 줄만 바꾼다

https://github.com/rimoir/dam/issues/63

## 완료 기준

- 모드 바꾸기 명령을 내면 다음 답부터 그 모드로 선언하고, 열린 작업이 있으면 그 작업 상태 파일 첫 줄이 바뀐다 (https://github.com/rimoir/dam/issues/55)
- 열린 작업이 없으면 모드를 바꿔도 파일을 만들지 않는다 (https://github.com/rimoir/dam/issues/55)
- Claude Code와 Codex의 모드 명령 본문이 같은지 CI가 확인한다 (https://github.com/rimoir/dam/issues/55)

## 계획

- 실패 검사로 mode 하위 명령과 두 본문 일치를 본다.
- 열린 작업의 state.md 첫 줄만 바꾸고, 이름이 넷 밖이면 거부한다.
- 열린 작업이 없으면 폴더를 만들지 않는다.
- Claude는 `.claude/commands/mode.md`, Codex는 `.agents/skills/mode/SKILL.md`에 같은 본문을 둔다. `.codex`에는 파일을 넣지 않는다.
