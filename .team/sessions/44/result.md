# 결과 44

## 결과

250줄 로그를 `rotate 44`로 옮기면 `log/001.md`가 원래 앞부분과 같고, log.md는 200줄이며 첫 줄은 `이전: log/001.md`다. 상태 2,001자와 로그 201줄에서 `python3 scripts/team-session.py check`는 종료 1이다. `notes.md`만 있는 폴더는 실패 이유에 나오지 않는다.

## 교훈 후보

- 상한 실패를 보여주는 명령은 CI와 같은 `python3 scripts/team-session.py check`다. 검사 대상 루트만 임시 디렉터리로 둔다.
