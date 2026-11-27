# HR P PC 실행 확인

이 문서는 HR P PC에서 돌릴 절차다. 이 저장소의 개발 세션은 로그인하지 않고, 명령을 실행하지 않는다.

상태: 공용 박스의 Claude 단계는 끝났다. 그 결과는 HR P PC에서 나온 것이 아니다. Codex 단계와 HR P Mac 확인은 #139에서 대기한다(https://github.com/rimoir/dam/issues/139).

샌드박스를 끄지 않는다. 승인을 전부 끄는 옵션도 쓰지 않는다. Codex가 작업 폴더의 커밋을 막으면 그 사실을 적고 #78은 멈춘다. 풀지는 HR P가 정한다.

Claude Code의 물을 일을 거부하는 옵션은 v2.1.259 이상이라는 요건이 있다. 버전이 낮으면 그 사실을 적고, 샌드박스를 끄는 쪽으로 바꾸지 않는다.

시험용 폴더와 브랜치는 `m5-try`뿐이다. dam 저장소의 브랜치는 지우지 않는다.

## 0. 버전과 로그인

```
claude --version
codex --version
claude auth status
```

결과: 공용 박스. Claude Code 2.1.317. `claude auth status`는 loggedIn true, subscriptionType max. 0.51초. 출처는 https://github.com/rimoir/dam/issues/77#issuecomment-7206185368 과 PM 검토 https://github.com/rimoir/dam/issues/77#issuecomment-7206253884. `codex --version`은 #139로 옮김(https://github.com/rimoir/dam/issues/139).

## 1. 시험용 작업 폴더

```
cd ~/dam && git worktree add ../dam-m5-try -b m5-try origin/main
```

결과: 공용 박스, 통과, 경로만 변경. 0.04초. 문서 경로 `../dam-m5-try`는 `/workspace/dam-m5-try`가 되어 허락 범위 밖이라 `/workspace/dam-verify/.m5-try`로 바꿨다. 새 브랜치 `m5-try`, HEAD는 `a555a9bc2b6bbed623b2e3a537a08aa10ba527bf`로 `origin/main`과 같다. 출처는 https://github.com/rimoir/dam/issues/77#issuecomment-7206185368.

## 2. Claude Code 읽기 전용

```
cd ../dam-m5-try
claude -p "board.md의 열린 줄 수를 숫자 하나로만 답해" \
  --output-format json --permission-mode plan --max-turns 3 > /tmp/m5-c.json
```

결과: 공용 박스, 통과. 2.46초. 종료 0, 답 `18`, 1턴, 거부된 권한 0건. 시험 폴더의 `.team/board.md`를 직접 세면 21줄 중 완료 3줄을 뺀 18줄이다. PM 검토도 답 `18`, 권한 거부 0건, 실행 뒤 작업 폴더 변경 0줄. 출처는 https://github.com/rimoir/dam/issues/77#issuecomment-7206185368 과 https://github.com/rimoir/dam/issues/77#issuecomment-7206253884.

## 3. 세션 재개

```
claude -p "방금 숫자를 한 번 더 말해" --resume "$(jq -r .session_id /tmp/m5-c.json)" --output-format json
```

결과: 공용 박스, 통과. 1.12초. 종료 0, 같은 세션 id, 답 `18`, 거부된 권한 0건. PM 검토가 적은 세션 id는 `574ed42e…`이고, 그 뒤는 댓글에 없음. 출처는 https://github.com/rimoir/dam/issues/77#issuecomment-7206185368 과 https://github.com/rimoir/dam/issues/77#issuecomment-7206253884.

## 4. Codex 읽기 전용

```
codex exec -C ../dam-m5-try --sandbox read-only --json -o /tmp/m5-x.md \
  "board.md의 열린 줄 수를 숫자 하나로만 답해"
```

결과: #139로 옮김(https://github.com/rimoir/dam/issues/139)

## 5. 커밋

Codex가 작업 폴더 안에서 커밋할 수 있는지 본다. push는 넣지 않는다.

```
codex exec -C ../dam-m5-try --sandbox workspace-write \
  "빈 파일 m5-probe.txt를 만들고 git add 뒤 probe로 커밋해"
```

결과: #139로 옮김(https://github.com/rimoir/dam/issues/139)

## 6. 시작 시간

명령부터 첫 이벤트까지, 두 도구 각 5회 중간값이다.

```
claude -p "안녕" --output-format stream-json --verbose
codex exec -C ../dam-m5-try --json "안녕"
```

결과: 공용 박스. Claude만 통과하고 Codex 5회는 #139로 옮김(https://github.com/rimoir/dam/issues/139). 명령은 `claude -p "안녕" --output-format stream-json --verbose`, 5회, 모두 종료 0. 첫 이벤트는 훅 시작 이벤트라 모델 응답이 아니다. 출처는 https://github.com/rimoir/dam/issues/77#issuecomment-7206185368.

| 회차 | 첫 이벤트 | init | 첫 assistant | 전체 |
|---|---|---|---|---|
| 1 | 0.22초 | 0.33초 | 1.85초 | 3.82초 |
| 2 | 0.22초 | 0.33초 | 2.36초 | 3.21초 |
| 3 | 0.23초 | 0.36초 | 1.69초 | 2.85초 |
| 4 | 0.24초 | 0.34초 | 1.64초 | 3.15초 |
| 5 | 0.22초 | 0.33초 | 2.23초 | 3.32초 |
| 중간값 | 0.22초 | 0.33초 | 1.85초 | 3.21초 |

PM 검토 https://github.com/rimoir/dam/issues/77#issuecomment-7206253884 는 중간값을 첫 답 1.85초, 전체 3.21초로 적고 예산 15초 안이라고 했다. 첫 이벤트 중간값 0.22초는 그 댓글에 없음.

## 7. 정리

시험용 폴더와 `m5-try` 브랜치만 정리한다.

```
cd ~/dam && git worktree remove --force ../dam-m5-try && git branch -D m5-try
```

결과: 공용 박스, 통과, 경로만 변경. 0.02초. `git worktree remove --force /workspace/dam-verify/.m5-try && git branch -D m5-try`. `Deleted branch m5-try (was a555a9b)`. 정리 뒤 `git worktree list`에는 `/workspace/dam-verify`만 있고 `m5-try`는 없다. 지운 것은 만든 로컬 브랜치 하나이고 push한 적이 없으며 커밋도 없었다. 원격 브랜치는 건드리지 않았다. PM 검토는 클론이 `2021a24`로 돌아왔다고 적었다. 출처는 https://github.com/rimoir/dam/issues/77#issuecomment-7206185368 과 https://github.com/rimoir/dam/issues/77#issuecomment-7206253884.
