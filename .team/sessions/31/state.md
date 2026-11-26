# 상태 31

## 지금 상태

pull 명령과 검사를 넣었다. PR을 연 뒤 검사와 검토를 확인한다.

## 결정

- PR은 `python3 scripts/team-session.py pull <이슈번호> --title <제목> --tool Codex`로만 연다. `new`는 열지 않는다.
- 본문은 이슈 링크 한 줄이다. log.md 한 줄의 종류는 기존 `push`이고, 내용 칸에 PR URL을 넣는다. 도구는 `Claude Code` 또는 `Codex`다.
- 열기에 실패하면 log.md를 쓰지 않는다.

## 다음 할 일

PR의 검사 세 개와 검토 기록을 확인한 뒤 머지한다. 사람 계정으로 실제 PR을 여는 확인은 HR P 게이트로 남긴다.
