# 스킬 평가·페이퍼컷·폐기 (Skill Evals)

스킬은 만들 때보다 **지우고 줄일 때** 근거가 더 필요하다. 이 문서는 그 근거를 만드는 세 장치를 정한다: 명세와 eval 사례, 페이퍼컷 기록, 폐기 절차.
작성 규칙은 `docs/skill-authoring.md` 가 정본이다.

## 1. 명세와 사례의 위치

```
{plugin}/evals/{skill}/
├── spec.md                 # 목표 · 결과물 · 필수 행동 · 금지 행동 (행동 사례가 있는 스킬)
├── trigger/                # 사용자 표현 1개 → 이 스킬이 불렸는가
│   ├── prompt.md
│   └── graders/fires.md
└── {behavior-case}/        # 스킬 on/off 로 결과가 달라지는가
    ├── prompt.md
    └── graders/*.md
```

- **명세(`spec.md`)가 자산이다.** SKILL.md 는 모델·호스트가 바뀌면 다시 쓴다. 명세와 사례는 그대로 남아서 새 SKILL.md 를 시험한다.
- 사례의 프롬프트는 사용자가 실제로 입력하는 표현으로 쓴다. `description` 의 트리거 문구를 그대로 옮긴 사례가 `trigger` 다.
- 사례 태그는 두 가지다: `trigger`(스킬 호출 여부), `behavior`(결과 품질).
- 형식은 `claude plugin eval` 의 `prompt.md + graders/*.md` 다. scaffold 스크립트와 실제 MCP 서버는 쓰지 않는다 (작성 시점에는 Bash 없이 끝나는 사례만 둔다).

## 2. 실행

모델을 실제로 실행하므로 비용이 든다. **CI(`scripts/verify.sh`)에 넣지 않는다.** 스킬의 `description` 이나 본문을 고친 PR 에서 수동으로 실행한다.

```bash
# 트리거: baseline arm 없이 스킬 호출 여부만 채점한다
claude plugin eval ./common --tag trigger --ablation none --no-publish --max-cost-usd 5

# 행동: 스킬 on/off 두 arm 을 실행하고 점수 차이를 본다
claude plugin eval ./common --tag behavior --no-publish --max-cost-usd 5

# 항상 로드되는 토큰 비용 (description 합계)
claude --plugin-dir ./common plugin details common
```

- 결과는 `{plugin}/evals/results/` 에 생긴다. `.gitignore` 대상이다.
- 고치기 **전에** 한 번 실행해 기준선을 남기고, 고친 뒤 다시 실행해 비교한다.
- 사례 1개는 2~3회만 실행한다. 표본이 작으므로 사례 1개의 1회 실패는 변동으로 본다. 같은 사례가 반복해서 실패할 때만 회귀로 본다.

## 3. 판정

| 결과 | 판정 | 조치 |
|---|---|---|
| `trigger` 사례가 고친 뒤 실패 | description 회귀 | 트리거 문구를 되돌리거나 고친다 |
| `behavior` 점수가 고친 뒤 하락 | 본문 회귀 | 지운 문장을 되돌린다 |
| on/off 점수 차이가 반복 실행의 변동 안 | **흡수됨** — 모델이 스킬 없이도 한다 | 폐기 후보 (4절) |
| on 이 off 보다 뚜렷하게 높음 | 유지 | 본문을 한 문장씩 줄이는 시험을 계속할 수 있다 |

모든 사례를 100% 통과하는 묶음은 답이 바뀌어도 알아채지 못할 수 있다. 통과하지 못하는 사례를 지우지 말고 원인을 적는다.

## 4. 폐기 절차

1. 후보 선정: `흡수됨` 판정, 또는 `/skill-doctor`·사용량 기록에서 장기간 호출이 없는 스킬.
2. 참조 확인: 다른 스킬·에이전트·오버레이가 그 스킬을 호출하는지 `scripts/check_contracts.py` 로 확인한다 (삭제 뒤 `missing internal skill call` 이 나오면 호출자가 있다).
3. 삭제 PR: SKILL.md 와 `evals/{skill}/` 를 함께 지우고, README 변경 이력에 근거(사례 이름과 점수)를 적는다. 대체 호출이 있으면 각 플러그인 README 의 마이그레이션 표에 적는다.
4. 스킬을 지우지 않고 줄일 때도 같은 근거를 남긴다.

## 5. 페이퍼컷 (마찰 자동 기록)

스킬 지시가 틀렸거나 명령이 스킬 설명과 다르게 끝나도 에이전트는 우회해서 일을 끝낸다. 그 순간이 기록되지 않으면 스킬은 고쳐지지 않는다.

- common mod(`common/hooks/register.tsx`)가 `harnessPapercut` 컨텍스트 블록을 넣는다. 에이전트는 마찰을 만나면 작업 뒤 `common/hooks/papercut.py record` 를 1회 실행한다.
- 기록 필드: `plugin, skill, goal(하려던 일), command(실행한 명령), expected(기대한 결과), actual(실제 결과), workaround(우회 방법), proposal(수정안)`.
- git 저장소 안에서만 기록한다 (저장 폴더를 저장소 기준으로 정한다). 저장소 밖에서는 `NOT_GIT_REPO` 로 끝난다.
- 저장 위치는 저장소 밖이다: `~/.claude/harness-metrics/<repo>-<hash>/papercuts.jsonl` (`metrics.py` 와 같은 폴더). **자동으로 외부에 보내지 않는다.**
- 확인: `papercut.py list --cwd . [--plugin NAME]`.
- 제출: `/common:submit-feedback --papercuts`. 사람이 하는 일은 두 가지다 — 비슷한 기록을 묶어 제출할 항목을 고르는 것, 제출 내용을 검토하는 것.
- mod 는 Claude Code 전용이다. 다른 호스트에서는 기록이 생기지 않을 뿐이고 스킬 절차는 달라지지 않는다.

## 6. 현재 범위와 후속 후보

- 사례가 있는 스킬: `common`(트리거 10, 행동 2), `be-harness`(트리거 4, 행동 1). 나머지는 사례가 없다. `spec.md` 는 행동 사례가 있는 3개 스킬에만 있다.
- git 저장소·프로필·MCP 가 필요한 스킬(commit 실제 실행, convention-check, start-workflow)은 scaffold 가 필요해서 아직 행동 사례가 없다.
- 후속 후보: `sync-base` 의 base 결정·버전 계산·충돌 분류를 helper 스크립트로 옮기기, 탐색 전용 에이전트의 모델 낮추기, 에이전트 `description` 예산.
