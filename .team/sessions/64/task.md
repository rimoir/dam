# 작업 64

## 목표

[M5a] 규칙 원본과 모드 명령 본문의 줄 수 상한을 CI가 검사한다

https://github.com/rimoir/dam/issues/64

## 완료 기준

- 규칙 원본의 줄 수와 모드 명령 본문 줄 수가 상한 이하임을 CI가 확인한다 (https://github.com/rimoir/dam/issues/55)

## 계획

- 실패 검사로 51줄 규칙과 41줄 명령, 서로 다른 본문이 check를 실패하게 한다.
- 확정 상한은 규칙 원본 50줄, 명령 본문 40줄이다. 측정은 39줄과 10줄이라 상한을 올리지 않는다.
- 검사는 기존 `team-session.py check`에 더하고 새 CI 잡은 만들지 않는다.
