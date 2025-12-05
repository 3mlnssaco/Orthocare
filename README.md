# OrthoCare

> 근거 기반 무릎 진단 및 운동 추천 AI 시스템 (V3 - 마이크로서비스 아키텍처)

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [V3 아키텍처](#2-v3-아키텍처---마이크로서비스-분리)
3. [프로젝트 구조](#3-프로젝트-구조)
4. [파이프라인 상세](#4-파이프라인-상세)
5. [데이터 구조](#5-데이터-구조)
6. [운동 데이터베이스 스키마 및 추천 알고리즘](#6-운동-데이터베이스-스키마-및-추천-알고리즘)
7. [API 엔드포인트](#7-api-엔드포인트-상세)
8. [사후 평가 시스템](#8-사후-평가-시스템-rpe-기반)
9. [설치 및 실행](#9-설치-및-실행)
10. [평가 결과](#10-평가-결과)
11. [기술 스택](#11-기술-스택)

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
         │                                     │
         └───────────-----─┬───────────────────┘
                           ▼
                   ┌──────────────┐
                   │    shared/   │
                   │    공통 모듈   │
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

## 6. 운동 데이터베이스 스키마 및 추천 알고리즘

### 6.1 운동 데이터 스키마

운동 데이터는 `data/exercise/{body_part}/exercises.json`에 저장됩니다.

#### 현재 구현된 필드

```json
{
  "E01": {
    "name_en": "Heel Slide",
    "name_kr": "힐 슬라이드",
    "difficulty": "low",
    "diagnosis_tags": ["INF", "TRM"],
    "function_tags": ["Mobility"],
    "target_muscles": ["햄스트링", "대퇴사두근"],
    "sets": 2,
    "reps": "15회",
    "rest": "30초",
    "description": "누워서 발꿈치를 엉덩이 쪽으로 미끄러뜨려 무릎 가동범위 회복",
    "youtube": "https://youtu.be/Er-Fl_poWDk"
  }
}
```

#### 필드 상세 설명

| 필드 | 타입 | 필수 | 설명 | 임상적 근거 |
|------|------|------|------|------------|
| **code** (key) | string | ✓ | 운동 고유 ID (예: E01, E02) | AI가 운동을 호출하고 추적하는 기준 |
| **name_en** | string | ✓ | 영문 운동명 | 전문가/트레이너 간 국제 표준 명칭 |
| **name_kr** | string | ✓ | 한글 운동명 | 환자가 이해하기 쉬운 명칭 |
| **difficulty** | string | ✓ | 난이도 등급 | 부하량, 가동범위, 근력 요구도 기반 |
| **diagnosis_tags** | array | ✓ | 질환 분류 키 | 운동 추천의 1차 필터 역할 |
| **function_tags** | array | ✓ | 기능 분류 키 | 프로토콜 설계의 핵심 기준 |
| **target_muscles** | array | ✓ | 주동근 목록 | 약화 근육 직접 타겟팅 |
| **sets** | int | ✓ | 세트 수 | 부하 용량(Volume) 결정 |
| **reps** | string | ✓ | 반복 횟수 또는 시간 | 근력/지구력/신경활성 패턴 정량화 |
| **rest** | string | ✓ | 세트 간 휴식 | 근지구력/근비대/신경활성 목적별 조절 |
| **description** | string | ✓ | 운동 수행법 설명 | 정확한 자세로 부상 예방 |
| **youtube** | string | | 영상 링크 | 시각적 학습 자료 |

#### 난이도 등급 체계 (Difficulty)

| 등급 | 코드 | 기준 | 대상 환자 |
|------|------|------|----------|
| **기초 단계** | `low` | 누운/앉은 자세, 최소 관절 부하, 기본 ROM | 급성기, 고령자, 신체점수 D |
| **표준 단계** | `medium` | 중간 관절 부하, 표준 ROM, 부분 체중지지 | 아급성기, 신체점수 C-B |
| **강화 단계** | `high` | 높은 관절 부하, 전체 체중지지, 기능적 동작 | 회복기, 신체점수 B-A |

> 향후 `very_high` (심화 단계) 추가 예정: 스포츠 복귀 목적, 폭발적 동작 포함

#### 질환 분류 키 (Diagnosis Tags)

| 태그 | 의미 | 설명 | 운동 특성 |
|------|------|------|----------|
| **OA** | Osteoarthritis | 퇴행성 관절염 | 저충격, 관절 보호, 근력 유지 |
| **OVR** | Overuse | 과사용 증후군 | 점진적 강화, 생역학 교정 |
| **TRM** | Trauma | 외상성 손상 | ROM 회복, 안정성, 단계적 진행 |
| **INF** | Inflammatory | 염증성 질환 | 저강도 가동성, 순환 촉진 |

#### 기능 분류 키 (Function Tags)

| 태그 | 목적 | 루틴 순서 | 대표 운동 |
|------|------|----------|----------|
| **Mobility** | 관절 가동범위 회복 | 1 (준비) | 힐 슬라이드, 발목 펌프 |
| **Stretching** | 근육/연부조직 유연성 | 2 (준비) | 종아리 스트레칭, 햄스트링 스트레칭 |
| **Strengthening** | 근력 강화 | 3 (본운동) | 스쿼트, 브리지, 레그프레스 |
| **Stability** | 관절 안정성 | 4 (마무리) | 클램쉘, 코어 운동 |
| **Balance** | 균형 및 고유수용감각 | 5 (마무리) | 한 발 서기, BOSU 운동 |
| **Endurance** | 근지구력 | 3-4 | 벽앉기, 반복 스텝 |
| **Circulation** | 혈액순환 촉진 | 1 | 발목 펌프, 경미한 움직임 |

### 6.2 확장 예정 필드 (V2 스키마)

임상적 정확도 향상을 위해 다음 필드 추가 예정:

```json
{
  "E01": {
    "...기존 필드...": "...",

    "joint_loading": "very_low",
    "movement_pattern": "mobility",
    "required_rom": "small",
    "kinetic_chain": "OKC",
    "agonist": ["햄스트링", "대퇴사두근"],
    "antagonist": ["고관절 굴곡근"],
    "synergist": ["복직근", "중둔근"]
  }
}
```

#### 관절 부하 수준 (Joint Loading Level)

| 등급 | 코드 | 설명 | 적응증 |
|------|------|------|--------|
| **매우 낮음** | `very_low` | 비체중부하, 지지면 위 | 급성기, NRS 7+ |
| **낮음** | `low` | 부분 체중부하, 보조기구 | 아급성기, NRS 5-6 |
| **중간** | `moderate` | 전체 체중부하, 정적 동작 | 회복기, NRS 3-4 |
| **높음** | `high` | 동적 체중부하, 충격 포함 | 기능적 단계, NRS 0-2 |

> **임상적 이유**: 통증 단계/재활 단계에 맞는 운동 선택을 정확히 하기 위함

#### 움직임 패턴 (Movement Pattern Type)

| 패턴 | 코드 | 대표 운동 | 주요 근육 |
|------|------|----------|----------|
| **스쿼트** | `squat` | 미니스쿼트, 벽앉기 | 대퇴사두근, 둔근 |
| **런지** | `lunge` | 전방런지, 측면런지 | 대퇴사두근, 고관절굴곡근 |
| **힙힌지/브리지** | `hip_hinge` | 브리지, 데드리프트 | 둔근, 햄스트링 |
| **스텝/보행** | `step_gait` | 스텝업, 보행훈련 | 하지 전체 |
| **밸런스** | `balance` | 한 발 서기, BOSU | 고유수용감각 |
| **코어** | `core` | 플랭크, 데드버그 | 복근, 요추다열근 |
| **가동성** | `mobility` | 힐슬라이드, ROM 운동 | 관절낭, 인대 |

> **임상적 이유**: 패턴 단위 처방이 근육 단위보다 기능 회복에 더 효과적

#### 필요 가동범위 (Required ROM)

| 등급 | 코드 | 무릎 ROM 예시 | 적응증 |
|------|------|-------------|--------|
| **소** | `small` | 0-45° | ROM 제한 환자, 초기 재활 |
| **중** | `medium` | 0-90° | 부분 ROM 회복 환자 |
| **대** | `full` | 0-120°+ | 전체 ROM 회복 환자 |

#### 운동 사슬 타입 (Kinetic Chain)

| 타입 | 코드 | 특성 | 적응증 |
|------|------|------|--------|
| **OKC** | `OKC` | 원위부 자유 (레그익스텐션) | 특정 근육 격리 강화 |
| **CKC** | `CKC` | 원위부 고정 (스쿼트) | 관절 안정성, 기능적 움직임 |

> **임상 근거**: CKC는 관절 안정성↑, OKC는 특정 근육 격리 강화↑

#### 근육 분류 체계

| 분류 | 설명 | 임상적 중요도 |
|------|------|--------------|
| **주동근 (Agonist)** | 주로 힘을 생산하는 근육 | 약화 근육 직접 타겟팅 |
| **길항근 (Antagonist)** | 주동근 반대 작용 근육 | 타이트→ROM 제한→통증 증가 |
| **협동근 (Synergist)** | 보조/안정화 역할 근육 | 운동 패턴 정상화, 기능 개선 |

### 6.3 운동 추천 알고리즘

#### 전체 파이프라인

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. 입력 검증 및 전처리                                          │
├─────────────────────────────────────────────────────────────────┤
│ • 버킷 유효성 검증 (OA/OVR/TRM/INF)                             │
│ • 복수 버킷 처리: "TRM|OA" → 첫 번째 유효 버킷 선택             │
│ • 신체 점수 레벨 확인 (A/B/C/D)                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. 후보 운동 필터링 (ExerciseFilter)                            │
├─────────────────────────────────────────────────────────────────┤
│ • 버킷 매칭: diagnosis_tags에 버킷 포함 여부                    │
│ • 난이도 필터링: 신체 점수 + NRS 기반 허용 난이도 결정          │
│   - 신체 Lv A: low, medium, high 허용                          │
│   - 신체 Lv D: low만 허용                                       │
│   - NRS ≥ 7: low만 허용                                        │
│   - NRS 4-6: high 제외                                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. 개인화 조정 (PersonalizationService)                         │
├─────────────────────────────────────────────────────────────────┤
│ • 나이 기반 조정                                                │
│   - 65세+: 세트 -1, 휴식 +15초                                  │
│   - 50-64세: 휴식 +10초                                         │
│ • BMI 기반 조정                                                 │
│   - BMI 30+: 근력운동 세트 -1, 휴식 +15초                       │
│   - BMI 25-29: 휴식 +5초                                        │
│ • 통증 기반 조정                                                │
│   - NRS 7+: 세트 -1, 반복 -3회                                  │
│   - NRS 4-6: 반복 -2회                                          │
│ • 우선순위 부스트                                               │
│   - 고령자: 균형/안정성 운동 +0.15                              │
│   - 비만: 가동성/스트레칭 +0.1                                  │
│   - 고통증: 가동성 +0.15                                        │
│   - 젊은층+저통증: 근력 +0.1                                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. LLM 기반 최종 선택 (ExerciseRecommender)                     │
├─────────────────────────────────────────────────────────────────┤
│ • 환자 프로필 분석 → LLM 프롬프트에 포함                        │
│ • 후보 운동 정보 + 개인화 가이드 전달                           │
│ • 선택 기준:                                                    │
│   1. 환자 특성 맞춤 (나이/BMI/통증)                              │
│   2. 기능 균형 (가동성, 근력, 안정성)                           │
│   3. 다양성 (같은 기능 운동만 선택 방지)                        │
│   4. 진행성 (쉬운 → 어려운 순서)                                │
│ • 출력: 5-7개 운동 + 추천 이유 + 적합도 점수                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. 운동 순서 결정 (get_exercise_order)                          │
├─────────────────────────────────────────────────────────────────┤
│ 순서 원칙:                                                      │
│ 1. 준비 운동 (Mobility, Stretching) → 먼저                      │
│ 2. 본 운동 (Strengthening) → 중간                               │
│ 3. 마무리 (Balance, Stability) → 마지막                         │
│ 4. 같은 카테고리 내 난이도 오름차순                              │
└─────────────────────────────────────────────────────────────────┘
```

#### 난이도 허용 매트릭스

| 신체 레벨 | NRS 0-3 | NRS 4-6 | NRS 7+ |
|----------|---------|---------|--------|
| **A** | low, medium, high | low, medium | low |
| **B** | low, medium, high | low, medium | low |
| **C** | low, medium | low, medium | low |
| **D** | low | low | low |

#### 개인화 조정 상세

```python
# 나이 기반 조정
if age >= 65:
    sets = max(1, sets - 1)
    rest = rest + 15초
    # 균형/안정성 운동 우선순위 +0.15

# BMI 기반 조정
if bmi >= 30:
    if "Strengthening" in function_tags:
        sets = max(1, sets - 1)
    rest = rest + 15초
    # 가동성/스트레칭 운동 우선순위 +0.1

# 통증 기반 조정
if nrs >= 7:
    sets = max(1, sets - 1)
    reps = max(5, reps - 3)
    # 가동성 운동 우선순위 +0.15
```

#### 사후 설문 기반 조정

3세션 RPE 합계에 따른 다음 세션 조정:

| RPE 합계 | 해석 | 조정 |
|----------|------|------|
| ≤ 6 | 너무 쉬움 | 난이도 +1, 세트 +1, 반복 +2 |
| 7-11 | 적정 | 유지 |
| ≥ 12 | 너무 힘듦 | 난이도 -1, 세트 -1, 반복 -2 |

### 6.4 벡터 검색 기반 운동 검색

#### 운동용 벡터 DB (orthocare-exercise)

```python
# 운동 벡터 메타데이터
metadata = {
    "id": "E01",
    "body_part": "knee",
    "source": "exercise",
    "bucket": "INF,TRM",           # 쉼표 구분 복수 버킷
    "name_kr": "힐 슬라이드",
    "name_en": "Heel Slide",
    "difficulty": "low",
    "function_tags": "Mobility",
    "target_muscles": "햄스트링,대퇴사두근"
}
```

#### 증상 기반 검색 쿼리 생성

```python
def _build_query(symptoms, body_part, bucket, demographics):
    parts = [
        f"부위: {body_part}",
        f"버킷: {bucket}",
        f"증상: {', '.join(symptoms[:5])}"
    ]

    if demographics.age >= 65:
        parts.append("고령자 안전 운동")
    elif demographics.age >= 50:
        parts.append("중년 적합 운동")

    return " ".join(parts)
```

#### 검색 필터

```python
filters = {
    "body_part": body_part,    # 부위 필터
    "source": "exercise"       # 운동 데이터만
}

# min_score: 0.35 (유사도 임계값)
# top_k: 20 (후보 운동 수)
```

### 6.5 LLM 프롬프트 구성

#### 환자 프로필 분석

```markdown
## 환자 특성 분석 (개인화 필수 반영)
- **고령 환자**: 낙상 위험 고려, 균형/안정성 운동 필수, 고강도 운동 제외
- **비만**: 관절 부담 고려, 저충격 운동 선택
- **심한 통증**: 저강도 가동성 운동만, 근력 운동 최소화
- **신체 Lv D**: 기초 운동만, 저강도 위주
```

#### 선택 기준

```markdown
## 선택 기준 (중요도 순)
1. **환자 특성 맞춤**: 나이/BMI/통증에 따른 운동 강도 조절
2. **기능 균형**: 가동성, 근력, 안정성 운동을 균형 있게 포함
3. **다양성**: 같은 기능의 운동만 선택하지 말고 다양하게 선택
4. **진행성**: 쉬운 운동 → 어려운 운동 순서로 배치

## 개인화 가이드
- 고령자(65+): 균형/안정성 운동 우선, 고강도 제외
- 비만(BMI 30+): 체중 부하 적은 운동 우선
- 고통증(NRS 7+): 저강도, 가동성 위주
- 젊은 층(40-): 근력 운동 비중 높게
```

#### 응답 형식

```json
{
    "selected_exercises": ["E01", "E06", "E09", ...],
    "reasons": {
        "E01": "ROM 제한 환자에게 적합한 저강도 가동성 운동"
    },
    "scores": {
        "E01": 0.95
    },
    "combination_rationale": {
        "why_together": "가동성 → 안정성 → 근력 순서로 점진적 강화",
        "bucket_coverage": "OA 관절 보호를 위한 저충격 운동 조합",
        "progression_logic": "준비 → 본운동 → 마무리 순서"
    },
    "patient_fit": {
        "age_consideration": "55세 중년층, 중등도 운동 가능",
        "bmi_consideration": "BMI 26.5 과체중, 체중 부하 최소화",
        "nrs_consideration": "NRS 5 중등도 통증, 고강도 제외"
    },
    "reasoning": "전체 추천 요약"
}
```

---

## 7. API 엔드포인트 상세

### 7.1 버킷 추론 API (Port 8001)

```bash
POST /api/v1/infer-bucket
```

#### Request 스키마

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
    "primary": true,
    "side": "both",
    "symptoms": ["pain_bilateral", "chronic", "stairs_down", "stiffness_morning"],
    "nrs": 6,
    "red_flags_checked": []
  }],
  "natural_language": {
    "chief_complaint": "양쪽 무릎이 아프고 계단 내려갈 때 힘들어요",
    "pain_description": "아침에 뻣뻣하고 30분 정도 지나면 나아져요",
    "history": "5년 전부터 서서히 심해짐"
  }
}
```

#### Request 필드 상세

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| **demographics** | object | ✓ | 인구통계학적 정보 |
| ├─ age | int | ✓ | 나이 (10-100) |
| ├─ sex | string | ✓ | 성별 (`male` / `female`) |
| ├─ height_cm | float | ✓ | 키 (cm, 100-250) |
| └─ weight_kg | float | ✓ | 몸무게 (kg, 30-200) |
| **body_parts** | array | ✓ | 부위별 증상 입력 (최소 1개) |
| ├─ code | string | ✓ | 부위 코드 (`knee`, `shoulder`, `back`, `neck`, `ankle`) |
| ├─ primary | bool | | 주요 부위 여부 (기본: true) |
| ├─ side | string | | 좌우 구분 (`left` / `right` / `both`) |
| ├─ symptoms | array | | 증상 코드 리스트 |
| ├─ nrs | int | ✓ | 통증 점수 (0-10) |
| └─ red_flags_checked | array | | 확인된 레드플래그 코드 |
| **natural_language** | object | | 자연어 입력 (선택) |
| ├─ chief_complaint | string | | 주호소 - 사용자가 직접 입력한 증상 설명 |
| ├─ pain_description | string | | 통증 설명 - 언제, 어떻게, 어디가 아픈지 |
| └─ history | string | | 병력 - 이전 치료, 부상 경험 등 |

#### 증상 코드 예시 (무릎)

| 코드 | 설명 | 관련 버킷 |
|------|------|----------|
| `pain_stairs` | 계단 오르내릴 때 통증 | OA |
| `stiffness_morning` | 아침 뻣뻣함 | OA |
| `pain_running` | 달리기 시 통증 | OVR |
| `swelling_acute` | 급성 부종 | TRM, INF |
| `instability` | 무릎 불안정감 | TRM |
| `warmth_redness` | 열감/발적 | INF |

#### Response 스키마

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
  "weight_ranking": ["OA", "OVR", "INF", "TRM"],
  "search_ranking": ["OA", "OVR", "TRM"],
  "discrepancy": null,
  "evidence_summary": "검증된 논문과 OARSI 가이드라인에 따르면, 55세 여성의 양측 무릎 통증, 아침 뻣뻣함, 계단 통증은 퇴행성 관절염(OA)의 전형적인 증상입니다.",
  "llm_reasoning": "### 버킷 판단 근거\n- **가중치 분석**: OA 15점으로 최고점\n- **검색 분석**: OA 관련 논문 5개 매칭\n- **결론**: 두 경로 일치, OA로 최종 판단",
  "red_flag": null,
  "inferred_at": "2025-12-05T12:00:00"
}
```

#### Response 필드 상세

| 필드 | 타입 | 설명 |
|------|------|------|
| **body_part** | string | 부위 코드 |
| **final_bucket** | string | 최종 진단 버킷 (`OA` / `OVR` / `TRM` / `INF`) |
| **confidence** | float | 신뢰도 (0-1) |
| **bucket_scores** | object | 버킷별 가중치 점수 |
| ├─ OA | float | 퇴행성 관절염 점수 |
| ├─ OVR | float | 과사용 점수 |
| ├─ TRM | float | 외상 점수 |
| └─ INF | float | 염증 점수 |
| **weight_ranking** | array | 가중치 기반 버킷 순위 |
| **search_ranking** | array | 벡터 검색 기반 버킷 순위 |
| **discrepancy** | object \| null | 가중치 vs 검색 불일치 정보 |
| ├─ type | string | 불일치 유형 |
| ├─ weight_ranking | array | 가중치 순위 |
| ├─ search_ranking | array | 검색 순위 |
| ├─ message | string | 경고 메시지 |
| └─ severity | string | 심각도 (`warning` / `critical`) |
| **evidence_summary** | string | 근거 요약 (LLM 생성, 논문 인용 포함) |
| **llm_reasoning** | string | LLM 판단 근거 (마크다운) |
| **red_flag** | object \| null | 레드플래그 결과 |
| ├─ triggered | bool | 레드플래그 발동 여부 |
| ├─ flags | array | 발동된 레드플래그 코드 |
| ├─ messages | array | 경고 메시지들 |
| └─ action | string | 권장 조치 (예: "즉시 병원 방문") |
| **inferred_at** | datetime | 추론 시간 (ISO 8601) |

---

### 7.2 운동 추천 API (Port 8002)

```bash
POST /api/v1/recommend-exercises
```

#### Request 스키마

```json
{
  "user_id": "user_001",
  "body_part": "knee",
  "bucket": "OA",
  "physical_score": {
    "total_score": 9
  },
  "demographics": {
    "age": 55,
    "sex": "female",
    "height_cm": 160,
    "weight_kg": 65
  },
  "nrs": 5,
  "previous_assessments": [
    {
      "session_date": "2025-12-04T10:00:00",
      "difficulty_felt": 3,
      "muscle_stimulus": 3,
      "sweat_level": 2,
      "pain_during_exercise": 4,
      "skipped_exercises": [],
      "completed_sets": 10,
      "total_sets": 12
    }
  ],
  "last_assessment_date": "2025-12-04T10:00:00",
  "skipped_exercises": ["E05"],
  "favorite_exercises": ["E01", "E02"]
}
```

#### Request 필드 상세

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| **user_id** | string | ✓ | 사용자 ID |
| **body_part** | string | ✓ | 부위 코드 (`knee` 등) |
| **bucket** | string | ✓ | 버킷 추론 결과 (`OA`/`OVR`/`TRM`/`INF`) |
| **physical_score** | object | ✓ | 신체 점수 |
| └─ total_score | int | ✓ | 사전평가 총점 (4-16) |
| **demographics** | object | ✓ | 인구통계 정보 (위와 동일) |
| **nrs** | int | ✓ | 현재 통증 점수 (0-10) |
| **previous_assessments** | array | | 이전 사후 설문 (최대 3세션) |
| ├─ session_date | datetime | ✓ | 세션 날짜 |
| ├─ difficulty_felt | int | ✓ | 운동 난이도 체감 (1-5) |
| ├─ muscle_stimulus | int | ✓ | 근육 자극 정도 (1-5) |
| ├─ sweat_level | int | ✓ | 땀 배출량 (1-5) |
| ├─ pain_during_exercise | int | | 운동 중 통증 (0-10) |
| ├─ skipped_exercises | array | | 건너뛴 운동 ID 목록 |
| ├─ completed_sets | int | | 완료한 세트 수 |
| └─ total_sets | int | | 총 세트 수 |
| **last_assessment_date** | datetime | | 마지막 사후 설문 날짜 |
| **skipped_exercises** | array | | 자주 건너뛴 운동 ID (우선순위 ↓) |
| **favorite_exercises** | array | | 즐겨찾기 운동 ID (우선순위 ↑) |

#### 신체 점수 레벨

| 레벨 | 점수 범위 | 허용 난이도 | 운동 개수 |
|------|----------|------------|----------|
| **A** | 14-16점 | low, medium, high | 6개 |
| **B** | 11-13점 | low, medium, high | 5개 |
| **C** | 8-10점 | low, medium | 4개 |
| **D** | 4-7점 | low | 3개 |

#### Response 스키마

```json
{
  "user_id": "user_001",
  "body_part": "knee",
  "bucket": "OA",
  "exercises": [
    {
      "exercise_id": "E01",
      "name_kr": "힐 슬라이드",
      "name_en": "Heel Slide",
      "difficulty": "low",
      "function_tags": ["Mobility", "Stretching"],
      "target_muscles": ["대퇴사두근", "햄스트링"],
      "sets": 2,
      "reps": "10회",
      "rest": "30초",
      "reason": "무릎 가동범위 개선에 효과적이며, 55세 여성의 OA 상태에 적합한 저강도 운동입니다.",
      "priority": 1,
      "match_score": 0.95,
      "youtube": "https://youtube.com/watch?v=xxx",
      "description": "누운 상태에서 발꿈치를 바닥에 대고 무릎을 구부렸다 폅니다."
    },
    {
      "exercise_id": "E02",
      "name_kr": "클램쉘",
      "name_en": "Clamshell",
      "difficulty": "low",
      "function_tags": ["Strengthening", "Stability"],
      "target_muscles": ["중둔근", "외회전근"],
      "sets": 2,
      "reps": "15회",
      "rest": "30초",
      "reason": "고관절 안정성 강화로 무릎 부담을 줄여줍니다.",
      "priority": 2,
      "match_score": 0.92,
      "youtube": "https://youtube.com/watch?v=yyy",
      "description": "옆으로 누워 무릎을 구부린 상태에서 위쪽 무릎을 들어올립니다."
    }
  ],
  "excluded": [
    {
      "exercise_id": "E10",
      "name_kr": "점프 스쿼트",
      "reason": "NRS 5점으로 고강도 운동 제외",
      "exclusion_type": "nrs"
    }
  ],
  "routine_order": ["E01", "E02", "E03", "E04", "E05"],
  "total_duration_min": 15,
  "difficulty_level": "low",
  "adjustments_applied": {
    "difficulty_delta": 0,
    "sets_delta": 0,
    "reps_delta": 0
  },
  "assessment_status": "normal",
  "assessment_message": "2세션 완료. 1세션 후 난이도가 조정됩니다.",
  "llm_reasoning": "### 운동 조합 근거\n- **시너지**: 가동성 → 근력 순서로 워밍업 효과 극대화\n- **버킷 치료**: OA 관절 보호를 위한 저충격 운동 위주 선택\n\n### 환자 맞춤 고려사항\n- **나이 고려**: 55세로 중년기, 중등도 이하 난이도 적합\n- **BMI 고려**: 25.4로 과체중, 체중 부하 운동 최소화\n- **통증 고려**: NRS 5점으로 중등도 통증, 고강도 제외",
  "recommended_at": "2025-12-05T12:30:00"
}
```

#### Response 필드 상세

| 필드 | 타입 | 설명 |
|------|------|------|
| **user_id** | string | 사용자 ID |
| **body_part** | string | 부위 코드 |
| **bucket** | string | 진단 버킷 |
| **exercises** | array | 추천 운동 목록 (최소 1개) |
| ├─ exercise_id | string | 운동 ID |
| ├─ name_kr | string | 한글명 |
| ├─ name_en | string | 영문명 |
| ├─ difficulty | string | 난이도 (`low`/`medium`/`high`) |
| ├─ function_tags | array | 기능 태그 (아래 참조) |
| ├─ target_muscles | array | 타겟 근육 |
| ├─ sets | int | 세트 수 |
| ├─ reps | string | 반복 횟수 (예: "10회", "30초") |
| ├─ rest | string | 휴식 시간 (예: "30초") |
| ├─ reason | string | 이 환자에게 추천하는 구체적 이유 |
| ├─ priority | int | 우선순위 (1=최우선) |
| ├─ match_score | float | 적합도 점수 (0-1) |
| ├─ youtube | string \| null | 유튜브 영상 링크 |
| └─ description | string \| null | 운동 설명 |
| **excluded** | array | 제외된 운동 목록 |
| ├─ exercise_id | string | 운동 ID |
| ├─ name_kr | string | 한글명 |
| ├─ reason | string | 제외 사유 |
| └─ exclusion_type | string | 제외 유형 (아래 참조) |
| **routine_order** | array | 루틴 순서 (운동 ID 배열) |
| **total_duration_min** | int | 예상 소요 시간 (분) |
| **difficulty_level** | string | 전체 난이도 (`low`/`medium`/`high`/`mixed`) |
| **adjustments_applied** | object | 적용된 조정 |
| ├─ difficulty_delta | int | 난이도 변화 (-1/0/+1) |
| ├─ sets_delta | int | 세트 수 변화 |
| └─ reps_delta | int | 반복 횟수 변화 |
| **assessment_status** | string | 사후 설문 처리 상태 (아래 참조) |
| **assessment_message** | string | 사후 설문 처리 메시지 |
| **llm_reasoning** | string | LLM 추천 근거 (마크다운) |
| **recommended_at** | datetime | 추천 시간 (ISO 8601) |

#### function_tags (기능 태그)

| 태그 | 설명 | 루틴 순서 |
|------|------|----------|
| `Mobility` | 관절 가동성 | 1 (준비) |
| `Stretching` | 스트레칭 | 2 (준비) |
| `Strengthening` | 근력 강화 | 3 (본운동) |
| `Stability` | 안정성 | 4 (마무리) |
| `Balance` | 균형 | 5 (마무리) |

#### exclusion_type (제외 유형)

| 타입 | 설명 |
|------|------|
| `contraindication` | 금기 사항 |
| `difficulty` | 난이도 부적합 |
| `nrs` | 통증 점수 기준 제외 |
| `assessment` | 사후 설문 기반 제외 |

#### assessment_status (사후 설문 상태)

| 상태 | 설명 |
|------|------|
| `fresh_start` | 최초 운동 (사전 평가만 사용) |
| `normal` | 정상 (이전 기록 반영, 3세션 완료 시 조정) |
| `reset` | 리셋 (7일+ 미접속 또는 기록 손실) |

---

### 7.3 간단 운동 추천 API (LLM 미사용)

```bash
POST /api/v1/recommend-exercises/simple
```

LLM 호출 없이 빠르게 운동을 추천합니다. 응답 형식은 동일합니다.

---

## 8. 사후 평가 시스템 (RPE 기반)

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

## 9. 설치 및 실행

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

## 10. 평가 결과

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

## 11. 기술 스택

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
