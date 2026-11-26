# 작업 43

## 목표

[M4] start-context가 열린 현황과 상태만 내게 하고 규칙 모순을 없앤다

https://github.com/rimoir/dam/issues/43

## 완료 기준

- 세션 시작용 출력이 현황판의 열린 줄과 열린 작업 하나의 상태 파일만 담고(도구 전환 때는 로그 마지막 5줄을 더함), 출력이 정해 둔 글자 상한 이하인지 CI 테스트가 확인한다 (https://github.com/rimoir/dam/issues/42)
- 시작 주입에는 로그 전체가 들어가지 않는다(도구 전환 때의 마지막 5줄만 예외) (https://github.com/rimoir/dam/issues/42)
- dam의 열린 작업이 현황판과 노트 네 파일(목표, 상태, 로그, 결과)을 쓰고, 규칙 원본에서 '폴더를 통째로 읽어라'와 '현황판과 상태만 읽어라'가 서로 다르게 적힌 모순이 없어진다 (https://github.com/rimoir/dam/issues/42)

## 계획

- 실패하는 start-context 검사를 먼저 둔다
- 열린 줄과 작업 하나의 state.md만 내고, 상한과 로그 전체를 뺀다
- 규칙 원본 앞줄을 고치고 rulesync로 다시 만든다
- 훅 파일은 만들지 않는다
