# API Input / Output Summary

## Input (UnifiedRequest)

Endpoints:
- `POST /api/v1/diagnose-and-recommend`
- `POST /api/v1/diagnose`

Required:
- `user_id` (string)
- `demographics`:
  - `age` (int, 10-100)
  - `sex` ("male" | "female")
  - `height_cm` (number, 100-250)
  - `weight_kg` (number, 30-200)
- `body_parts` (array, min 1):
  - `code` ("knee" | "shoulder" | "back" | "neck" | "ankle")
  - `primary` (bool, default true)
  - `side` ("left" | "right" | "both", optional)
  - `symptoms` (array of symptom codes)
  - `nrs` (int, 0-10)
  - `red_flags_checked` (array, optional)

Optional:
- `request_id` (string, uuid)
- `physical_score`:
  - `total_score` (int, 4-16)
- `natural_language`:
  - `chief_complaint` (string)
  - `pain_description` (string)
  - `history` (string)
- `raw_survey_responses` (object)
- `options`:
  - `include_exercises` (bool, default true)
  - `exercise_days` (int, 1-7, default 3)
  - `skip_exercise_on_red_flag` (bool, default true)

Minimal request (diagnose only):
```json
{
  "user_id": "user_001",
  "demographics": {
    "age": 55,
    "sex": "female",
    "height_cm": 160,
    "weight_kg": 65
  },
  "body_parts": [
    {
      "code": "knee",
      "primary": true,
      "side": "both",
      "symptoms": ["pain_medial", "stiffness_morning"],
      "nrs": 6,
      "red_flags_checked": []
    }
  ],
  "options": {
    "include_exercises": false
  }
}
```

Full request (diagnose + recommend):
```json
{
  "user_id": "user_123",
  "demographics": {
    "age": 55,
    "sex": "male",
    "height_cm": 175,
    "weight_kg": 80
  },
  "body_parts": [
    {
      "code": "knee",
      "primary": true,
      "side": "left",
      "symptoms": ["pain_medial", "stiffness_morning"],
      "nrs": 6,
      "red_flags_checked": []
    }
  ],
  "physical_score": {
    "total_score": 12
  },
  "options": {
    "include_exercises": true,
    "exercise_days": 3,
    "skip_exercise_on_red_flag": true
  }
}
```

## Output (UnifiedResponse)

Top-level fields:
- `request_id`, `user_id`
- `survey_data`:
  - `demographics`, `body_parts`, `natural_language`, `physical_score`, `raw_responses`
- `diagnosis`:
  - `body_part`, `final_bucket`, `confidence`
  - `bucket_scores`, `weight_ranking`, `search_ranking`
  - `evidence_summary`, `llm_reasoning`
  - `red_flag` (object or null)
  - `inferred_at`
- `exercise_plan` (object or null)
- `status`, `message`
- `processed_at`, `processing_time_ms`

Minimal response (exercise skipped):
```json
{
  "request_id": "uuid",
  "user_id": "user_001",
  "survey_data": {
    "demographics": {
      "age": 55,
      "sex": "female",
      "height_cm": 160.0,
      "weight_kg": 65.0
    },
    "body_parts": [
      {
        "code": "knee",
        "primary": true,
        "side": "both",
        "symptoms": ["pain_medial", "stiffness_morning"],
        "nrs": 6,
        "red_flags_checked": []
      }
    ],
    "natural_language": null,
    "physical_score": null,
    "raw_responses": null
  },
  "diagnosis": {
    "body_part": "knee",
    "final_bucket": "OA",
    "confidence": 0.75
  },
  "exercise_plan": null,
  "status": "success",
  "message": null,
  "processed_at": "2026-01-05T00:00:00Z",
  "processing_time_ms": 8000
}
```
