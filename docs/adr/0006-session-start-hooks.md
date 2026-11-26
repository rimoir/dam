# 0006. SessionStart 훅

## 상태

채택. 2026-11-26. HR P가 세션 시작 훅을 승인했다.

## 결정

Claude Code와 Codex의 SessionStart 훅으로 `python3 scripts/team-session.py start-context`를 실행한다. matcher는 `startup|resume|clear|compact`다. 타임아웃은 임시 10초다. PreCompact는 쓰지 않는다.

파일은 저장소 안의 `.claude/settings.json`과 `.codex/hooks.json`만이다. 사용자 홈과 전역 설정은 바꾸지 않는다. 명령 끝에 `|| true`를 붙여, 스크립트가 실패하거나 시간 안에 끝나지 않아도 셸은 종료 0으로 돌아온다. 세션 시작은 막지 않는다.

이 결정은 #3의 '훅 파일을 추가하지 않는다'를 뒤집는다. Codex는 훅 파일이 바뀔 때마다 신뢰 검토가 필요하며, 절차는 README에 적는다.

번호는 #27의 0003, M3의 0004, 어댑터 선택의 0005 다음이라 0006이다.

## 이유

컨텍스트 창 대신 열린 작업 노트를 세션 시작에 넣기 위해서다. 두 도구 모두 SessionStart에서 compact를 매처로 받을 수 있다. 훅 실패가 세션 자체를 막으면 안 된다.
