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
        # 앱 입력을 그대로 사용해 추론 (자동 매핑/변환 없음)
        result = orchestration_service.process_diagnosis_only(request)
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
