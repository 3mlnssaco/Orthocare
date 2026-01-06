# 최신 테스트 결과 (2026-01-05)

이 문서만 최신 테스트 결과로 관리합니다.

## 테스트 환경

- **URL**: https://orthocare-production.up.railway.app
- **테스트 시간**: 2026-01-05 12:18 EST
- **테스트 방법**: `python test_railway_api.py` 스크립트

---

## 테스트 1: 헬스 체크

```bash
curl -X GET https://orthocare-production.up.railway.app/health
```

**결과:** ✅ 성공 (200)

**응답:**
```json
{
  "status": "healthy",
  "service": "gateway",
  "timestamp": "2026-01-05T17:17:58.742764"
}
```

**결론:** 게이트웨이 서비스 자체는 정상 작동 중

---

## 테스트 2: 최소 요청 (올바른 값)

```bash
curl -X POST https://orthocare-production.up.railway.app/api/v1/diagnose-and-recommend \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_manual_001",
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
      "symptoms": ["pain_medial", "stiffness_morning"],
      "nrs": 6,
      "red_flags_checked": []
    }],
    "options": {
      "include_exercises": false
    }
  }'
```

**결과:** ✅ 성공 (200)

**응답:**
```json
{
  "request_id": "444656a7-d307-4c50-acf2-ef9d42486500",
  "status": "success",
  "diagnosis": {
    "final_bucket": "OA",
    "confidence": 0.75
  },
  "exercise_plan": null,
  "processing_time_ms": 11747
}
```

**분석:**
- 최소 요청 정상 처리
- 버킷 추론만 수행 (exercise_plan: null)

---

## 테스트 3: Swagger 예시 요청 (전체 필드)

```bash
curl -X POST https://orthocare-production.up.railway.app/api/v1/diagnose-and-recommend \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "demographics": {
      "age": 55,
      "sex": "male",
      "height_cm": 175,
      "weight_kg": 80
    },
    "body_parts": [{
      "code": "knee",
      "primary": true,
      "side": "left",
      "symptoms": ["pain_medial", "stiffness_morning"],
      "nrs": 6,
      "red_flags_checked": []
    }],
    "physical_score": {
      "total_score": 12
    },
    "options": {
      "include_exercises": true,
      "exercise_days": 3,
      "skip_exercise_on_red_flag": true
    }
  }'
```

**결과:** ✅ 성공 (200)

**응답:**
```json
{
  "request_id": "8cab1258-0230-4883-9178-92df509d6d1f",
  "status": "success",
  "diagnosis": {
    "final_bucket": "OA",
    "confidence": 0.75
  },
  "exercise_plan": {
    "total_duration_min": 18,
    "difficulty_level": "medium"
  },
  "processing_time_ms": 24085
}
```

**분석:**
- 버킷 추론 + 운동 추천 정상 처리
- 운동 6개 추천, 총 18분, 중간 난이도

---

## 테스트 4: 진단만 실행 (/api/v1/diagnose)

```bash
curl -X POST https://orthocare-production.up.railway.app/api/v1/diagnose \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user_002",
    "demographics": {
      "age": 55,
      "sex": "female",
      "height_cm": 160,
      "weight_kg": 65
    },
    "body_parts": [{
      "code": "knee",
      "symptoms": ["pain_medial", "stiffness_morning"],
      "nrs": 6
    }]
  }'
```

**결과:** ✅ 성공 (200)

**응답:**
```json
{
  "request_id": "db0ca69b-8beb-4f20-a95b-7395ed511cb1",
  "status": "success",
  "diagnosis": {
    "final_bucket": "OA",
    "confidence": 0.75
  },
  "exercise_plan": null,
  "processing_time_ms": 7569
}
```

---

## 결론

### 정상 작동하는 부분

1. ✅ **게이트웨이 서비스**: 헬스 체크 정상
2. ✅ **버킷 추론**: 최소 요청, 진단-only 모두 성공
3. ✅ **운동 추천**: 통합 요청 성공

### 문제가 있는 부분

1. ✅ **현재 확인된 문제 없음**

### 해결 방법

추가로 확인할 사항이 생기면 Railway 로그와 함께 업데이트 예정

---

## 참고 문서

- `RAILWAY_DEPLOYMENT_CHECKLIST.md` - 환경 변수 설정 가이드
- `SWAGGER_QUICK_START.md` - 올바른 요청 예시
- `TEST_RESULTS.md` - 이전 테스트 결과
