# 이슈 27

main으로 가는 pull request와 main push에서 검사 세 개를 돌리게 했다. 테스트는 `python3 scripts/team-session_test.py`, 재생성은 rulesync `43.14.0`, 비밀 검사는 gitleaks `8.30.1`이다. 권한은 `contents: read`만이고 secrets는 없다. 서드파티 action은 커밋 SHA로 고정했다.

머지 규칙은 `docs/adr/0003-ci-and-merge.md`와 README에 적었다. main 브랜치 보호는 권고만 적고 저장소 설정은 바꾸지 않는다.

로컬에서 워크플로와 같은 명령을 돌렸다. 테스트 `OK` 7개. rulesync `43.14.0` 재생성 뒤 `git diff --exit-code`는 0. gitleaks `8.30.1` 작업 트리는 `no leaks found`.
