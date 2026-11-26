# 작업 32

## 목표

[M3b] 현황판을 GitHub 현재 상태와 검사 결과로 갱신한다

https://github.com/rimoir/dam/issues/32

## 완료 기준

- 현황판을 갱신하면 작업마다 GitHub의 현재 상태가 보인다. 열린 PR이면 검토 중과 검사 결과(통과, 실패, 아직 안 돎), 머지되면 완료, 이슈가 닫히면 닫힘이다. GitHub과 다른 상태가 현황판에 남지 않는다 (https://github.com/rimoir/dam/issues/4)
- 시험용 가짜 어댑터로 바꿔 끼워도 현황판 갱신이 같은 형식의 결과로 나온다 (https://github.com/rimoir/dam/issues/4)
- GitHub에 닿지 못하거나 로그인이 안 된 상태에서 현황판을 갱신하면 이유를 알려 주는 오류가 나오고, 틀린 상태가 남지 않는다 (https://github.com/rimoir/dam/issues/4)
- 현황판 갱신은 GitHub에 아무것도 쓰지 않는다. 토큰이나 비밀번호가 노트, 저장소, 로그에 남지 않고, 사람이 이미 로그인한 gh CLI 인증만 쓴다 (https://github.com/rimoir/dam/issues/4)

## 계획

- 실패 검사를 먼저 둔다. 현황판 파일을 읽는다.
- `board`는 읽기만 한다. 상태, 담당, 막힘 칸은 유지하고 GitHub 칸을 붙인다.
- 실패하면 기존 줄을 바꾸지 않는다.
