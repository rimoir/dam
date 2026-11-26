# 작업 31

## 목표

[M3b] PR 본문에 이슈 링크를 넣고 log.md에 PR URL을 남긴다

https://github.com/rimoir/dam/issues/31

## 완료 기준

- 그 작업으로 연 PR 본문에 이슈 #N 링크가 있고, log.md에 PR URL이 도구 칸과 함께 한 줄로 남는다 (https://github.com/rimoir/dam/issues/4)
- GitHub에 쓰는 동작(PR 열기)은 사람이 그 동작을 직접 명령했을 때만 일어나고 자동으로 일어나지 않는다. GitHub 밖으로는 아무것도 보내지 않는다 (https://github.com/rimoir/dam/issues/4)
- 토큰이나 비밀번호가 노트, 저장소, 로그에 남지 않고, 사람이 이미 로그인한 gh CLI 인증만 쓴다 (https://github.com/rimoir/dam/issues/4)

## 계획

- 실패 검사를 먼저 둔다. 본문과 log.md 한 줄을 읽는다.
- `pull`은 사람이 명령할 때만 PR을 연다. 본문은 이슈 링크다.
- 열기에 실패하면 log.md를 바꾸지 않는다. `new`는 PR을 열지 않는다.
