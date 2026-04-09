# harness-plugins

개발 워크플로우 자동화를 위한 Claude Code 플러그인 모음.

## 설치

```bash
# 마켓플레이스 등록
/plugin marketplace add kangmomin/harness-plugins

# 백엔드 플러그인 설치
/plugin install minmos-harness@harness-plugins

# 프론트엔드 플러그인 설치
/plugin install hyeondongs-harness@harness-plugins
```

## 플러그인 목록

| 플러그인 | 대상 | 설명 |
|---------|------|------|
| **minmos-harness** | Go 백엔드 | 커밋/PR, 컨벤션 검사, E2E 테스트(REST+gRPC), Apidog 스키마 생성 |
| **hyeondongs-harness** | React 프론트엔드 | 컴포넌트 생성, 커밋/PR, 단위/E2E 테스트, 코드 품질 검사(ESLint, a11y) |
