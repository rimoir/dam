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

## 이슈로 작업 시작

작업ID가 이슈 번호이면 `python3 scripts/team-session.py new <번호>`가 issue-tracker 어댑터로 그 이슈를 읽는다. 기본 선택은 github이고, 사람이 이미 로그인한 `gh`만 쓴다. 제목과 이슈 링크는 task.md 목표에, 완료 기준 목록은 완료 기준 칸에 들어간다. 날짜형 작업ID는 이슈를 읽지 않는다. 이미 있는 노트는 덮어쓰지 않는다. 이슈를 읽지 못하면 이유를 알리고 노트를 만들지 않는다.

선택 파일은 `.team/adapters.lock`의 `issue-tracker` 키다. 파일이 없으면 github다. 토큰은 적지 않는다. 결정은 `docs/adr/0004-m3-scope.md`, `docs/adr/0005-adapter-choice.md`다.

## 검사

main으로 가는 pull request와 main push에서 같은 검사 세 개가 돈다. 로컬에서도 같은 명령을 쓴다. Node.js는 `22.22.0` 이상이다.

테스트:

```bash
python3 scripts/team-session_test.py
```

rulesync `43.14.0` 재생성. 출력이 없으면 커밋된 `CLAUDE.md`, `AGENTS.md`와 같다.

```bash
npx --yes rulesync@43.14.0 generate --targets claudecode,codexcli
git diff --exit-code -- CLAUDE.md AGENTS.md
```

gitleaks `8.30.1`. 작업 트리와, main 이후로 더한 커밋을 본다.

```bash
gitleaks detect --source . --no-git -v
gitleaks detect --source . --log-opts="origin/main..HEAD" -v
```

## 머지

첫 CI pull request는 검사가 아직 없으므로, 코드를 보고 남긴 검토 기록이 한 건 이상이면 머지한다. 연 뒤 1분이 지나기 전에는 머지하지 않는다.

그 다음부터는 검사 세 개가 통과하고, 검토 기록이 있어야 한다. 검토 기록은 승인, 또는 사람이나 검토 봇이 코드를 보고 남긴 내용 있는 검토 코멘트다. "검토하지 못했다"는 봇 알림과 머지 자체는 기록이 아니다. pull request를 연 뒤 1분 안에 머지하지 않고, 리뷰 없이 머지하지 않는다.

main을 브랜치 보호 또는 룰셋으로 막는 설정은 HR P가 적용한다. 자세한 결정은 `docs/adr/0003-ci-and-merge.md`다.
