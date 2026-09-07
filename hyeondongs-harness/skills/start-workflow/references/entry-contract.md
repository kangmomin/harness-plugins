> 모든 진입·재개·도메인 전환에서 먼저 `assets/workflow_policy.py route`를 실행한다. 이 검사는 읽기 전용이며 init, profile 저장, Plan/구현, 브랜치, RUN 생성보다 앞선다.

# 진입 계약

| 도메인 | Build | Analyze (`--analyze`, `-a`) | Verify (`--verify`, `-v`) | Build `--hard` / `-h` |
|--------|-------|--------------------------|------------------------|---------------------|
| BE / minmos | 지원 | 지원 | 지원 | 현재 브랜치 commit → Gate → push, PR 생략 |
| FE / hyeondongs | 지원 | `BLOCKED:UNSUPPORTED_MODE` | `BLOCKED:UNSUPPORTED_MODE` | 현재 브랜치 commit → Gate → push, PR 생략 |
| FS | 지원 | `BLOCKED:UNSUPPORTED_MODE` | `BLOCKED:UNSUPPORTED_MODE` | 현재 브랜치 **로컬 commit만**, push/PR 생략 |

미지원·상충 요청은 사유와 지원 조합을 반환하고 종료한다. 플래그를 버리고 Build로 실행하거나 init/요구사항 질문을 시작하지 않는다. 자동 판정에서도 동일하며, 도메인 확인 질문에는 지원되는 후보만 표시한다.

```bash
python3 -I -B "{PLUGIN_ROOT}/skills/start-workflow/assets/workflow_policy.py" route - <<'JSON'
{"entry":"common","arguments":["--fs","--analyze"],"installed":{}}
JSON
```

입력은 실제 인자의 문자열 배열이다(쉘 eval 금지). `entry`는 `common|be|fe|mm|hd|fs`, 자동 판정 결과는 `detected_domain: be|fe|fs`. `installed`는 세션 메타데이터에서 확인한 논리 역할 `be/fe/mm/hd` → **실제 호출명** 매핑이다. 위 예시는 의도적으로 BLOCKED(exit 1)를 반환하며 actions가 비어 있다. 입력 오류 exit 2도 닫힌 실패다.

- exit 0 `READY`의 `dispatch`만 호출하고 `arguments`를 전달한다. 직접 base 호출에서 dispatch=null은 자신의 모드 절차를 뜻한다. common 미설치 상태에서도 BE/FE에 동봉된 helper가 동작한다.
- `--be/--fe`는 base 스킬을 직접 선택한다. `--mm/--hd`는 해당 설치 오버레이를 강제한다. 자동 선택은 설치 오버레이 → base 순서다. **base 선택은 프로젝트 override 파일을 무효화하지 않는다.** 이미 복사된 overlay-source 규칙도 프로젝트 override이며 플러그인 동적 주입과 중복 적용하지 않는다.
- `--resume`이면 상태를 읽어 `resume_mode`와 boolean `resume_hard`, 저장된 `resume_publish_policy`와 `resume_route_target`(be/fe/mm/hd/fs)을 전달한다. 저장된 유효 정책·선택이 재개 기준이며 BE hard를 push로 새로 도출해 local을 거부하지 않는다. 이 진입 검사는 모드 교차 확인일 뿐이다. READY 뒤에도 `run-lifecycle.md`의 절대 경로·저장소·미완료 검증을 통과해야 재개한다. MODE 충돌은 BLOCKED이며 무시하지 않는다.
- 새 실행의 유효 `publish_policy`와 `route_target`을 `## Flags`의 `PUBLISH_POLICY: pr|push|local|none`, `ROUTE_TARGET: be|fe|mm|hd|fs`로 기록한다. 과거 상태에 없으면 MODE/HARD_MODE로 정책을 도출하고 기존 인계/overlay 기록으로 ROUTE_TARGET을 복원한다. 선택 근거가 없으면 해당 base를 사용했다고 명시하고 자동 wrapper를 새로 삽입하지 않는다. 재개·최종 결정 후에도 이 값이 상한이며 CLI 인자 유실로 다시 결정하지 않는다.
- BE/FE ↔ FS **양방향 전환**은 원래 모드를 `inherited_mode`, 유효 원격 정책을 `inherited_publish_policy`로 전달하고 gate를 다시 실행한다. FS로 전환할 때 기존 단일 도메인 RUN을 fs로 덮어쓰지 않는다. 검증한 source RUN을 인계 기록에 남기고 새 도메인 RUN을 생성한다.
- FS `local`이 BE/FE로 좁아지면 그대로 local이다. BE/FE `push`가 FS로 바뀌면 hard 인자를 잃어도 local로 제한됨을 고지한다. 같은 단일 도메인의 push는 유지한다. 원래 Analyze/Verify를 Build로 바꾸지 않는다. 정책을 확대하는 별도 사용자 지시가 있을 때만 새 범위를 기록한다.
- `PUBLISH_POLICY: local`인 단일 도메인 경로도 PR/Push Phase와 finalization에서 commit만 수행한다. raw `git push`로 hard 플래그를 다시 해석하지 않는다. `none`은 분석/검증 산출물만 허용하며 구현/배포 절차를 경유하지 않는다.

- wrapper → base 위임에는 `inherited_route_target`도 전달한다. base는 이미 선택된 overlay context를 보존하고 자기 절차로 진입하며 wrapper를 재호출하지 않는다. 도메인 자체를 전환할 때는 새 도메인의 선택을 새 ROUTE_TARGET으로 기록한다.
