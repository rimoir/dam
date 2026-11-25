# 차용 출처

네 항목의 버전, 커밋 SHA, 라이선스, 가져오는 방식이다. 값은 2026-11-25에 각 출처를 클론하거나 npm 타르볼을 받아 확인했다. 생성기 코드와 AGPL 코드는 넣지 않았다.

| 이름 | 고정 | 라이선스 | 가져오는 방식 |
|---|---|---|---|
| superpowers | v7.0.2, `22f0b463e7a5e579904dd6211a520321035526f7` | MIT, Copyright (c) 2025 Jesse Vincent | 플러그인 설치. 이 저장소에 복사하지 않음 |
| rulesync | 43.14.0, git `cef38c2e2b229fec4802b60b632b849ae335348a` | MIT, Copyright (c) 2024 dyoshikawa | CLI만. 생성기 코드는 넣지 않음 |
| pstack | `9e278fe4d4ecd8bfe98b1b79bf4be662efb338cc` | MIT, Copyright (c) 2026 Lauren Tan | `vendor/pstack/`에 필요한 스킬만 복사 |
| groundcrew | `de6fddba94d2bd3f9252eeef19535ae7b32c7f6d` | MIT, Copyright (c) 2026 Clipboard Health | 참고만. 복사도 설치도 하지 않음 |

## superpowers

- 저장소: https://github.com/obra/superpowers
- `git clone --branch v7.0.2` 뒤 `git describe --tags --exact-match`가 `v7.0.2`, `git rev-parse HEAD`가 `22f0b463e7a5e579904dd6211a520321035526f7`.
- `.claude-plugin/plugin.json`의 `version`은 `7.0.2`. LICENSE 첫 줄은 MIT License, 저작권은 Copyright (c) 2025 Jesse Vincent.
- 설치 절차는 #7 README에 둔다.

## rulesync

- 저장소: https://github.com/dyoshikawa/rulesync
- git 태그 `v43.14.0`의 `git rev-parse HEAD`는 `cef38c2e2b229fec4802b60b632b849ae335348a`. 그 커밋의 `package.json` version은 `43.14.0`, license는 MIT.
- LICENSE 저작권은 Copyright (c) 2024 dyoshikawa.
- npm `rulesync@43.14.0`의 `dist.integrity`는 `sha512-EXgI0d12WyyJ6ItUrWXLeR8NkJlNy+zHLdOn0aAYFh+jCyHMuMdpybVgLrg3EYy1Wnb28hyYgr6uOiMFYVKXFw==`. 받은 타르볼의 sha512과 같았다.
- 생성 명령과 재생성 diff는 #7에서 다룬다.

## pstack

- 저장소: https://github.com/cursor/plugins
- `git rev-parse HEAD`가 `9e278fe4d4ecd8bfe98b1b79bf4be662efb338cc`.
- `pstack/LICENSE` 저작권은 Copyright (c) 2026 Lauren Tan. 원문은 `vendor/pstack/LICENSE`. 출처 SHA는 `vendor/pstack/SOURCE_SHA`.
- 복사한 파일은 `skills/sharpen/SKILL.md`, `skills/in-your-own-words/SKILL.md`, `skills/why/SKILL.md`뿐이다. 원본과 `diff -ru` 출력이 없고 exit 0이다. 기록은 `.team/sessions/6/vendor-check.txt`.
- 세 스킬 본문에서 `principle`을 찾지 못했다. 가리키는 principle 스킬이 없어 원칙 파일은 복사하지 않았다.
- `why` 본문은 런타임 동작을 `how` 스킬로 보라고 적는다. 벤더에는 `how`, `swarm`, `arena`를 넣지 않는다 (https://github.com/rimoir/dam/issues/1). `find`로 그 이름 디렉터리는 0개다.

## groundcrew

- 저장소: https://github.com/ClipboardHealth/groundcrew
- 커밋 `de6fddba94d2bd3f9252eeef19535ae7b32c7f6d`의 LICENSE는 MIT, Copyright (c) 2026 Clipboard Health.
- 작업 소스 어댑터와 worktree 배정 패턴만 참고한다. 파일은 가져오지 않았고 도구도 설치하지 않는다.
