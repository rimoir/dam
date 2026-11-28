# 전체 설계

랩 설계 초안: '도구를 갈아끼우는 멀티 에이전트 하네스: 오케스트레이터 설계와 동작 흐름' https://cursor.com/canvas/store-ed6c6a42-9907-4aa3-b747-9b4cc62728b5/823ad43d-e8f0-477e-bbc0-2ad3db2ad38d .

아래 M4 절은 랩 초안 'dam M4 스펙 초안: 파일 레이어 읽기 계약과 강제 장치' https://cursor.com/canvas/store-ed6c6a42-9907-4aa3-b747-9b4cc62728b5/117296ee-29d6-4c10-9a05-5bb81c8ebfcc 의 본문이다. 초안을 에픽으로 다시 쪼개지 않는다. HR P가 훅 도입을 승인했다.

## issue-tracker

이슈 번호로 `python3 scripts/team-session.py new <번호>`를 실행하면 issue-tracker 어댑터가 제목, 이슈 링크, 완료 기준 목록을 읽어 `.team/sessions/<번호>/task.md`의 목표와 완료 기준에 넣는다. 날짜형 작업ID는 이슈를 읽지 않는다. 이미 있는 노트는 덮어쓰지 않는다. 읽기에 실패하면 이유를 알리고 노트를 만들지 않는다.

기본 구현은 github다. 호출은 사람이 이미 로그인한 gh CLI의 읽기다. 선택 결과는 `.team/adapters.lock`의 `issue-tracker` 키이고, 파일이 없으면 github다. 그 파일에 토큰을 적지 않는다. GitHub 명령은 `scripts/issue_tracker.py`에만 둔다. 쓰는 동작의 진입점도 그 파일이고, 사람이 그 동작을 직접 명령했을 때 호출한다. ADR 0007 조건 안의 워커가 호출하는 것은 그 결정이 허용한 동작뿐이다. 이 저장소의 작업 시작 명령은 읽기만 한다.

결정은 `docs/adr/0004-m3-scope.md`와 `docs/adr/0005-adapter-choice.md`다. CI와 머지 규칙은 `docs/adr/0003-ci-and-merge.md`다. 워커의 쓰기와 머지는 `docs/adr/0007-worker-github-write-and-merge.md`다. 워커가 노트에서 쓸 수 있는 곳은 결과 칸뿐이고, 넘기는 글은 맡은 단위뿐인 결정은 `docs/adr/0009-worker-result-section.md`다. 워커는 원격에 쓰지 않고, push, PR, 병합은 데브가 한다. 워커에게 Bash와 MCP를 주지 않는다. `--restricted --strict-mcp-config`를 넣고 `--mcp-config`는 넣지 않는다. 읽기와 파일 쓰기는 Read, Edit, Write뿐이고, bare 허용으로 작업 폴더 밖을 열지 않는다. 결과 칸 밖의 변경은 실행 없이 거부한다. 공통 gitdir 설정이 바뀌면 문제다. 결정 줄이나 승인 줄이 바뀌면 이유에 경로와 그 줄을 적는다. 줄당 200자, 최대 8줄이고 제어 문자는 이스케이프한다. 그 밖 파일은 경로만 적는다. 수거는 세션 그룹이 비었을 때만 결과 한 줄을 읽는다. 수거가 `성공`이면 검사한 작업 폴더를 네트워크와 인증 정보가 없는 최소 루트에 담아 검증하고, 사람이 보는 상태는 `검증 통과` 또는 `검증 실패`다. 잠그지 못하거나 검사 뒤에 내용이 바뀌면 명령을 돌리지 않는다. 빠져나간 프로세스는 그 루트의 init과 함께 끝난다. `검증 통과`일 때만 사람이 노트 루트에서 그 결과 파일 하나만 `git -c core.hooksPath=/dev/null -c core.fsmonitor=false add`와 같은 옵션의 `git commit`으로 담는다. add의 clean filter는 그 저장소에 이미 있는 설정이다. 워커 폴더는 그룹을 끝낸 뒤에 `git worktree remove`로 지운다. 절차는 `docs/adr/0009-worker-result-section.md`다.

## 모드

모드는 조사, 작은 수정, 기능, 이어받기 넷이다. 첫 답은 모드와 이유 한 줄, 작업 이름, 다음 할 일 세 줄이다. 두 모드에 걸치면 세션당 질문은 한 번이고, 기본값은 코드를 덜 바꾸는 쪽이다. 기준과 예시 네 개, 상태 파일 첫 줄 형식은 `docs/adr/0008-mode-declaration.md`다. 모드 바꾸기는 `python3 scripts/team-session.py mode <이름>`이고, Claude `.claude/commands/mode.md`와 Codex `.agents/skills/mode/SKILL.md`의 본문은 같다. 조사 모드는 코드를 바꾸지 않는다. `python3 scripts/team-session.py code-clean`이 `.team/` 밖의 변경이 있으면 실패한다. 결론과 근거는 열린 작업의 result.md에만 남긴다.

## 세션 시작

`python3 scripts/team-session.py start-context`는 `.team/board.md`의 열린 줄과, 브랜치 이름이 이슈 번호로 끝날 때 그 작업 하나의 `state.md`만 낸다. 그 상태 파일 첫 줄이 `모드:`로 시작하면 그 줄도 출력에 남는다. 첫 줄이 없어도 오류는 아니다. 번호가 없거나 그 번호가 열린 줄이 아니면 작업 줄은 `작업: 없음 (열린 줄 N)`이다. 상태 `완료`와 `닫힘`은 열린 줄이 아니다. 도구를 바꿀 때는 `start-context --switch`로 그 로그의 마지막 5줄만 더하고, 로그 전체는 넣지 않는다. 시작 주입 4,000자 또는 상태 파일 2,000자를 넘으면 본문 대신 줄이라는 한 줄만 낸다. 이 값은 측정 전 임시 상한이다. `summary`는 state.md만 내는 호환 명령으로 남는다.

검증 역할의 시작은 `python3 scripts/team-session.py start-context --role 검증 --criteria <완료 기준> --base <SHA> --head <SHA> --checks <검사 명령>`이다. 이 출력은 완료 기준, BASE, HEAD, 검사 명령만 낸다. 현황판, state.md, log.md, task.md, result.md는 읽지 않는다. 작성 세션의 결정 메모는 이 출력에 들어가지 않는다. 역할 인자가 없으면 위 작성 세션 출력과 같다. 환경 변수로 역할을 넘기지 않는다. 훅 파일은 그대로다. 검증 세션은 `python3 scripts/team-session.py verify-session --criteria <완료 기준> --base <SHA> --head <SHA> --checks <검사 명령>`으로 훅이 없는 일회용 복사본 안에서 띄운다. 그 프로세스가 받은 첫 입력은 네 칸뿐이다. macOS에는 `unshare`가 없어 그 세션은 실패로 끝난다. 결정은 `docs/adr/0010-verification-session-input.md`다.

검증 결과 판정은 `python3 scripts/team-session.py verify-judge --head <SHA> --text <결과>`다. 결과 첫 줄은 `PASS`, `ISSUES`, `BLOCKED` 중 하나다. 이어서 `헤드 SHA:`, `확인 방법:`, `증거 요약:`이 한 줄씩 있어야 한다. 셋 중 하나라도 없거나 헤드가 기대한 SHA와 다르면 출력은 `실패`이고 통과로 치지 않는다. `PASS`만 종료 0이다. 읽기 전용 확인은 명령이 작업 폴더의 코드 파일을 직접 찍는다. `python3 scripts/team-session.py verify-readonly --begin --snapshot <작업 폴더 밖 파일>`이 시작 스냅샷을 쓰고, 표준 출력으로 그 파일의 sha256을 낸다. 다이제스트는 검증을 벌이는 호출자가 갖는다. 검증 세션 시작 입력에는 넣지 않는다. `--end --snapshot <같은 파일> --expect <다이제스트>`가 파일 다이제스트를 먼저 보고, 같으면 다시 찍어 비교한다. `--expect`가 없거나 형식이 틀리거나 파일 다이제스트가 다르면 `실패`다. 검증 세션이 그 다이제스트를 다시 계산하지 못하게, 호출자는 격리 밖에서 `verify-readonly --isolated --snapshot <작업 폴더 밖> --command <검증 명령>`으로 전후를 찍는다. 다이제스트는 그 프로세스 메모리에만 있고 격리 루트와 검증 세션 출력에는 없다. 격리 안에서 스냅샷 경로가 보이거나, 격리된 명령이 코드를 바꾸고 스냅샷을 다시 찍거나 덮어쓰면 `실패`다. 이 격리는 Linux `unshare`를 쓴다. macOS에는 `unshare`가 없어 그 확인은 `실패`다. 마운트와 권한 경계는 바꾸지 않는다. 추적된 파일, 추적되지 않은 파일, `.gitignore`된 파일을 포함한다. `.git`과 `.team/`은 빼다. 각 파일은 내용 해시와 lstat이고, 심볼릭 링크는 링크 대상이다. 시작 스냅샷이 없거나 읽을 수 없거나 작업 폴더 안이면 `실패`다. `.team/`만 바뀌면 `깨끗`이다. 파일을 바꿨다 되돌려도 lstat가 다르면 `실패`다. `code-clean` 명령은 그대로다. 훅 파일은 바꾸지 않는다. 결정은 `docs/adr/0011-verification-verdict.md`다.

`python3 scripts/team-session.py rotate <작업ID>`는 log.md가 200줄을 넘으면 앞부분을 `.team/sessions/<작업ID>/log/001.md`로 옮기고, log.md에는 최근 줄과 `이전: log/001.md`만 남긴다. 옮긴 내용은 바꾸지 않는다. 다시 넘으면 `002.md`다. `python3 scripts/team-session.py check`는 상태 파일 2,000자, 시작 주입 4,000자, 로그 200줄, 규칙 원본 50줄, 모드 명령 본문 40줄을 넘기면 실패한다. 두 모드 명령 본문이 달라도 실패한다. `notes.md`만 있는 폴더는 보지 않는다. 로그 200줄도 측정 전 임시 상한이다.

## M4 파일 레이어

시작할 때 넣는 것은 board.md의 열린 줄과 그 작업의 state.md 하나다. 도구를 바꿀 때만 log.md 마지막 5줄을 더한다. log.md 전체, result.md, 닫힌 작업은 넣지 않는다. 검증 역할은 이 계약 밖이고, 완료 기준과 두 SHA와 검사 명령만 넣는다.

파일 역할은 그대로다. task.md는 목표와 완료 기준과 계획이고 시작 때 읽지 않는다. state.md는 지금 상태, 결정, 다음 할 일을 덮어 쓰며 시작 때 열린 작업 하나만 읽는다. log.md는 한 줄씩 추가하고, 넘치면 log/로 옮긴다. result.md는 끝날 때 결과와 교훈 후보다. board.md는 작업당 한 줄이고 열린 줄만 읽는다.

읽기 계약: 새 세션, /compact, resume, clear는 같은 start-context다. 장치 매처는 `startup|resume|clear|compact`다. 열린 작업은 브랜치 끝 번호다. 번호가 없거나 열린 작업이 아니면 작업 줄은 `작업: 없음 (열린 줄 N)`이다. 상한을 넘으면 본문 대신 줄이라는 한 줄만 낸다.

줄이기: state.md는 세 칸만 덮어 쓴다. log.md 앞부분은 지우지 않고 log/로 옮긴다. 요약은 state.md, docs/adr, result.md, kb/ 중 내용에 맞는 곳에 두고 새 요약 파일은 만들지 않는다. 기존 notes.md 폴더는 옮기지 않는다.

강제: Claude Code `.claude/settings.json`과 Codex `.codex/hooks.json`의 SessionStart가 같은 명령을 임시 10초 제한으로 실행한다. 실패해도 세션 시작을 막지 않는다. PreCompact는 공통 장치로 쓰지 않는다. Codex는 훅 파일이 바뀔 때마다 README의 신뢰 검토를 거친다. 결정은 `docs/adr/0006-session-start-hooks.md`다.

사용성 예산의 임시값은 시작 주입 4,000자, state.md 2,000자, log.md 200줄, 훅 10초다. 측정 뒤 고친다. 출처로 확인된 도구 상한은 Claude Code 훅 주입 10,000자와 Codex 훅 약 2,500토큰, 기본 타임아웃 600초다. 이 임시값은 그 안에서 짧게 잡은 추정이다.

출처: https://code.claude.com/docs/en/hooks , https://developers.openai.com/codex/hooks . 이 환경에는 Codex CLI가 없어 사용자 PC의 0.172.0 여부는 확인하지 못했다.
