모드: 기능

# 상태 72

## 지금 상태

시작과 수거는 `scripts/orchestrator.py`만 하고, native와 fake가 같은 다섯 칸을 낸다. 모르는 이름은 거부한다.

## 결정

- 반환 칸은 ok, handle, state, line, reason이다.
- 파일이 없거나 orchestrator 키가 없으면 native다.
- fake는 시험용이고 제품 이름이 아니다. 실제 도구는 띄우지 않는다.
- 로그 도구 칸은 Codex다. go는 이 에픽 구현 지시다.

## 다음 할 일

#73 시작 전 검사를 이 어댑터 위에 얹는다.
