모드: 기능

# 상태 81

## 지금 상태

verify-record가 PASS만 남긴다. 키 이름에 password, secret, token이 들어가면 그 값을 가림 한 곳에서 지운다. 값 없는 문장은 그대로다.

## 결정

- 통과는 PASS뿐이다. ISSUES, BLOCKED, 형식 불량은 파일을 바꾸지 않는다.
- 로그 종류는 종료다. 내용 칸은 `검증 PASS 모델 <이름> 헤드 <짧은 SHA>`다. 이 줄은 go로 세지 않는다.
- 결과 칸은 수거가 읽는 한 줄이고, 증거 요약은 다음 절이다. 교훈 후보는 둔다.
- 토큰과 이름 뒤의 값은 issue_tracker.redact 한 곳에서 지운다. 훅과 격리 코드는 바꾸지 않는다. PR 코멘트는 하지 않는다.
- 이름 없이 그냥 적힌 비밀번호는 범위 밖이다 (https://github.com/rimoir/dam/issues/81#issuecomment-7240213178).

## 다음 할 일

#143에 가림을 올리고 #82는 시작하지 않는다.
