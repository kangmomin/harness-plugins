# SessionStart worktree hook 계약

`assets/worktree_init.py`가 설치와 복사를 담당한다. Linux/macOS Python 3.9+의 descriptor I/O, advisory flock과 권한 보존을 사용한다. 실행 중 package 다운로드는 없다. Codex의 native hook 지원으로 표시하지 않는다.

## 설치

- 실제 settings 경로를 `install --settings PATH`로 명시한다. 파일이 없으면 빈 JSON 객체에서 시작하고 새 파일은 exclusive publish한다. 유효하지 않은 JSON/중복 키/잘못된 hooks 구조는 변경 전 BLOCKED다.
- 기존 `hooks.SessionStart` 및 다른 hook/permissions/설정 값을 보존하며, 같은 버전 재설치는 settings bytes를 바꾸지 않는다. 새 항목은 공식 SessionStart command 형식이다. [Claude hooks](https://code.claude.com/docs/en/hooks#sessionstart)
- hook은 `hooks/minmos-worktree-init-<content hash>/`에 script+metadata helper bundle로 설치한다. 기존 사용자 script를 덮어쓰지 않는다. 검증된 자기 bundle의 정확한 command만 갱신하며 다른 hook을 삭제하지 않는다. 이전 bundle은 기존 세션이 참조할 수 있어 자동 일괄 삭제하지 않는다.
- 기존 `worktree-init.sh` 등록이 있으면 새 설치를 중단한다. 구 hook을 보존한 채 두 개를 켜면 구 코드가 ignore 확인 없이 복사하므로 migration 완료가 아니다. 요청된 migration에서는 기존 command/script를 읽고 정확한 등록 제거 diff를 준비한다. 사용자 작성 hook은 임의 제거하지 않는다.
- settings mode/uid/gid/xattrs와 ACL을 보존한다. metadata 코드는 `work-log`에서 검증한 `Metadata`와 class byte parity를 검사한다. Linux mode/xattrs는 fixture로 검증하고 Darwin ACL은 동일 native API 경계를 사용하되 이 환경에서는 실제 macOS 검증을 하지 않았다. 보존 API가 실패하면 쓰기를 중단한다.
- 설치 lock은 같은 디렉터리의 `.minmos-worktree-init.lock`이며 나이로 삭제하지 않는다. 설정 temp는 실행별 exclusive이며 publish 직전 inode/bytes를 재검증하고 자기 inode만 정리한다. publish 뒤 destination inode/bytes가 다르면 UNKNOWN:PUBLISH로 보고하고 원본 복원으로 다른 writer를 덮지 않는다. UNKNOWN에서는 참조 여부가 불명확한 bundle도 보존한다. 기존 파일은 replace 직전 inode/크기/mtime/ctime/mode/소유자를 다시 대조하고 변경 시 BLOCKED다. 비협조적인 외부 editor와 모든 시점의 compare-and-swap을 보장한다고 하지 않는다. 첫 설치는 exclusive link여서 다른 최초 writer의 settings를 덮어쓰지 않는다.

## 실행과 복사

- SessionStart JSON의 실제 cwd에서 Git root를 구하고 `git worktree list --porcelain -z`로 main 경로 전체를 읽는다. 공백/한글 경로와 중첩 cwd를 지원한다. main에서는 복사하지 않으며 bare main/확인 불가 대상은 BLOCKED다.
- 허용 대상은 `.mcp.json`, `.env`, `secret/.env`, `secret/gcp-sa-key.json` 네 파일뿐이다. source가 없으면 경로별 SOURCE_MISSING을 보고하고 필요한 환경이 준비됐다고 하지 않는다.
- source와 destination 경로 모두 `git ls-files -z -- PATH`가 비어 있고 `git check-ignore --quiet -- PATH`가 성공해야 한다. root `.env`가 ignore됐다는 이유로 `secret/.env`도 그렇다고 가정하지 않는다. tracked secret은 자동 복사/추적 해제하지 않는다.
- 기존 destination(심볼릭 링크 포함)은 덮어쓰지 않는다. source와 모든 parent는 no-follow descriptor로 읽고 경로/inode 변화를 확인한다. 새 파일은 완성된 bytes를 exclusive publish하며 0600으로 제한하고, 새 secret 디렉터리는 0700이다. 비밀 값은 출력하지 않는다.
- 결과의 copied/skipped 경로 목록과 실제 대상 파일·Git ignore 상태를 대조한다. 환경 파일 복사 자체는 앱/MCP DB identity 검증을 대신하지 않는다. E2E의 필수 DB 게이트를 계속 수행한다.

검증은 임시 Git 저장소와 설치 경로에서 실제 등록 command에 SessionStart JSON을 전달한다. 실제 Claude loader가 hook을 실행했다고 주장하지 않는다. 설치 실패 시 기존 settings와 다른 writer 파일을 보존하고 자기 임시 파일/미등록 bundle만 정리한다.

게시와 검증이 완료된 뒤 자기 임시 파일 정리만 실패하면 `INSTALLED`/`UNCHANGED`와 `cleanup_warnings`를 함께 보고한다. 저장 실패로 재설치하지 않고 해당 임시 경로만 소유권을 확인해 정리한다. 게시 이후 내구성 또는 내용 검증 실패는 `UNKNOWN:PUBLISH`로 구분한다.
