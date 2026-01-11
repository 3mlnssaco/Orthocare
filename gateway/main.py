"""Gateway Service - 통합 API 서버

사용법:
    PYTHONPATH=. python -m gateway.main

포트: 8000 (기본)
"""

from contextlib import asynccontextmanager
from datetime import datetime, date
import json
import os
import re

from dotenv import load_dotenv
load_dotenv(override=True)

from fastapi import FastAPI, HTTPException, Body
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI

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


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    try:
        req = schema["paths"]["/api/v1/recommend-exercises"]["post"]["requestBody"]["content"]["application/json"]
        req.pop("example", None)
        req["examples"] = {
            "initial": {
                "summary": "초기 (사후 설문 없음)",
                "value": {
                    "userId": 1,
                    "routineDate": "2025-01-11",
                    "painLevel": 5,
                    "squatResponse": "10개",
                    "pushupResponse": "5개",
                    "stepupResponse": "15개",
                    "plankResponse": "30초",
                    "bucket": "OA",
                    "bodyPart": "knee",
                    "age": 26,
                    "gender": "FEMALE",
                    "height": 170,
                    "weight": 65,
                    "physicalScore": 70,
                },
            },
            "after_feedback": {
                "summary": "사후 설문 포함",
                "value": {
                    "userId": 1,
                    "routineDate": "2025-01-11",
                    "painLevel": 5,
                    "squatResponse": "10개",
                    "pushupResponse": "5개",
                    "stepupResponse": "15개",
                    "plankResponse": "30초",
                    "postSurvey": {
                        "rpeResponse": "적당함",
                        "muscleStimulationResponse": "중간",
                        "sweatResponse": "보통",
                        "previousRoutine": {
                            "routineDate": "2025-01-11",
                            "exercises": [
                                {
                                    "exerciseId": "E09",
                                    "nameKo": "브리지",
                                    "difficulty": "기초 단계",
                                    "recommendedSets": 2,
                                    "recommendedReps": 10,
                                    "exerciseOrder": 1,
                                    "videoUrl": "https://..."
                                },
                                {
                                    "exerciseId": "E13",
                                    "nameKo": "부분 스쿼트",
                                    "difficulty": "기초 단계",
                                    "recommendedSets": 2,
                                    "recommendedReps": 8,
                                    "exerciseOrder": 2,
                                    "videoUrl": "https://..."
                                },
                                {
                                    "exerciseId": "E20",
                                    "nameKo": "의자 일어서기",
                                    "difficulty": "표준 단계",
                                    "recommendedSets": 2,
                                    "recommendedReps": 8,
                                    "exerciseOrder": 3,
                                    "videoUrl": "https://..."
                                }
                            ]
                        }
                    },
                    "bucket": "OA",
                    "bodyPart": "knee",
                    "age": 26,
                    "gender": "FEMALE",
                    "height": 170,
                    "weight": 65,
                    "physicalScore": 70,
                },
            },
        }
    except KeyError:
        pass
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi

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


def _clamp_physical_score(score: int) -> int:
    return max(0, min(100, int(score)))


def _calc_bmi(height_cm: int, weight_kg: int) -> float:
    if height_cm <= 0:
        return 0.0
    height_m = height_cm / 100
    return weight_kg / (height_m * height_m)


def _call_openai_json(prompt: str) -> dict | None:
    try:
        client = OpenAI()
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            messages=[
                {
                    "role": "system",
                    "content": "Return only valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        content = response.choices[0].message.content
        return json.loads(content) if content else None
    except Exception:
        return None


def _gpt_physical_score_from_diagnose(request: AppDiagnoseRequest) -> int:
    age = _age_from_birthdate(request.birth_date)
    bmi = _calc_bmi(request.height, request.weight)
    prompt = (
        "Estimate a physical ability score between 0 and 100.\n"
        "0 = very low, 100 = very high. Return JSON with key total_score.\n"
        f"- age: {age}\n"
        f"- gender: {request.gender}\n"
        f"- height_cm: {request.height}\n"
        f"- weight_kg: {request.weight}\n"
        f"- bmi: {bmi:.1f}\n"
        f"- pain_area: {request.pain_area}\n"
        f"- pain_level: {request.pain_level}/10\n"
        f"- pain_trigger: {request.pain_trigger}\n"
        f"- pain_sensation: {request.pain_sensation}\n"
        f"- pain_duration: {request.pain_duration}\n"
        f"- pain_started: {request.pain_started_date}\n"
    )
    data = _call_openai_json(prompt) or {}
    score = data.get("total_score") or data.get("totalScore")
    try:
        return _clamp_physical_score(int(float(score)))
    except (TypeError, ValueError):
        return 50


def _summarize_previous_routine(previous_routine) -> str:
    if not previous_routine or not previous_routine.exercises:
        return "None"
    parts = []
    for ex in previous_routine.exercises[:6]:
        parts.append(
            f"{ex.exercise_id}/{ex.name_ko}/{ex.difficulty} "
            f"{ex.recommended_sets}x{ex.recommended_reps}"
        )
    return "; ".join(parts)


def _gpt_physical_score_for_exercise(
    request: AppExerciseRequest,
    demographics: Demographics,
    bucket: str,
    body_part: str,
    base_score: int | None,
) -> int:
    bmi = demographics.bmi
    routine_summary = _summarize_previous_routine(
        request.post_survey.previous_routine if request.post_survey else None
    )
    prompt = (
        "Estimate or update a physical ability score between 0 and 100.\n"
        "If base_score is provided, adjust it using post-survey feedback and routine summary.\n"
        "If base_score is not provided, estimate from profile and pre-survey responses.\n"
        "Return JSON with key total_score.\n"
        f"- base_score: {base_score if base_score is not None else 'None'}\n"
        f"- age: {demographics.age}\n"
        f"- gender: {demographics.sex}\n"
        f"- height_cm: {demographics.height_cm}\n"
        f"- weight_kg: {demographics.weight_kg}\n"
        f"- bmi: {bmi:.1f}\n"
        f"- bucket: {bucket}\n"
        f"- body_part: {body_part}\n"
        f"- pain_level: {request.pain_level}/10\n"
        f"- squat_response: {request.squat_response}\n"
        f"- pushup_response: {request.pushup_response}\n"
        f"- stepup_response: {request.stepup_response}\n"
        f"- plank_response: {request.plank_response}\n"
        f"- post_survey_rpe: {request.post_survey.rpe_response if request.post_survey else None}\n"
        f"- post_survey_muscle: {request.post_survey.muscle_stimulation_response if request.post_survey else None}\n"
        f"- post_survey_sweat: {request.post_survey.sweat_response if request.post_survey else None}\n"
        f"- previous_routine: {routine_summary}\n"
    )
    data = _call_openai_json(prompt) or {}
    score = data.get("total_score") or data.get("totalScore")
    try:
        return _clamp_physical_score(int(float(score)))
    except (TypeError, ValueError):
        return _clamp_physical_score(base_score if base_score is not None else 50)


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


def _map_difficulty_label(value: str | None) -> str | None:
    if not value:
        return value
    key = value.strip().lower()
    mapping = {
        "beginner": "기초 단계",
        "standard": "표준 단계",
        "advanced": "강화 단계",
        "expert": "심화 단계",
        "low": "기초 단계",
        "medium": "표준 단계",
        "high": "강화 단계",
        "mixed": "표준 단계",
        "intermediate": "표준 단계",
        "기초 단계": "기초 단계",
        "표준 단계": "표준 단계",
        "강화 단계": "강화 단계",
        "심화 단계": "심화 단계",
    }
    return mapping.get(key, value)

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
    physical_score = _gpt_physical_score_from_diagnose(request)
    data["physical_score"] = PhysicalScore(total_score=physical_score)
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

    bucket_raw = (
        request.bucket
        or request.diagnosis_type
        or extras.get("bucket")
        or extras.get("diagnosis_type")
        or extras.get("diagnosisType")
    )
    body_part_raw = (
        request.body_part
        or request.pain_area
        or extras.get("body_part")
        or extras.get("bodyPart")
        or extras.get("painArea")
    )
    demo_raw = request.demographics or extras.get("demographics")

    if not bucket_raw or not body_part_raw:
        raise ValueError("bucket/body_part 누락: 백엔드에서 추가 전달 필요")

    if demo_raw:
        if hasattr(demo_raw, "model_dump"):
            demo_raw = demo_raw.model_dump()
        if not isinstance(demo_raw, dict):
            raise ValueError("demographics 형식 오류: dict 형태 필요")
        demo_age = demo_raw.get("age")
        demo_sex = demo_raw.get("sex") or demo_raw.get("gender")
        demo_height = demo_raw.get("height_cm") or demo_raw.get("height")
        demo_weight = demo_raw.get("weight_kg") or demo_raw.get("weight")
        if demo_age is None or demo_sex is None or demo_height is None or demo_weight is None:
            raise ValueError("demographics 누락: age/sex/height_cm/weight_kg 필요")
        demographics = Demographics(
            age=demo_age,
            sex=_map_gender(str(demo_sex)),
            height_cm=demo_height,
            weight_kg=demo_weight,
        )
    else:
        age = request.age or extras.get("age")
        gender = request.gender or extras.get("gender")
        height = request.height or extras.get("height")
        weight = request.weight or extras.get("weight")
        birth_date = request.birth_date or extras.get("birthDate")
        if age is None and birth_date:
            age = _age_from_birthdate(date.fromisoformat(str(birth_date)))
        if age is None or gender is None or height is None or weight is None:
            raise ValueError("demographics 누락: age(or birthDate)/gender/height/weight 필요")
        demographics = Demographics(
            age=age,
            sex=_map_gender(str(gender)),
            height_cm=height,
            weight_kg=weight,
        )

    bucket = _map_bucket(str(bucket_raw))
    body_part = _map_pain_area(str(body_part_raw))

    physical_score_override = request.physical_score
    if physical_score_override is None:
        extra_score = extras.get("physicalScore")
        if isinstance(extra_score, dict):
            total = extra_score.get("totalScore") or extra_score.get("total_score")
            physical_score_override = total
        elif extra_score is not None:
            physical_score_override = extra_score

    base_score = None
    if physical_score_override is not None:
        base_score = _clamp_physical_score(int(physical_score_override))

    if request.post_survey or base_score is None:
        total_score = _gpt_physical_score_for_exercise(
            request=request,
            demographics=demographics,
            bucket=bucket,
            body_part=body_part,
            base_score=base_score,
        )
    else:
        total_score = base_score

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
                "difficulty": _map_difficulty_label(ex_dict.get("difficulty")),
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
            "bucket": "OA",
            "bodyPart": "knee",
            "age": 26,
            "gender": "FEMALE",
            "height": 170,
            "weight": 65,
            "physicalScore": 70,
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
            "physicalScore": exercise_input.physical_score.total_score,
            "exercises": exercises_app,
            "recommendationReason": exercise_output.llm_reasoning,
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
        survey_payload = result.survey_data.model_dump(by_alias=True) if result.survey_data else {}
        if result.survey_data and result.survey_data.physical_score:
            survey_payload["physical_score"] = result.survey_data.physical_score.total_score
        diagnosis = result.diagnosis
        diagnosis_payload = {
            "body_part": diagnosis.body_part,
            "final_bucket": diagnosis.final_bucket,
            "confidence": diagnosis.confidence,
            "diagnosisPercentage": diagnosis.diagnosis_percentage,
            "diagnosisType": diagnosis.diagnosis_type,
            "diagnosisDescription": diagnosis.diagnosis_description,
        }
        return {
            "survey_data": survey_payload,
            "diagnosis": diagnosis_payload,
        }
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
