"""Gateway Service - 통합 API 서버

사용법:
    PYTHONPATH=. python -m gateway.main

포트: 8000 (기본)
"""

from contextlib import asynccontextmanager
from datetime import datetime, date
import os
import re

from dotenv import load_dotenv
load_dotenv(override=True)

from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gateway.models import (
    UnifiedRequest,
    UnifiedResponse,
    AppDiagnoseRequest,
    AppDiagnoseResponse,
    AppExerciseRequest,
    AppExerciseResponse,
)
from gateway.services import OrchestrationService
from exercise_recommendation.models.input import ExerciseRecommendationInput
from exercise_recommendation.models.output import ExerciseRecommendationOutput
from bucket_inference.models.input import NaturalLanguageInput
from shared.models import Demographics, BodyPartInput, PhysicalScore


# 오케스트레이션 서비스 (싱글톤)
orchestration_service: OrchestrationService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 라이프사이클 관리"""
    global orchestration_service
    print("Gateway Service 시작 중...")
    orchestration_service = OrchestrationService()
    print("Gateway Service 준비 완료")
    yield
    print("Gateway Service 종료")


app = FastAPI(
    title="Orthocare Gateway API",
    description="버킷 추론 + 운동 추천 통합 API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _error_payload(error: Exception, hint: str = None) -> dict:
    """오류 응답용 페이로드 (디버깅 도움용)"""
    return {
        "error": str(error),
        "type": type(error).__name__,
        "hint": hint,
    }


def _age_from_birthdate(birth_date: date) -> int:
    today = date.today()
    age = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
    return max(age, 0)


def _map_gender(gender: str) -> str:
    key = gender.strip().upper()
    mapping = {
        "MALE": "male",
        "FEMALE": "female",
        "PREFER_NOT_TO_SAY": "prefer_not_to_say",
    }
    if key not in mapping:
        raise ValueError(f"지원하지 않는 gender: {gender}")
    return mapping[key]


def _map_pain_area(pain_area: str) -> str:
    key = pain_area.strip().lower()
    mapping = {
        "knee": "knee",
        "shoulder": "shoulder",
        "back": "back",
        "neck": "neck",
        "ankle": "ankle",
        "무릎": "knee",
        "어깨": "shoulder",
        "허리": "back",
        "목": "neck",
        "발목": "ankle",
    }
    if key not in mapping:
        raise ValueError(f"지원하지 않는 painArea: {pain_area}")
    return mapping[key]


def _map_side(affected_side: str) -> str | None:
    key = affected_side.strip().lower()
    mapping = {
        "left": "left",
        "right": "right",
        "both": "both",
        "왼쪽": "left",
        "오른쪽": "right",
        "양쪽": "both",
        "좌": "left",
        "우": "right",
    }
    return mapping.get(key)


def _parse_int(text: str) -> int | None:
    if not text:
        return None
    match = re.search(r"\d+", text)
    return int(match.group()) if match else None


def _parse_reps_value(value) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    parsed = _parse_int(str(value))
    return parsed if parsed is not None else 0


def _parse_duration_seconds(text: str) -> int | None:
    if not text:
        return None
    value = _parse_int(text)
    if value is None:
        return None
    if "분" in text:
        return value * 60
    return value


def _score_from_count(value: int | None, thresholds: tuple[int, int, int]) -> int:
    if value is None:
        return 2
    if value <= thresholds[0]:
        return 1
    if value <= thresholds[1]:
        return 2
    if value <= thresholds[2]:
        return 3
    return 4


def _build_unified_from_app(request: AppDiagnoseRequest) -> UnifiedRequest:
    extras = request.model_extra or {}
    user_id = extras.get("user_id") or extras.get("userId") or "unknown"
    request_id = extras.get("request_id") or extras.get("requestId")

    age = _age_from_birthdate(request.birth_date)
    sex = _map_gender(request.gender)
    body_code = _map_pain_area(request.pain_area)
    side = _map_side(request.affected_side)

    symptoms = [
        request.pain_trigger,
        request.pain_sensation,
        request.pain_duration,
        request.pain_started_date,
    ]
    symptoms = [s for s in symptoms if s]

    nl = NaturalLanguageInput(
        chief_complaint=f"{request.pain_area} 통증",
        pain_description="; ".join(
            s for s in [request.pain_trigger, request.pain_sensation, request.pain_duration] if s
        ),
        history=request.pain_started_date,
    )

    raw_responses = {
        "painArea": request.pain_area,
        "affectedSide": request.affected_side,
        "painStartedDate": request.pain_started_date,
        "painLevel": request.pain_level,
        "painTrigger": request.pain_trigger,
        "painSensation": request.pain_sensation,
        "painDuration": request.pain_duration,
        "redFlags": request.red_flags,
    }

    data = {
        "user_id": str(user_id),
        "demographics": Demographics(
            age=age,
            sex=sex,
            height_cm=request.height,
            weight_kg=request.weight,
        ),
        "body_parts": [
            BodyPartInput(
                code=body_code,
                primary=True,
                side=side,
                symptoms=symptoms,
                nrs=request.pain_level,
            )
        ],
        "natural_language": nl,
        "raw_survey_responses": raw_responses,
    }
    if request_id:
        data["request_id"] = request_id
    return UnifiedRequest(**data)


def _map_bucket(value: str) -> str:
    key = value.strip()
    mapping = {
        "OA": "OA",
        "OVR": "OVR",
        "TRM": "TRM",
        "INF": "INF",
        "STF": "STF",
        "퇴행성형": "OA",
        "과사용형": "OVR",
        "외상형": "TRM",
        "염증형": "INF",
        "경직형": "STF",
    }
    if key not in mapping:
        raise ValueError(f"지원하지 않는 bucket: {value}")
    return mapping[key]


def _build_exercise_input_from_app(request: AppExerciseRequest) -> ExerciseRecommendationInput:
    extras = request.model_extra or {}

    bucket_raw = extras.get("bucket") or extras.get("diagnosis_type") or extras.get("diagnosisType")
    body_part_raw = extras.get("body_part") or extras.get("bodyPart") or extras.get("painArea")
    demo_raw = extras.get("demographics")

    if not bucket_raw or not body_part_raw:
        raise ValueError("bucket/body_part 누락: 백엔드에서 추가 전달 필요")

    if demo_raw:
        demographics = Demographics(**demo_raw)
    else:
        birth_date = extras.get("birthDate")
        gender = extras.get("gender")
        height = extras.get("height")
        weight = extras.get("weight")
        if not all([birth_date, gender, height, weight]):
            raise ValueError("demographics 누락: birthDate/gender/height/weight 필요")
        age = _age_from_birthdate(date.fromisoformat(birth_date))
        demographics = Demographics(
            age=age,
            sex=_map_gender(gender),
            height_cm=height,
            weight_kg=weight,
        )

    bucket = _map_bucket(str(bucket_raw))
    body_part = _map_pain_area(str(body_part_raw))

    squat = _parse_int(request.squat_response)
    pushup = _parse_int(request.pushup_response)
    stepup = _parse_int(request.stepup_response)
    plank_seconds = _parse_duration_seconds(request.plank_response)

    squat_score = _score_from_count(squat, (5, 10, 15))
    pushup_score = _score_from_count(pushup, (3, 6, 10))
    stepup_score = _score_from_count(stepup, (5, 10, 15))
    plank_score = _score_from_count(plank_seconds, (10, 20, 40))

    total_score = max(4, min(16, squat_score + pushup_score + stepup_score + plank_score))

    return ExerciseRecommendationInput(
        user_id=str(request.user_id),
        body_part=body_part,
        bucket=bucket,
        physical_score=PhysicalScore(total_score=total_score),
        demographics=demographics,
        nrs=request.pain_level,
    )


def _build_exercises_app(exercises: list) -> list[dict]:
    exercises_app = []
    for idx, ex in enumerate(exercises, start=1):
        ex_dict = ex.model_dump()
        exercises_app.append(
            {
                "exerciseId": ex_dict.get("exercise_id"),
                "nameKo": ex_dict.get("name_kr"),
                "difficulty": ex_dict.get("difficulty"),
                "recommendedSets": ex_dict.get("sets"),
                "recommendedReps": _parse_reps_value(ex_dict.get("reps")),
                "exerciseOrder": idx,
                "videoUrl": ex_dict.get("youtube"),
            }
        )
    return exercises_app


@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {
        "status": "healthy",
        "service": "gateway",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/api/v1/recommend-exercises", response_model=AppExerciseResponse)
async def recommend_exercises(
    request: AppExerciseRequest = Body(
        ...,
        example={
            "userId": 1,
            "routineDate": "2025-01-11",
            "painLevel": 5,
            "squatResponse": "10개",
            "pushupResponse": "5개",
            "stepupResponse": "15개",
            "plankResponse": "30초",
            "rpeResponse": "적당함",
            "muscleStimulationResponse": "중간",
            "sweatResponse": "보통",
        },
    )
):
    """운동 추천만 실행 (버킷 추론 생략)

    앱/백엔드에서 이미 버킷과 사전평가가 있을 때 사용
    """
    try:
        exercise_input = _build_exercise_input_from_app(request)
        exercise_output = orchestration_service.exercise_pipeline.run(exercise_input)
        exercises_app = _build_exercises_app(exercise_output.exercises)
        return {
            "userId": request.user_id,
            "routineDate": request.routine_date,
            "exercises": exercises_app,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=_error_payload(
                e,
                hint="bucket/body_part/인구통계 정보가 백엔드에서 전달되어야 합니다.",
            ),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_error_payload(
                e,
                hint="환경 변수(OPENAI/PINECONE) 또는 외부 서비스 연결 상태를 확인하세요.",
            ),
        )


@app.post(
    "/api/v1/diagnose",
    response_model=None,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "schema": AppDiagnoseResponse.model_json_schema(),
                }
            },
        }
    },
)
async def diagnose_only(request: AppDiagnoseRequest):
    """버킷 추론만 실행 (운동 추천 제외)

    운동 추천 없이 버킷 추론 결과만 반환
    """
    try:
        # 앱 입력을 그대로 사용해 추론 (자동 매핑/변환 없음)
        unified_request = _build_unified_from_app(request)
        result = orchestration_service.process_diagnosis_only(unified_request)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=_error_payload(
                e,
                hint="필수 필드(birthDate/height/weight/gender/painArea/painLevel 등)를 확인하세요.",
            ),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=_error_payload(
                e,
                hint="환경 변수(OPENAI/PINECONE) 또는 외부 서비스 연결 상태를 확인하세요.",
            ),
        )


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("GATEWAY_HOST", "0.0.0.0")
    port = int(os.getenv("GATEWAY_PORT", "8000"))

    print(f"Gateway Service 시작: http://{host}:{port}")
    uvicorn.run(
        "gateway.main:app",
        host=host,
        port=port,
        reload=True,
    )
