# 작업 68

## 목표

[M5a] 기능 계획의 형식을 task.md에 정하고 go 전에 코드가 안 바뀌는지 검사하는 명령을 둔다

https://github.com/rimoir/dam/issues/68

## 완료 기준

- 기능 모드(완료 기준 여러 개, 세 파일 이상, 또는 PR 여러 개)는 질문 뒤 task.md에 계획을 쓰고, 계획에 PR 단위 목록, 단위 사이 의존, 단위마다 건드릴 파일, 단위마다 검증 방법이 있다 (https://github.com/rimoir/dam/issues/56)
- 사람의 go가 log.md에 남기 전에는 코드 파일이 바뀌지 않는다 (https://github.com/rimoir/dam/issues/56)

## 계획

- 실패 검사로 plan-check의 네 칸, go 전 코드 변경, 한 화면 알림을 본다.
- 읽기 함수는 뒤에 범위 검사가 그대로 쓰게 나눈다.
