# Claude 워커는 여기서 띄운다

native 시작은 PATH의 `claude`를 비대화형으로 띄운다. Codex는 미검증이라 띄우지 않고 거부로 남긴다.

## 아직 비어 있는 것

`docs/milestones/m5b-hr-p-check.md`의 결과 칸은 모두 `결과: 아직 없음`이다. 공용 박스에서 본 Claude 확인은 그 칸을 채우지 않는다. Claude 시작 시간 중간값은 `.team/sessions/78/result.md`에 있다. Codex 칸은 미측정이다. 실제 Claude 호출은 사람이 박스에서 따로 한다.

## 보안 경계는 그대로 둔다

워커에게 처음부터 push, PR, 머지 도구를 주는 일은 ADR 0007에 제안으로 적혀 있다. HR P가 직접 확인하기 전에는 채택이 아니다. 이 변경은 그 경계를 열지 않는다.

- 새 토큰을 만들지 않는다. 좁은 토큰이나 GitHub App도 HR P 답 전에 시작하지 않는다.
- 승인과 샌드박스를 끄지 않는다. `bypassPermissions`와 `--dangerously-skip-permissions`는 쓰지 않는다. 훅 신뢰 우회와 새 훅도 없다.
- `scripts/issue_tracker.py`의 쓰기 함수는 사람이 명령했을 때만 gh를 부른다. 그 검사를 느슨하게 하지 않는다.
- 허용 목록의 명령 글자만으로 경계를 삼지 않는다. 넘기는 도구 문자열은 ADR 0007 제안을 실행에 싣는 자리다.

Codex가 작업 폴더 커밋을 막는지는 아직 모른다. 샌드박스를 풀지 않고 Codex는 띄우지 않는다.

## 띄우는 방법

1. 계획에 없는 단위는 거부로 돌려주고 프로세스를 만들지 않는다. 노트 루트에서 띄우지 않는다.
2. 계획에 있는 단위는 노트 루트의 형제인 `dam-<작업ID>`에서만 띄운다. 그 폴더가 없으면 거부하고 프로세스를 만들지 않는다.
3. handle은 노트 루트의 `.team/orchestrator`에 둔다. 워커의 작업 폴더 아래에는 그 파일이 없다.
4. 제품 명령은 PATH에서 `claude`를 고른 뒤 그 절대 경로만 실행한다. `ORCH_CLAUDE`가 `-`이면 PATH를 보지 않는다. 테스트는 이 값으로 실제 도구를 막는다.
5. 워커마다 횟수 상한은 40이다. 임시이고, 시작 시간을 잰 뒤에 고친다.
6. `--permission-mode acceptEdits`, `--permission-prompts none`, `--output-format stream-json`, `--verbose`를 쓴다. 첫 이벤트까지 걸린 시간은 공개 다섯 칸 밖에 둔다. 결과 줄은 result.md에서 거둔다.
7. 워커에게 Bash와 MCP를 넘기지 않는다. `--tools`는 Read, Edit, Write이고, `--disallowedTools`는 Bash다. `--restricted --strict-mcp-config`를 넣고 `--mcp-config`는 넣지 않는다. push, PR, 병합은 데브가 한다. 새 토큰은 없다.
8. 워커는 새 세션으로 뜬다. 끝과 대기는 한 판단이다. 종료 파일이 있고 그룹이 비었으면 끝이다. 그룹에 프로세스가 있으면 대기이고 결과 줄을 읽지 않는다. 멈출 때는 bash 내장 `kill -TERM -<pid>`로 그룹을 끝낸다. `/bin/kill`은 그룹을 못 끝낼 수 있다. 워커 폴더에서는 아무것도 실행하지 않고 쓰지도 않는다.
9. 수거가 `성공`이면 네트워크와 인증 정보가 없는 일회용 복사본에서 검증한다. 사람이 보는 상태는 `검증 통과` 또는 `검증 실패`다. `검증 통과`일 때만 결과 줄을 노트 루트 `.team/sessions/<작업ID>/result.md`에 넣고, `git -c core.hooksPath=/dev/null -c core.fsmonitor=false add -- .team/sessions/<작업ID>/result.md` 뒤에 같은 `-c`를 붙인 `git commit`으로 담는다. add의 clean filter는 그 저장소에 이미 있는 설정이다. 그룹이 비면 `git worktree remove --force ../dam-<작업ID>`로 워커 폴더를 지운다.

## 하지 않은 것

Codex를 띄우는 코드는 없다. Claude 시작 시간 중간값은 `.team/sessions/78/result.md`에 있고, Codex는 미측정이다. HR P PC 결과 칸은 비어 있다.
