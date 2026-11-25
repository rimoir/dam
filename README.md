# dam

도구를 바꿔도 같은 작업 노트와 규칙으로 작업이 이어지는 하네스다. Claude Code와 Codex CLI에서 같은 노트로 이어 간다.

- `docs/`: 팀 규칙 원본(`docs/conventions.md`)과 전체 설계 자리(`docs/spec.md`)를 담는다.
- `docs/adr/`: 결정 기록(ADR)을 담는다.
- `docs/milestones/`: 마일스톤 노트를 담는다.
- `kb/`: 지식 베이스를 담는다.
- `.team/`: 작업 노트를 담는다.
- `.team/sessions/`: 이슈 번호별 작업 노트를 담는다.

`kb/`는 나중에 별도 저장소로 뗄 수 있다.

## 설치

Node.js가 필요하다. rulesync는 `43.14.0`으로 고정한다. superpowers는 태그 `v7.0.2`(커밋 `22f0b463e7a5e579904dd6211a520321035526f7`)로 고정한다. 로그인한 세션에서 스킬이 보이는지는 M0 게이트에서 확인한다. 아래는 로그인 없이 설치, 목록, 버전 표시까지다.

### rulesync

원본은 `.rulesync/rules/dam.md`다. 생성:

```bash
npx --yes rulesync@43.14.0 generate --targets claudecode,codexcli
```

다시 실행해도 `CLAUDE.md`와 `AGENTS.md`에 diff가 없어야 한다. 두 파일은 생성물이다. 고칠 때는 원본을 고치고 위 명령을 다시 실행한다.

rulesync `43.14.0`의 README와 package.json 의존성에서 텔레메트리 수집을 찾지 못했다. 끌 스위치는 없다.

### Claude Code

공식 문서(https://code.claude.com/docs/en/plugins/install)는 마켓플레이스 저장소 뒤에 `#태그`를 붙이면 그 태그에 고정된다고 한다. `obra/superpowers`의 `v7.0.2`는 마켓플레이스 `superpowers-dev`를 포함하고, 플러그인 버전은 `7.0.2`다.

```bash
claude plugin marketplace add obra/superpowers#v7.0.2
claude plugin install superpowers@superpowers-dev
claude plugin list
```

`claude plugin list`에 `Version: 7.0.2`가 보여야 한다. `claude plugin details superpowers@superpowers-dev`의 스킬 목록에 `brainstorming`, `writing-plans`가 있다.

텔레메트리:

- superpowers: `SUPERPOWERS_DISABLE_TELEMETRY=1` (v7.0.2 README. `DISABLE_TELEMETRY`와 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`도 존중한다)
- Claude Code: `DISABLE_TELEMETRY=1` 또는 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` (https://code.claude.com/docs/en/env-vars)

### Codex CLI

v7.0.2 README의 Codex CLI 절은 `/plugins` 검색 설치만 적고 태그 고정은 없다. 공식 마켓플레이스 `openai/plugins`의 superpowers `plugin.json` version은 `6.3.0`이라 그 경로로는 `v7.0.2`가 아니다.

Codex CLI `0.172.0`의 `plugin marketplace add`는 `--ref`로 git 태그를 고정한다.

```bash
codex plugin marketplace add obra/superpowers --ref v7.0.2
codex plugin add superpowers@superpowers-dev
codex plugin list --json
```

`plugin list`의 `version`이 `7.0.2`여야 한다. 설치 캐시의 `skills/`에 `brainstorming`, `writing-plans`가 있다.

텔레메트리: 사용자 `~/.codex/config.toml`에 `analytics.enabled = false`를 두면 내장 Statsig 지표가 꺼진다. 명시적 OTLP까지 끄려면 `otel.metrics_exporter = "none"`을 둔다. 프로젝트 로컬 설정은 텔레메트리 키를 무시한다 (https://developers.openai.com/codex/config-reference). superpowers 쪽은 `SUPERPOWERS_DISABLE_TELEMETRY=1`이다.

작업 노트는 훅 없이 이어간다. Codex CLI `0.172.0`은 세션을 열 때 저장소 루트의 `AGENTS.md`를 읽는다. `.codex/hooks.json`은 두지 않는다.

```bash
codex
```

저장소 루트에서 위 명령으로 연다. 열린 작업은 `.team/board.md`와 그 작업의 `state.md`를 읽고, log.md 한 줄의 도구 칸에는 `Codex`를 적는다. 새 작업은 `python3 scripts/team-session.py new <작업ID>`다.
