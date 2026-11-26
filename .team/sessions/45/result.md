# 결과 45

## 결과

SessionStart 훅이 저장소 안에서 start-context를 호출한다. 상태 파일이 깨져 UnicodeDecodeError가 나도 훅 명령은 종료 0이고, stdout에 세션을 멈추는 continue false는 없다. 결정은 ADR 0006, 신뢰 검토는 README, 규칙 생성물은 rulesync로 맞췄다.

## 교훈 후보

- 훅 명령의 `|| true`는 스크립트 실패를 세션 차단으로 바꾸지 않는다. 성공일 때는 start-context stdout이 그대로 남는다.
