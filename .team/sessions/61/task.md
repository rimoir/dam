# 작업 61

## 목표

[M5a] 모드 넷과 첫 답 세 줄, 질문 한 번 규칙을 규칙 원본에 쓴다

https://github.com/rimoir/dam/issues/61

## 완료 기준

- 모드는 조사, 작은 수정, 기능, 이어받기 넷뿐이다 (https://github.com/rimoir/dam/issues/55)
- 요청하면 Claude Code와 Codex 모두 첫 답이 모드와 이유 한 줄, 작업 이름, 상태 파일의 다음 할 일 세 줄이다 (https://github.com/rimoir/dam/issues/55)
- 두 모드에 걸치는 요청 예시 네 개에서 질문은 한 번만 나오고, 고를 것 둘과 기본값(코드를 덜 바꾸는 쪽)이 같이 적히며 세션당 질문은 최대 한 번이다 (https://github.com/rimoir/dam/issues/55)

## 계획

- 실패 검사로 모드 이름 한 줄과 ADR 0008의 예시 네 개를 본다.
- 규칙 원본의 첫 답 줄을 세 줄 형식으로 합치고, Codex 절의 중복 첫 답을 한 줄로 줄인다.
- 기준과 예시 네 개는 ADR 0008에 둔다. 규칙 원본은 50줄 아래로 둔다.
- rulesync 43.14.0으로 CLAUDE.md와 AGENTS.md를 다시 만든다.
