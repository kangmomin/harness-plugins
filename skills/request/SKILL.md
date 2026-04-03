---
name: request
description: "기능 단위 요청을 구조화된 Technical Spec으로 변환. PRD 대신 'Where & How' 중심의 콤팩트한 기능 명세를 생성한다."
allowed-tools: AskUserQuestion, Read, Glob, Grep, Agent
argument-hint: <기능 설명 또는 요청>
user-invocable: true
---

# Feature Spec Generator

기능 단위 요청을 받아, 기존 코드베이스와의 연결고리를 명확히 짚는 **실행 가능한 기능 명세서**를 생성한다.

## 핵심 철학

- **"What" 보다 "Where & How"**: 무엇을 만들지보다, 어디에 어떻게 얹을지를 명확히 한다.
- **기존 코드 우선**: 중복 코드를 만들지 않도록, 반드시 기존 구조를 파악한 후 명세를 작성한다.
- **콤팩트하게**: PRD가 아닌 Technical Spec. 실행에 필요한 정보만 담는다.

---

## Workflow

### Phase 1: 요청 수신 및 초기 분석

1. `$ARGUMENTS`에서 기능 요청을 확인한다. 비어있으면 `AskUserQuestion`으로 어떤 기능을 추가/수정하려는지 질문한다.
2. 요청에서 **핵심 키워드**를 추출한다 (도메인명, 엔티티명, API 경로 등).

### Phase 2: 코드베이스 탐색 (Context Discovery)

기능 요청의 키워드를 기반으로 기존 코드를 탐색한다. **코드를 짜기 전에 반드시 기존 구조를 파악하는 것이 목적이다.**

#### 탐색 대상

```
1. CLAUDE.md          → 프로젝트 컨벤션, 아키텍처 패턴
2. Handler (rest/)    → 기존 API 엔드포인트, Request/Response 구조
3. Usecase            → 비즈니스 로직 패턴, 인터페이스 시그니처
4. Repository         → 데이터 접근 패턴, Entity 구조
5. Domain (domain/)   → VO, Command, Domain Error
6. DI (cmd/setup/)    → 의존성 주입 구조
7. Errcode            → 기존 에러 코드 패턴
8. Migration          → DB 스키마 현황
```

#### 탐색 방법

- `Glob`으로 관련 파일 패턴 검색 (e.g., `internal/**/*{keyword}*`)
- `Grep`으로 관련 키워드/함수/타입 검색
- `Read`로 핵심 파일 내용 확인
- 유사 기능이 이미 구현된 파일을 **참조 구현(Reference Implementation)**으로 식별

#### 탐색 결과 정리

```markdown
## Context Discovery 결과

### 관련 기존 파일
- `path/to/file.go` - [역할 설명]

### 참조 구현 (유사 기능)
- `path/to/similar.go` - [이 기능과 유사한 점]

### 재사용 가능한 코드
- `패키지.함수명` - [활용 방법]

### 영향받는 기존 코드
- `path/to/affected.go:라인` - [수정이 필요한 이유]
```

### Phase 3: 구조화된 질문 (Gap Filling)

탐색 결과를 바탕으로, 명세 작성에 부족한 정보를 `AskUserQuestion`으로 채운다.

**질문 원칙:**
- **한 번에 하나씩** 질문한다
- 탐색에서 발견한 내용을 공유하며 질문한다 ("기존에 X가 있는데, 이걸 활용할까요?")
- 코드베이스에서 답을 유추할 수 있으면 질문하지 않는다

**질문 우선순위 (부족한 것만 질문):**

1. **Input/Output**: 어떤 데이터를 받고 어떤 결과를 내야 하는가?
   - Request/Response 필드 구성
   - 성공/실패 시 기대 동작
2. **Constraint**: 제약 조건
   - 기존 코드/라이브러리 외 새로 추가할 것이 있는가?
   - 성능 요구사항, 권한 제어 등
3. **Edge Case**: 예외 상황
   - 데이터 없음, 중복, 권한 부족 시 동작
   - 비즈니스 규칙 상 특수한 케이스
4. **Test Plan**: 검증 방법
   - 단위 테스트 범위, E2E 필요 여부

### Phase 4: Feature Spec 생성

수집된 정보를 아래 템플릿으로 구조화하여 출력한다.

---

## Output Template

```markdown
# Feature Spec: [기능명]

## 1. 기능 목표
[한 문장으로 정의. "~하면 ~해야 한다" 형식]

## 2. 현재 상황 (As-Is)
[기존에 어떤 파일들이 있고 어떻게 동작하는지]

### 관련 기존 파일
| 파일 | 역할 | 수정 필요 |
|------|------|----------|
| `path/to/file.go` | [역할] | Yes/No |

### 참조 구현
- `path/to/similar.go` → [이 패턴을 따라서 구현]

## 3. 변경 사항 (To-Be)

### 3.1 새로 생성할 파일
| 파일 | 용도 |
|------|------|
| `internal/domain/xxx_vo.go` | VO/Command 정의 |

### 3.2 수정할 기존 파일
| 파일 | 변경 내용 |
|------|----------|
| `internal/repository/interfaces.go` | Repository 인터페이스 추가 |
| `internal/repository/uow.go` | UoW 팩토리 메서드 추가 |
| `cmd/setup/handler.go` | DI 등록 |

### 3.3 API 엔드포인트
| Method | Path | 설명 | 인증 |
|--------|------|------|------|
| POST | /v1/xxx | 생성 | Required |

### 3.4 비즈니스 로직
[핵심 로직을 간결하게 기술]
- 조건 A이면 → 동작 X
- 조건 B이면 → 동작 Y

## 4. Input/Output

### Request
| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| name | string | Y | 이름 |

### Response
| 필드 | 타입 | 설명 |
|------|------|------|
| id | int | 생성된 ID |

## 5. 제약 사항 (Constraints)
- [기존 코드/패턴 관련 제약]
- [성능/보안 제약]

## 6. 엣지 케이스
| 케이스 | 기대 동작 | HTTP |
|--------|----------|------|
| 데이터 없음 | 404 반환 | 404 |

## 7. DB 변경 (해당 시)
- [ ] 새 테이블: [테이블명]
- [ ] 컬럼 추가: [테이블.컬럼]
- [ ] 인덱스: [설명]

## 8. 구현 체크리스트
- [ ] Domain VO/Command
- [ ] Entity
- [ ] Repository 인터페이스 + 구현
- [ ] UoW 팩토리 메서드
- [ ] Usecase 인터페이스 + 구현
- [ ] Handler + 라우트
- [ ] DI 등록 (cmd/setup/handler.go)
- [ ] 에러 코드 등록 (errcode.go)
- [ ] DDL 마이그레이션 (해당 시)
- [ ] 테스트
```

---

## 중요 원칙

1. **탐색 없이 명세를 작성하지 않는다** - Phase 2를 건너뛰지 않는다.
2. **유추한 내용은 `[Assumption]` 태그를 붙인다** - 사용자에게 확인을 구한다.
3. **기존 패턴을 존중한다** - 참조 구현과 다른 방식을 제안할 때는 이유를 명시한다.
4. **실행 가능한 수준으로** - 이 명세만 보고 바로 구현에 들어갈 수 있어야 한다.
5. **불필요한 섹션은 생략한다** - DB 변경이 없으면 섹션 7을 빼는 식으로, 해당하는 것만 포함한다.
