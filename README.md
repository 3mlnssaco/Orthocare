# OrthoCare

> 근거 기반 무릎 진단 및 운동 추천 AI 시스템 (V3 - 마이크로서비스 아키텍처)

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [V3 아키텍처](#2-v3-아키텍처---마이크로서비스-분리)
3. [프로젝트 구조](#3-프로젝트-구조)
4. [파이프라인 상세](#4-파이프라인-상세)
5. [데이터 구조](#5-데이터-구조)
6. [API 엔드포인트](#6-api-엔드포인트)
7. [사후 평가 시스템](#7-사후-평가-시스템-rpe-기반)
8. [설치 및 실행](#8-설치-및-실행)
9. [평가 결과](#9-평가-결과)
10. [기술 스택](#10-기술-스택)

---

## 1. 프로젝트 개요

OrthoCare는 자연어 증상 입력을 분석하여 무릎 통증의 원인을 진단하고, 의학 논문 근거에 기반한 맞춤형 운동 프로그램을 추천하는 AI 시스템입니다.

### 핵심 기능

- **3-Layer 근거 검색**: 검증된 논문 → OrthoBullets → PubMed 순으로 신뢰도 높은 근거 우선 제공
- **버킷 기반 진단**: 4가지 카테고리(OA/OVR/TRM/INF)로 무릎 통증 분류
- **Anti-Hallucination**: LLM이 실제 검색된 문서만 인용 (가짜 논문 인용 방지)
- **맞춤형 운동 추천**: 진단 결과와 신체 상태에 따른 운동 프로그램 생성
- **사후 평가 반영**: RPE 기반 피드백으로 다음 세션 난이도 자동 조정

### 버킷 분류 체계

| 버킷 | 의미 | 주요 특징 | 예시 |
|------|------|----------|------|
| **OA** | Osteoarthritis (퇴행성) | 만성, 진행성, 아침 뻣뻣함 <30분 | 골관절염, 연골 마모 |
| **OVR** | Overuse (과사용) | 활동 후 악화, 반복적 동작 | 러너스니, 슬개대퇴 증후군 |
| **TRM** | Trauma (외상) | 급성 발병, 외상 이력 | ACL 손상, 반월판 파열 |
| **INF** | Inflammatory (염증) | 붓기, 열감, 전신 증상 | 화농성 관절염, 통풍 |

### 핵심 원칙

- **Fail-fast**: 오류 발생 시 즉시 드러내고 해결 (조용한 폴백 금지)
- **실제 근거 인용**: LLM 응답에서 벡터 DB 검색 결과만 인용 (hallucination 금지)
- Body-part 네임스페이스 분리 (무릎 → 어깨 → 전신 확장)

---

## 2. V3 아키텍처 - 마이크로서비스 분리

### 분리 배경

| 문제점 | 해결책 |
|--------|--------|
| 버킷 추론(2주 1회)과 운동 추천(매일)이 통합 | 독립 Docker 컨테이너로 분리 |
| 매일 운동 추천 시 불필요한 버킷 추론 비용 | 필요할 때만 버킷 추론 호출 |
| 벡터 DB 통합으로 검색 정확도 저하 | 진단용 / 운동용 벡터 DB 분리 |

### 서비스 구성

```
┌─────────────────────────────────────────────────────────────────┐
│                    OrthoCare V3 Architecture                    │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────┐         ┌──────────────────────────┐
│  bucket_inference    │         │ exercise_recommendation  │
│  (Docker :8001)      │         │  (Docker :8002)          │
├──────────────────────┤         ├──────────────────────────┤
│ • 버킷 추론            │         │ • 운동 추천                 │
│ • 2주 1회 호출         │  ────▶  │ • 매일 호출                 │
│ • 벡터DB: diagnosis   │         │ • 벡터DB: exercise        │
└──────────────────────┘         └──────────────────────────┘
         │                                │
         └────────────┬───────────────────┘
                      ▼
              ┌──────────────┐
              │   shared/    │
              │ 공통 모듈      │
              └──────────────┘
```

| 서비스 | 포트 | 빈도 | 벡터 DB |
|--------|------|------|---------|
| **bucket_inference** | 8001 | 2주 1회 | orthocare-diagnosis |
| **exercise_recommendation** | 8002 | 매일 | orthocare-exercise |

### 벡터 DB 분리

| 인덱스 | 용도 | 소스 |
|--------|------|------|
| `orthocare-diagnosis` | 버킷 추론 | verified_paper, orthobullets, pubmed |
| `orthocare-exercise` | 운동 추천 | exercise |

---

## 3. 프로젝트 구조

```
Orthocare/
├── bucket_inference/               # 버킷 추론 서비스
│   ├── main.py                     # FastAPI 엔트리포인트 (:8001)
│   ├── config/settings.py          # 설정 (PINECONE_INDEX=orthocare-diagnosis)
│   ├── models/
│   │   ├── input.py                # BucketInferenceInput
│   │   └── output.py               # BucketInferenceOutput
│   ├── services/
│   │   ├── weight_service.py       # 가중치 계산
│   │   ├── evidence_search.py      # 벡터 검색 (논문/가이드라인)
│   │   ├── ranking_merger.py       # 랭킹 통합
│   │   └── bucket_arbitrator.py    # LLM 버킷 중재
│   ├── pipeline/
│   │   └── inference_pipeline.py   # 버킷 추론 파이프라인
│   └── Dockerfile
│
├── exercise_recommendation/        # 운동 추천 서비스
│   ├── main.py                     # FastAPI 엔트리포인트 (:8002)
│   ├── config/settings.py          # 설정 (PINECONE_INDEX=orthocare-exercise)
│   ├── models/
│   │   ├── input.py                # ExerciseRecommendationInput
│   │   ├── output.py               # ExerciseRecommendationOutput
│   │   └── assessment.py           # 사전/사후 평가 모델
│   ├── services/
│   │   ├── assessment_handler.py   # 사후설문 처리 (핵심!)
│   │   ├── exercise_filter.py      # 버킷 기반 필터링
│   │   ├── personalization.py      # 개인화 조정
│   │   └── recommender.py          # LLM 운동 추천
│   ├── pipeline/
│   │   └── recommendation_pipeline.py
│   └── Dockerfile
│
├── shared/                         # 공유 모듈
│   ├── models/
│   │   ├── demographics.py         # Demographics 모델
│   │   └── body_part.py            # BodyPartInput 모델
│   └── utils/
│       ├── logging.py
│       └── pinecone_client.py      # Pinecone 공통 클라이언트
│
├── data/                           # 데이터
│   ├── medical/knee/
│   │   ├── papers/                 # 논문 (PDF + 청크)
│   │   │   ├── original/           # 원본 PDF
│   │   │   ├── processed/          # 청크 처리된 JSON
│   │   │   └── paper_metadata.json # 논문별 버킷/소스 메타데이터
│   │   └── guidelines/
│   ├── exercise/knee/
│   │   └── exercises.json          # 운동 라이브러리 (50개)
│   ├── crawled/
│   │   └── orthobullets_cache.json # OrthoBullets 교육 자료 (5개)
│   └── clinical/knee/
│       ├── weights.json
│       ├── buckets.json
│       ├── red_flags.json
│       └── symptom_mapping.json
│
├── scripts/
│   ├── index_diagnosis_db.py       # 진단용 벡터 DB 인덱싱
│   └── index_exercise_db.py        # 운동용 벡터 DB 인덱싱
│
├── docs/knee/                      # 무릎 관련 문서
│   ├── form_v1.1.md                # 설문 양식
│   └── weights_v1.1.md             # 가중치 정의
│
└── docker-compose.yml              # Docker 오케스트레이션
```

---

## 4. 파이프라인 상세

### 전체 흐름

```
┌─────────────────────────────────────────────────────────────────┐
│ Phase 1: 입력 처리                                                 │
├─────────────────────────────────────────────────────────────────┤
│ 1-1. 입력 검증                                                    │
│ 1-2. 레드플래그 체크 (부위별 룰)                                       │
│ 1-3. 설문 → 증상 코드 매핑 (테이블 기반, LLM 없음)                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Phase 2: 진단 (병렬 처리)                                           │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐              ┌─────────────────┐           │
│  │ 경로 A: 가중치     │              │ 경로 B: 벡터검색    │           │
│  │ weights.json    │              │ 의미 기반 검색      │           │
│  └────────┬────────┘              └────────┬────────┘           │
│           └───────────────┬────────────────┘                    │
│                           ↓                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ LLM Pass #1 — 버킷 검증/정당화                              │    │
│  │ • 두 경로 결과 비교, 불일치 감지 시 재검토                        │    │
│  │ • Output: 최종 버킷 + 신뢰도 + 근거 설명                       │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Phase 3: 운동 처방                                                │
├─────────────────────────────────────────────────────────────────┤
│ 3-1. 버킷 기반 운동 필터링                                           │
│ 3-2. LLM Pass #2 — 운동 추천                                      │
│      Input: 버킷 + 근거 + 신체점수 + NRS + 금기조건                    │
│      Output: 운동 5~7개 + 추천 이유                                 │
│ 3-3. 루틴 구성 (순서, 세트/렙/휴식)                                    │
└─────────────────────────────────────────────────────────────────┘
```

### 병렬 검색 전략 (가중치 + 벡터)

**문제**: 가중치만 믿으면 오류 시 전체가 틀어짐
**해결**: 두 경로 병렬 실행 → LLM이 비교 판단

```python
# 경로 A: 규칙 기반
weight_scores = {"OA": 15, "OVR": 8, "TRM": 3, "INF": 2}

# 경로 B: 의미 기반 검색
search_results = [
    {"bucket": "OA", "count": 5},
    {"bucket": "TRM", "count": 3},  # 가중치와 불일치!
]

# LLM에 둘 다 전달 → 불일치 감지 시 재검토 후 최종 결정
```

### 근거 검색 계층 (Evidence Layers)

| Layer | 소스 타입 | 신뢰도 |
|-------|----------|--------|
| **1** | verified_paper | 최상 |
| **2** | orthobullets | 상 |
| **3** | pubmed | 중 (미검증) |

**현재 벡터 DB 현황**:
```
총 벡터 수: 875개
├── verified_paper: 47개 (검증된 논문 청크)
├── pubmed: 40개 (PubMed 논문 청크)
├── orthobullets: 5개 (OrthoBullets 교육 자료)
└── exercise: 50개 (운동 데이터)
```

### LLM 인용 규칙 (Anti-Hallucination)

```
## 인용 규칙 (매우 중요)
- 벡터 DB 검색 결과에 있는 문서만 인용
- 존재하지 않는 논문/가이드라인 생성 금지
- 인용 형식: "제목" [source] - "관련 내용"
```

---

## 5. 데이터 구조

### 논문 메타데이터 (`paper_metadata.json`)

```json
{
  "papers": {
    "duncan2008": {
      "title": "Pain and Function in Knee Osteoarthritis (Duncan 2008)",
      "buckets": ["OA"],
      "source_type": "verified_paper",
      "evidence_level": "Level II",
      "year": 2008
    }
  }
}
```

### OrthoBullets 캐시 (`orthobullets_cache.json`)

| 토픽 | 버킷 | 내용 |
|------|------|------|
| knee_oa_overview | OA | 무릎 골관절염 |
| acl_injury | TRM | 전방십자인대 손상 |
| meniscus_tear | TRM | 반월판 파열 |
| patellofemoral_syndrome | OVR | 슬개대퇴 증후군 |
| septic_arthritis | INF | 화농성 관절염 |

### 벡터 DB 메타데이터 스키마

```python
metadata = {
    "body_part": "knee",           # 필수
    "source": "verified_paper",    # verified_paper, orthobullets, pubmed, exercise
    "bucket": "OA,TRM",            # 버킷 태그 (쉼표 구분)
    "title": "논문 제목",
    "text": "청크 텍스트 내용...",
    "year": 2008,
    "url": "https://..."
}
```

---

## 6. API 엔드포인트

### 버킷 추론 (Port 8001)

```bash
POST /api/v1/infer-bucket
```

**Request:**
```json
{
  "demographics": {
    "age": 55,
    "sex": "female",
    "height_cm": 160,
    "weight_kg": 65
  },
  "body_parts": [{
    "code": "knee",
    "symptoms": ["pain_bilateral", "chronic", "stairs_down", "stiffness_morning"]
  }],
  "natural_language": {
    "chief_complaint": "양쪽 무릎이 아프고 계단 내려갈 때 힘들어요"
  }
}
```

**Response:**
```json
{
  "body_part": "knee",
  "final_bucket": "OA",
  "confidence": 0.85,
  "bucket_scores": {
    "OA": 15.0,
    "OVR": 4.0,
    "TRM": 0.0,
    "INF": 2.0
  },
  "evidence_summary": "OARSI 가이드라인에 따르면...",
  "inferred_at": "2025-12-05T12:00:00"
}
```

### 운동 추천 (Port 8002)

```bash
POST /api/v1/recommend-exercises
```

**Request:**
```json
{
  "user_id": "user_001",
  "body_part": "knee",
  "bucket": "OA",
  "physical_score": {
    "level": "C",
    "total_score": 9
  },
  "demographics": {
    "age": 55,
    "sex": "female"
  },
  "nrs": 5,
  "previous_assessments": [
    {"session": 1, "rpe_difficulty": 3, "rpe_muscle": 3, "rpe_sweat": 2}
  ]
}
```

**Response:**
```json
{
  "exercises": [
    {
      "id": "ex_001",
      "name_kr": "힐 슬라이드",
      "sets": 2,
      "reps": "10회",
      "rest_sec": 30,
      "reason": "ROM 개선에 효과적"
    }
  ],
  "total_duration_min": 15,
  "difficulty_level": "low",
  "assessment_status": "normal",
  "adjustments_applied": {"difficulty": 0, "reps": 0}
}
```

---

## 7. 사후 평가 시스템 (RPE 기반)

### 신체 점수 시스템

**사전 평가 (4문항, 각 1~4점):**

| 레벨 | 점수 범위 | 운동 개수 | 난이도 |
|------|----------|----------|--------|
| **D** | 4-7점 | 3개 | low |
| **C** | 8-10점 | 4개 | low-medium |
| **B** | 11-13점 | 5개 | medium |
| **A** | 14-16점 | 6개 | medium-high |

### 사후 평가 (RPE 3문항)

| 문항 | 점수 범위 | 조정 대상 |
|------|----------|----------|
| 운동 난이도 체감 | 1-5 | 난이도, 세트 수 |
| 근육 자극 정도 | 1-5 | 반복 수 (렙) |
| 땀 배출량 | 1-5 | 운동 개수 |

### 난이도 조정 로직

```
3세션 RPE 합계:
- 합계 ≤ 6: 너무 쉬움 → 난이도 상향
- 합계 7-11: 적정 → 유지
- 합계 ≥ 12: 너무 힘듦 → 난이도 하향
```

### AssessmentHandler 케이스 처리

```python
# 케이스별 처리:
# 1. fresh_start: 최초 운동 (사전 평가만 사용)
# 2. normal: 정상 운동 (이전 기록 반영, 3세션 완료 시 조정)
# 3. reset: 오랜만 (7일+) 또는 기록 손실 (리셋)

handler = AssessmentHandler()
result = handler.process(
    previous_assessments=previous_assessments,
    last_assessment_date=last_date,
)
# result.status: "fresh_start" | "normal" | "reset"
```

---

## 8. 설치 및 실행

### 환경 설정

```bash
# 저장소 클론
git clone https://github.com/3mlnssaco/Orthocare.git
cd Orthocare

# 환경변수 설정
cp .env.example .env
# .env 파일에 API 키 입력
```

### 필수 환경변수

```bash
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=...
```

### Docker로 실행

```bash
# 전체 서비스 시작
docker-compose up -d

# 개별 서비스 실행
docker-compose up bucket-inference      # 버킷 추론만
docker-compose up exercise-recommendation  # 운동 추천만

# 로그 확인
docker-compose logs -f
```

### 로컬 개발

```bash
# 가상환경 생성
python -m venv .venv
source .venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# 버킷 추론 서비스 실행
cd bucket_inference && uvicorn main:app --reload --port 8001

# 운동 추천 서비스 실행 (새 터미널)
cd exercise_recommendation && uvicorn main:app --reload --port 8002
```

### 벡터 DB 인덱싱

```bash
# 진단용 벡터 DB 인덱싱
PYTHONPATH=. python scripts/index_diagnosis_db.py

# 운동용 벡터 DB 인덱싱
PYTHONPATH=. python scripts/index_exercise_db.py
```

---

## 9. 평가 결과

### 최신 평가 결과 (2025-11-29)

**전체 성능:**
- 총 케이스: 20개
- 통과: 19개
- 실패: 1개
- **정확도: 95.0%**

**버킷별 정확도:**

| 버킷 | 총 케이스 | 정확 | 정확도 |
|------|----------|------|--------|
| OA | 6 | 5 | 83.3% |
| OVR | 5 | 5 | 100.0% |
| TRM | 5 | 5 | 100.0% |
| INF | 2 | 2 | 100.0% |
| RED_FLAG | 2 | 2 | 100.0% |

### 테스트 페르소나

| Persona | 나이 | 증상 | 예상 버킷 |
|---------|------|------|----------|
| 1 | 55 | 무릎 통증, 아침 뻣뻣함, 계단 오르기 어려움 | OA |
| 2 | 28 | ACL 부상 후 불안정감, 운동 중 손상 | TRM |
| 3 | 35 | 달리기 후 무릎 앞쪽 통증, 앉았다 일어날 때 악화 | OVR |

---

## 10. 기술 스택

| 항목 | 기술 |
|------|------|
| **LLM** | OpenAI GPT-4o-mini |
| **벡터 DB** | Pinecone (3072차원, text-embedding-3-large) |
| **프레임워크** | FastAPI, Pydantic |
| **컨테이너** | Docker, Docker Compose |
| **언어** | Python 3.11+ |

### 결정 사항

| 항목 | 결정 |
|------|------|
| 무릎 버킷 수 | 4개 (OA/OVR/TRM/INF) |
| 벡터 DB | Pinecone (서버리스, 3072차원) |
| 임베딩 모델 | text-embedding-3-large (OpenAI) |
| 최소 유사도 | 0.35 (검색 결과 필터링) |
| OrthoBullets | 크롤링 불가 → 수동 큐레이션 |
| LLM 인용 | 검색된 문서만 (hallucination 금지) |

---

## 버전 히스토리

| 브랜치 | 설명 |
|--------|------|
| `main` | V3 마이크로서비스 아키텍처 (현재) |
| `v1-unified-model` | V1 통합 파이프라인 (레거시) |

---




## 기여

이슈 및 PR 환영합니다.
