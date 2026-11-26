# 0006. SessionStart 훅

## 상태

채택. 2026-11-26. HR P가 세션 시작 훅을 승인했다.

## 결정

Claude Code와 Codex의 SessionStart 훅으로 `python3 scripts/team-session.py start-context`를 실행한다. matcher는 `startup|resume|clear|compact`다. 타임아웃은 임시 10초다. PreCompact는 쓰지 않는다.

파일은 저장소 안의 `.claude/settings.json`과 `.codex/hooks.json`만이다. 사용자 홈과 전역 설정은 바꾸지 않는다. 명령 끝에 `|| true`를 붙여, 스크립트가 실패하거나 시간 안에 끝나지 않아도 셸은 종료 0으로 돌아온다. 세션 시작은 막지 않는다.

이 결정은 #3의 '훅 파일을 추가하지 않는다'를 뒤집는다. Claude Code와 Codex 둘 다에 SessionStart를 둔다. HR P 승인: https://github.com/rimoir/dam/issues/45#issuecomment-7180909933

Codex가 저장소 훅을 실행하려면 사람이 그 훅 정의를 검토하고 신뢰해야 한다. 출처는 https://developers.openai.com/codex/hooks 의 Review and trust hooks와 Where Codex looks for hooks다.

- 관리되지 않는 훅은 실행 전에 검토와 신뢰가 필요하다.
- Codex는 신뢰를 그 훅 정의의 현재 해시에 기록한다. 새 훅이나 바뀐 훅은 검토 대상으로 표시되고, 신뢰하기 전에는 건너뛴다.
- 저장소 훅 위치는 신뢰된 프로젝트 층의 `.codex/hooks.json`이다. Codex는 신뢰된 프로젝트 층의 `.codex`에서만 훅을 읽는다.
- CLI에서 `/hooks`로 훅 출처를 보고, 새 훅이나 바뀐 훅을 검토하고, 신뢰하거나, 비관리 훅을 하나씩 끈다.
- 시작 때 검토가 필요하면 Codex는 `/hooks`를 열라는 경고를 낸다.

이 절차 밖에 시작 질문이나 diff 순서를 더하지 않는다. 그 문장들은 위 문서에 없다.

번호는 #27의 0003, M3의 0004, 어댑터 선택의 0005 다음이라 0006이다.

## 이유

컨텍스트 창 대신 열린 작업 노트를 세션 시작에 넣기 위해서다. 두 도구 모두 SessionStart에서 compact를 매처로 받을 수 있다. 훅 실패가 세션 자체를 막으면 안 된다.
