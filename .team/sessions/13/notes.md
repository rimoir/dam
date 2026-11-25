# 이슈 13

`.rulesync/rules/dam.md`만 고치고 rulesync 43.14.0으로 `CLAUDE.md`와 `AGENTS.md`를 다시 만들었다. 생성물만 손으로 고치지 않았다.

보강한 내용: 새 작업은 생성기를 부른다. 계획 뒤 go 전에는 `git status`로 코드 파일이 그대로인지 본다. go, 시작, 종료, push는 log.md에 시각과 함께 한 줄이다. 작업 단위마다 state.md를 갱신하고, 끝나면 result.md의 결과와 교훈 후보를 채운다.

go 전 상태 기록은 `go-before-status.txt`. 재생성은 `rulesync-regen.txt`. 비밀 검사는 `secret-scan.txt`.
