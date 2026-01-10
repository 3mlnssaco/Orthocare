"""Gateway Service - 통합 API 서버

사용법:
    PYTHONPATH=. python -m gateway.main

포트: 8000 (기본)
"""

from contextlib import asynccontextmanager
from datetime import datetime
import os

from dotenv import load_dotenv
load_dotenv(override=True)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gateway.models import UnifiedRequest, UnifiedResponse
from gateway.services import OrchestrationService
from exercise_recommendation.models.input import ExerciseRecommendationInput
from exercise_recommendation.models.output import ExerciseRecommendationOutput


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


def _map_texts_to_symptoms(body_part: str, texts: list[str]) -> list[str]:
    """자유 텍스트를 증상 코드로 매핑 (앱 수정 불가 대응용 간단 매퍼)"""
    # 간단한 포함 매칭 (knee/shoulder만 커버)
    knee_map = {
        "걷": ["after_walking", "weight_bearing_pain"],
        "서있": ["after_walking", "weight_bearing_pain"],
        "계단 내려": ["stairs_down"],
        "계단 올": ["stairs_up"],
        "비틀": ["twisting"],
        "운동 후": ["after_exercise", "overuse_pattern"],
        "무리하게 운동": ["after_exercise", "overuse_pattern"],
        "아침": ["stiffness_morning"],
        "30분": ["stiffness_improves"],
        "붓": ["swelling"],
        "뜨거": ["swelling_heat", "heat"],
        "찌릿": ["sharp_pain"],
        "콕": ["sharp_pain"],
        "뻐근": ["chronic"],
        "묵직": ["chronic"],
        "걸리": ["locking", "catching"],
        "잠김": ["locking"],
        "불안정": ["instability"],
    }
    shoulder_map = {
        "벌리": ["abduction_overhead", "painful_arc"],
        "머리 위": ["abduction_overhead", "painful_arc"],
        "앞으로 들": ["forward_flexion"],
        "뒤로 돌리": ["internal_rotation_behind", "er_limitation"],
        "무거운": ["heavy_lifting"],
        "옆으로 누워": ["lying_on_side", "night_pain"],
        "가만히": ["at_rest", "night_pain"],
        "밤": ["night_pain"],
        "찌릿": ["sharp_pain"],
        "콕": ["sharp_pain"],
        "뻐근": ["dull_heavy", "chronic"],
        "묵직": ["dull_heavy", "chronic"],
        "걸리": ["catching_feeling", "crepitus"],
        "딸깍": ["crepitus"],
        "당기고 뻣뻣": ["stiff_restricted", "rom_limited", "capsular_pattern"],
    }

    mapping = knee_map if body_part == "knee" else shoulder_map if body_part == "shoulder" else {}
    found = []
    for text in texts:
        if not text:
            continue
        for key, codes in mapping.items():
            if key in text:
                found.extend(codes)
    return list(dict.fromkeys(found))  # uniq 순서 유지


def _map_redflags_text(body_part: str, text: str) -> list[str]:
    """자유 텍스트 레드플래그를 코드로 매핑"""
    if not text:
        return []
    text = text.lower()
    mappings = {
        "severe_pain_no_movement": ["거의 들기 어렵", "걷기 어렵", "심한 통증"],
        "acute_swelling_heat": ["갑자기 붓", "뜨겁"],
        "weakness_numbness": ["힘이", "저리", "감각"],
        "radiating_pain_cervical": ["목에서", "팔로", "전기"],
        "fever_chills": ["발열", "오한", "열"],
        "post_injection_pain": ["주사", "이후 통증"],
    }
    found = []
    for code, keys in mappings.items():
        if any(k in text for k in keys):
            found.append(code)
    return found


def _enrich_symptoms_from_text(request: UnifiedRequest) -> UnifiedRequest:
    """앱이 문자열만 줄 때 증상/레드플래그를 최대한 매핑"""
    texts = []
    if request.raw_survey_responses:
        for v in request.raw_survey_responses.values():
            if isinstance(v, str):
                texts.append(v)
    if request.natural_language:
        nl = request.natural_language
        texts.extend(filter(None, [nl.chief_complaint, nl.pain_description, nl.history]))

    new_bps = []
    for bp in request.body_parts:
        symptoms = list(bp.symptoms or [])
        mapped = _map_texts_to_symptoms(bp.code, texts)
        for s in mapped:
            if s not in symptoms:
                symptoms.append(s)

        red_flags = list(bp.red_flags_checked or [])
        rf_text = request.raw_survey_responses.get("redFlags") if request.raw_survey_responses else None
        if isinstance(rf_text, str):
            mapped_rf = _map_redflags_text(bp.code, rf_text)
            for r in mapped_rf:
                if r not in red_flags:
                    red_flags.append(r)

        new_bp = bp.model_copy(update={"symptoms": symptoms, "red_flags_checked": red_flags})
        new_bps.append(new_bp)

    return request.model_copy(update={"body_parts": new_bps})


@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {
        "status": "healthy",
        "service": "gateway",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/api/v1/recommend-exercises", response_model=ExerciseRecommendationOutput)
async def recommend_exercises(request: ExerciseRecommendationInput):
    """운동 추천만 실행 (버킷 추론 생략)

    앱/백엔드에서 이미 버킷과 사전평가가 있을 때 사용
    """
    try:
        exercise_output = orchestration_service.exercise_pipeline.run(request)
        return exercise_output
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=_error_payload(
                e,
                hint="필수 필드(body_part/bucket/physical_score/nrs 등)와 값 범위를 확인하세요.",
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


@app.post("/api/v1/diagnose", response_model=UnifiedResponse)
async def diagnose_only(request: UnifiedRequest):
    """버킷 추론만 실행 (운동 추천 제외)

    운동 추천 없이 버킷 추론 결과만 반환
    """
    try:
        enriched = _enrich_symptoms_from_text(request)
        result = orchestration_service.process_diagnosis_only(enriched)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=_error_payload(
                e,
                hint="필수 필드(demographics/body_parts/symptoms/nrs)와 증상 코드 매핑을 확인하세요.",
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
