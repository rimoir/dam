# 작업 44

## 목표

[M4] 로그를 롤오버하고 상태와 로그 크기 상한을 CI에서 막는다

https://github.com/rimoir/dam/issues/44

## 완료 기준

- 로그가 상한을 넘으면 앞부분이 작업 폴더의 log/로 옮겨지고 옮긴 내용은 바뀌지 않으며, 테스트가 이를 확인한다 (https://github.com/rimoir/dam/issues/42)
- 상태 파일이나 로그가 상한을 넘긴 PR은 CI가 실패한다 (https://github.com/rimoir/dam/issues/42)

## 계획

- 롤오버와 check 실패 검사를 먼저 둔다
- 로그 앞부분을 log/로 옮기고 내용은 그대로 둔다
- CI의 python test 잡에 check를 한 줄 더한다
