모드: 기능

# 상태 81

## 지금 상태

verify-record가 PASS만 result.md와 log.md에 남긴다. 형식 불량과 통과가 아닌 판정은 파일을 바꾸지 않는다. 전체 테스트는 통과했다.

## 결정

- 통과는 PASS뿐이다. ISSUES, BLOCKED, 형식 불량은 파일을 바꾸지 않는다.
- 로그 종류는 종료다. 내용 칸은 `검증 PASS 모델 <이름> 헤드 <짧은 SHA>`다. 이 줄은 go로 세지 않는다.
- 결과 칸은 수거가 읽는 한 줄이고, 증거 요약은 다음 절이다. 교훈 후보는 둔다.
- 토큰은 기존 redact로 지운다. 훅과 격리 코드는 바꾸지 않는다. PR 코멘트는 하지 않는다.

## 다음 할 일

verify-session, verify-readonly, verify-judge를 이 작업 폴더에 남긴다.
