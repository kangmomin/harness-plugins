# FE component generation fixture

`component_templates.py`의 현재 출력으로 매번 임시 프로젝트를 만든다. 산출물 사본을 테스트하지 않는다. 설치와 검증을 분리하며 검증 스크립트는 패키지를 다운로드하지 않는다.

```bash
cd tests/fixtures/fe-components
npm ci --ignore-scripts --no-audit --no-fund
python3 -B verify.py
```

- React(Next.js/Vite/CRA 선택)의 JS/TS × Vitest/Jest, Nuxt-compatible Vue SFC의 JS/TS × Vitest: 14개 조합.
- styled-components, React/Vue CSS Modules 추가 3개. Vitest globals:false, Jest API 명시 import.
- Vite library build, vue-tsc 타입/구문 검사, Vitest 11개와 Jest 6개 실제 콘텐츠 렌더 테스트. Storybook metadata는 타입 검사에 포함한다.
- Vue/Jest는 프로젝트별 SFC transform이 필요하므로 기본 generator가 출력 전 거부한다. 미지원 조합은 성공으로 세지 않는다.

관측 버전·실행 환경·조합별 결과는 `observed.json`에 있다. 이는 프레임워크에 종속되지 않는 컴포넌트 검증이다. Next/Nuxt/CRA **앱 전체·라우터·SSR 통합 또는 Storybook 브라우저 빌드**를 실행한 결과는 아니다. 실제 프로젝트에서는 해당 build/test 명령을 추가로 수행한다. 고정된 버전 표본을 모든 최신 버전의 호환 보장으로 해석하지 않는다.

템플릿 계약 참고: [Vue SFC script setup](https://vuejs.org/api/sfc-script-setup.html), [Vue component testing](https://vuejs.org/guide/scaling-up/testing.html), [Vitest explicit test imports](https://vitest.dev/guide/). 사용한 버전은 fixture lockfile로 고정하며 문서 사이트의 현재 버전과 별도로 기록한다.
