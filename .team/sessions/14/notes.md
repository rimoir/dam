# 이슈 14

훅을 넣지 않았다. 세션 시작과 compact 뒤에는 board.md와 열린 작업의 state.md만 읽고, 첫 답은 작업 이름과 다음 할 일을 말하며, 재개는 log.md 한 줄로 남기라고 규칙에 적었다.

세션 시작 요약은 `scripts/team-session.py summary`가 state.md만 출력한다. 10,000자를 넘기면 실패한다 (https://github.com/rimoir/dam/issues/2). log.md 전체는 요약에 넣지 않는다.

두 작업 12와 13은 폴더가 다르고 board.md에 한 줄씩 남는다. 다시 실행해도 첫 노트가 그대로다. 기록은 `isolation.txt`. 실패하던 요약 검사는 `tdd-fail.txt`, 통과는 `tdd-pass.txt`.

로그인한 Claude Code에서 /compact와 새 세션 첫 답은 돌리지 않았다. M1 게이트로 남긴다.
