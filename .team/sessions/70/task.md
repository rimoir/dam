# 작업 70

## 목표

[M5a] 이어받기 모드는 브랜치 끝 번호의 상태 파일과 로그로 멈춘 곳을 찾아 남은 일만 하고 원래 모드로 돌아가게 한다

https://github.com/rimoir/dam/issues/70

## 완료 기준

- 이어받기 모드는 브랜치 끝 번호의 상태 파일과 로그로 멈춘 곳을 찾아 남은 일만 하고, 끝나면 원래 모드로 돌아간다 (https://github.com/rimoir/dam/issues/56)

## 계획

- 실패 검사로 resume begin/end와 상태 파일 없음을 본다.
- 새 읽기 경로는 만들지 않고 기존 mode 교체를 쓴다.
