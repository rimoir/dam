# 이슈 12

작업마다 `.team/sessions/<작업ID>/`에 task.md, state.md, log.md, result.md를 만들고 `.team/board.md`에 한 줄을 붙이는 생성기를 두었다. 사람이 폴더를 손으로 만들지 않게 하려고다.

작업ID는 이슈 번호이거나 `YYYY-MM-DD-짧은이름`이다. 같은 ID로 다시 실행해도 노트를 덮어쓰지 않는다. M0의 `5`, `6`, `7` 폴더는 건드리지 않았다.

실패하던 검사는 `tdd.txt`. 두 작업 실행은 `generator-run.txt`. 비밀 검사는 `secret-scan.txt`. 세션이 생성기를 부르는 규칙은 #13이다.
