# 이슈 7

`.rulesync/rules/dam.md` 하나에서 rulesync 43.14.0으로 `CLAUDE.md`와 `AGENTS.md`를 생성했다. 다시 실행해도 diff가 없다. 기록은 `rulesync-regen.txt`.

superpowers v7.0.2는 로그인 없이 깨끗한 HOME에서 설치했다. Claude Code `2.1.332`는 `obra/superpowers#v7.0.2`로 마켓플레이스를 고정하고 `Version: 7.0.2`와 스킬 목록을 확인했다. Codex CLI `0.172.0`은 `--ref v7.0.2`로 같은 태그를 고정하고 설치 버전 `7.0.2`와 스킬 디렉터리를 확인했다. 출력은 `install-check.txt`.

로그인한 세션에서 스킬이 보이는지는 M0 게이트로 남겼다. writing-plans 경로와 subagent-driven-development는 `docs/adr/0001`, `docs/adr/0002`.
