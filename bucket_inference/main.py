"""Bucket Inference FastAPI 서버

Docker Container 1: 버킷 추론 모델
포트: 8001 (외부) → 8000 (내부)
"""

import os
from dotenv import load_dotenv
load_dotenv(override=True)

# LangSmith 프로젝트 분리
os.environ["LANGSMITH_PROJECT"] = "orthocare-bucket-inference"

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bucket_inference.models import BucketInferenceInput, BucketInferenceOutput
from bucket_inference.pipeline import BucketInferencePipeline
from bucket_inference.config import settings

app = FastAPI(
    title="OrthoCare Bucket Inference",
    description="버킷 추론 모델 API (2주 1회 사용)",
    version="1.0.0",
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 파이프라인 인스턴스
pipeline = BucketInferencePipeline()


@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {"status": "healthy", "service": "bucket-inference"}


@app.post("/api/v1/infer-bucket")
async def infer_bucket(input_data: BucketInferenceInput):
    """
    버킷 추론 API

    사용 빈도: 2주 1회

    입력:
    - demographics: 인구통계학적 정보
    - body_parts: 부위별 증상 입력
    - natural_language: 자연어 입력 (선택)

    출력:
    - 부위별 BucketInferenceOutput
    """
    try:
        results = pipeline.run(input_data)

        # 단일 부위인 경우 직접 반환
        if len(results) == 1:
            return list(results.values())[0]

        # 다중 부위인 경우 딕셔너리 반환
        return {"results": {k: v.model_dump() for k, v in results.items()}}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/infer-bucket/{body_part}")
async def infer_bucket_single(body_part: str, input_data: BucketInferenceInput):
    """단일 부위 버킷 추론"""
    try:
        result = pipeline.run_single(input_data, body_part)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "bucket_inference.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
