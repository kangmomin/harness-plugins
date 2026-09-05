import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
LOOP = ROOT / 'be-harness/skills/e2e-test-loop'
RAW = '''# E2E 테스트 실행 리포트 — fixture
> 생성: 2026-09-05T00:00:00Z
> E2E 메인 플로우: create user
> 수준: full

## 테스트 대상 엔드포인트
- `POST /users`

## Iteration 기록
### Iteration 1
#### Happy Path — create user
- 요청: `POST /users` · body: `{}`
- 기대: 201
- 실제: 500
- 판정: ❌ 실패
**실패 → 수정 (create user)**
- 실패 원인: missing name
- 수정: handler.go:3 — use default name
- 귀속: 본 변경 코드
- 재빌드/재시작: 다음 회차에서 수행 예정
'''


class E2EInterruptionTests(unittest.TestCase):
    def test_stop_gate_keeps_executed_records_and_renderer_reports_interruption(self):
        blocks = re.findall(r'```bash\n(.*?)```', (LOOP / 'SKILL.md').read_text(), re.S)
        gate = next(b for b in blocks if 'RENDER_REPORT=false' in b)
        for count in (0, 1):
            for reason in ('SKIPPED:LOCK_TIMEOUT', 'BLOCKED:LOCK_UNAVAILABLE', 'BLOCKED:SERVER_CODE_UNVERIFIED'):
                with self.subTest(count=count, reason=reason), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    raw = root / 'raw.md'
                    raw.write_text(RAW if count else '# E2E 테스트 실행 리포트 — empty\n')
                    env = {**os.environ, 'EXECUTED_ITERATIONS': str(count), 'RUN_REPORT': str(raw), 'STOP_REASON': reason}
                    result = subprocess.run(['bash', '-c', gate + '\nprintf "%s\\n%s\\n" "$LOOP_STATUS" "$RENDER_REPORT"'],
                                            env=env, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    if count == 0:
                        self.assertEqual(result.stdout.splitlines(), [reason, 'false'])
                        self.assertFalse(raw.exists())
                        continue
                    self.assertEqual(result.stdout.splitlines(), ['BLOCKED:INTERRUPTED', 'true'])
                    self.assertTrue(raw.read_text().startswith(RAW))
                    with raw.open('a') as stream:
                        stream.write('\n## 최종 요약\n- 총 iteration: 1회\n- 총 테스트: 1건 (통과 0 / 실패 1)\n- 미해결 이슈: 수정 후 재검증 미실행\n- 커버리지: 없음\n')
                    result = subprocess.run([sys.executable, str(LOOP / 'assets/render_e2e_report.py'), str(raw),
                                             '--out-dir', str(root / 'out'), '--level', 'full', '--status', 'BLOCKED:INTERRUPTED'],
                                            capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    report = Path(result.stdout.splitlines()[0].removeprefix('경로: ')).read_text()
                    self.assertIn('loop_status: BLOCKED:INTERRUPTED', report)
                    self.assertIn('verdict: "아니오"', report)
                    self.assertIn(reason, report)
                    self.assertIn('총 iteration 1회', report)
                    self.assertIn('handler.go:3', report)
                    self.assertIn('INCONCLUSIVE(수정 후 재검증 기록 없음)', report)
                    self.assertTrue(raw.exists())


if __name__ == '__main__':
    unittest.main()
