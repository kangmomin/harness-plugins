> 품질 검사·리뷰·Read-back의 공통 범위 계약. assets/workflow_scope.py가 실행 정본이다.

# 범위

워크플로우에서는 구현 직전 고정한 `START_SHA`부터 현재 작업 트리까지의 변경을 쓴다. 이미 커밋한 구현, staged, unstaged를 합치고 **실행 소유가 확인된 untracked**를 포함한다. dirty 여부로 기준 SHA를 바꾸지 않는다.

```bash
python3 -I -B "{PLUGIN_ROOT}/skills/start-workflow/assets/workflow_scope.py" \
  --cwd "{CWD}" --start-sha "{START_SHA}" --owned-files "{OWNED_FILES}" --out "{RUN_DIR}/scope.json"
```

- `{OWNED_FILES}`는 root-relative JSON 문자열 배열이다. run 생성 시 `[]`, 이후 오케스트레이터가 Plan·각 구현/수정 결과에서 확인한 파일만 합친다. 기존 사용자 파일을 단순 untracked라는 이유로 소유 목록에 추가하지 않는다. resume은 기존 목록을 보존하며 유실 시 구현 기록에서 복구한다.
- 명령 exit 0일 때만 현재 artifact를 소비한다. 실패하면 `BLOCKED:REVIEW_SCOPE`, 옛 artifact를 재사용하거나 빈 목록 PASS로 처리하지 않는다. 모든 writer가 끝난 배리어에서 수집하고 각 수정 후 다시 수집한다. Git 변경 중 atomic snapshot을 보장하는 helper는 아니다.
- `paths`는 전체 대상, `read`는 현재 일반 파일, `deleted`는 삭제 영향, `symlinks`는 링크 자체다. symlink 대상은 자동으로 읽지 않는다. root와 경로를 결합하며 현재 디렉터리를 붙여 해석하지 않는다.
- `patch`와 `index_patch`를 함께 본다. worktree가 원래 내용으로 돌아와도 index만 다른 변경은 숨기지 않는다. index/worktree 내용이 다르면 commit할 내용과 실제 검증한 내용을 구분한다.
- 소스/테스트/컴포넌트 필터는 이 목록에 적용한다. FE는 .tsx만 고정하지 않고 선택 framework·언어에 따라 .jsx/.vue/.js/.ts를 포함한다. 삭제 파일은 Read하지 않고 diff로 검토한다.
- 단독 호출은 호출자가 지정한 SHA 또는 **명시적으로 결정한 base ref**의 merge-base를 쓴다(`--start-sha` 대신 `--base-ref`). base가 없으면 먼저 기존 PR base·프로젝트 mainBranch·origin/HEAD를 근거로 결정한다. 동일 feature upstream을 PR base로 추정하지 않는다. 미해결은 BLOCKED이며 HEAD로 대체하지 않는다.
- Read-back 부모는 여기서 소스를 선정해 **명시 파일 목록만** 자식에게 전달한다. 자식은 main/base를 다시 추론하지 않는다. Spec·Plan·상태·Test Map 격리는 유지한다. 같은 브랜치에 직접 커밋하는 --hard도 START_SHA를 사용하므로 범위가 사라지지 않는다.

# 검증 이후 변경

검증 전후 `workflow_results.py tree --cwd "{CWD}"`를 비교하고 동일할 때 해당 이벤트에 `tested_tree`를 기록한다. 코드가 수정되거나 의도하지 않은 HEAD 이동이 있으면 해당 검증을 다시 수행한다. 범위 helper의 `content_sha256`은 index도 포함한 리뷰 범위 해시이며 result의 `tested_tree.content_sha256`과 다른 필드다. 두 해시를 대신 사용하지 않는다.
