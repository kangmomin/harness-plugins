# 하네스 회귀 검증

저장소 루트에서 실행한다. Python·Bash·Node.js 외 추가 패키지는 필요하지 않다.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
node --test work-log/tests/*.test.js
bash scripts/check-plugins.sh
```

Python 테스트는 실행 간 상태/락 격리, Go 패키지별 실패·재실행 대조, 실제 FE 빌드/타입 체크 지침의 exit code를 검증한다. Node 테스트는 work-log MCP 연결과 YAML 메타데이터 보존·태그 인덱싱을 검증한다. 구조 검사는 스킬 길이·앵커·공통 스크립트/참조 사본의 일치를 확인한다.
