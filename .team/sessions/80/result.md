# 결과 80

## 결과

가짜 검증 네 경우에서 PASS만 종료 0이다. 읽기 전용은 시작 스냅샷과 끝 스냅샷의 내용 해시와 lstat를 비교한다. scripts/ok.py를 바꿨다 되돌리면 실패와 scripts/ok.py다. gitignore된 ignored.py를 만들면 실패와 ignored.py다. 스냅샷이 없으면 실패다. 워커 judge는 그대로다.

## 교훈 후보

- 경로 이름과 git status만 보면 되돌린 내용과 무시된 파일을 놓친다. 내용 해시와 lstat를 명령이 직접 찍어야 한다.
- 결과 기록과 PR 코멘트는 다음 이슈다.
