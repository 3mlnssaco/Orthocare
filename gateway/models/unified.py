"""통합 API 요청/응답 모델

앱 → 서버 한 번의 요청으로:
1. 버킷 추론
2. 운동 추천 (선택)
3. 백엔드 저장용 데이터 반환
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
import uuid

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.models import Demographics, BodyPartInput, PhysicalScore
from bucket_inference.models import (
    BucketInferenceOutput,
    RedFlagResult,
)
from bucket_inference.models.input import NaturalLanguageInput
from exercise_recommendation.models.output import ExerciseRecommendationOutput


class RequestOptions(BaseModel):
    """요청 옵션"""

    include_exercises: bool = Field(
        default=True,
        description="운동 추천 포함 여부 (False면 버킷 추론만)"
    )
    exercise_days: int = Field(
        default=3,
        ge=1, le=7,
        description="운동 커리큘럼 일수"
    )
    skip_exercise_on_red_flag: bool = Field(
        default=True,
        description="Red Flag 시 운동 추천 스킵"
    )


class DiagnosisContext(BaseModel):
    """버킷 추론 컨텍스트 (운동 추천 개인화용)

    버킷 추론의 상세 정보를 운동 추천에 전달하여
    더 정교한 개인화 수행
    """

    # 핵심 결과
    bucket: str = Field(..., description="최종 버킷 (OA/OVR/TRM/INF/STF)")
    confidence: float = Field(..., description="추론 신뢰도 (0-1)")

    # LLM 추론 정보
    llm_reasoning: str = Field(
        default="",
        description="LLM 판단 근거 (운동 개인화에 활용)"
    )
    evidence_summary: str = Field(
        default="",
        description="근거 요약"
    )

    # 점수 정보
    bucket_scores: Dict[str, float] = Field(
        default_factory=dict,
        description="버킷별 점수"
    )
    contributing_symptoms: List[str] = Field(
        default_factory=list,
        description="주요 기여 증상들 (운동 우선순위 결정에 활용)"
    )

    # 검색 결과
    weight_ranking: List[str] = Field(
        default_factory=list,
        description="가중치 기반 순위"
    )
    search_ranking: List[str] = Field(
        default_factory=list,
        description="근거 검색 기반 순위"
    )

    @classmethod
    def from_bucket_output(
        cls,
        output: BucketInferenceOutput,
        symptoms: List[str] = None,
    ) -> "DiagnosisContext":
        """BucketInferenceOutput에서 생성"""
        # 기여 증상 추출 (상위 버킷 점수에 기여한 증상)
        contributing = symptoms or []

        return cls(
            bucket=output.final_bucket,
            confidence=output.confidence,
            llm_reasoning=output.llm_reasoning,
            evidence_summary=output.evidence_summary,
            bucket_scores=output.bucket_scores,
            contributing_symptoms=contributing,
            weight_ranking=output.weight_ranking,
            search_ranking=output.search_ranking,
        )


class SurveyData(BaseModel):
    """원본 설문 데이터 (백엔드 저장용)

    앱에서 서버로 보낸 설문 데이터를 그대로 반환하여
    백엔드에서 유저 프로필에 저장할 수 있도록 함
    """

    demographics: Demographics
    body_parts: List[BodyPartInput]
    natural_language: Optional[NaturalLanguageInput] = None
    physical_score: Optional[PhysicalScore] = None
    raw_responses: Optional[Dict[str, Any]] = Field(
        default=None,
        description="앱 설문 원본 응답 (key-value)"
    )


class UnifiedRequest(BaseModel):
    """통합 API 요청

    앱에서 서버로 보내는 단일 요청으로 버킷 추론을 처리
    """

    # 요청 식별
    request_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="요청 고유 ID (중복 방지, 캐싱용)"
    )
    user_id: str = Field(..., description="사용자 ID")

    # 필수 입력
    demographics: Demographics = Field(..., description="인구통계학적 정보")
    body_parts: List[BodyPartInput] = Field(
        ...,
        min_length=1,
        description="부위별 증상 입력"
    )

    # 운동 추천용 (선택이지만 운동 추천 시 필요)
    physical_score: Optional[PhysicalScore] = Field(
        default=None,
        description="신체 점수 (0-100, 운동 추천 시 필요)"
    )

    # 자연어 입력 (선택)
    natural_language: Optional[NaturalLanguageInput] = Field(
        default=None,
        description="자연어 입력"
    )

    # 원본 설문 (백엔드 저장용)
    raw_survey_responses: Optional[Dict[str, Any]] = Field(
        default=None,
        description="앱 설문 원본 응답"
    )

    # 옵션
    options: RequestOptions = Field(
        default_factory=RequestOptions,
        description="요청 옵션"
    )

    @property
    def primary_body_part(self) -> BodyPartInput:
        """주요 부위"""
        for bp in self.body_parts:
            if bp.primary:
                return bp
        return self.body_parts[0]

    @property
    def primary_nrs(self) -> int:
        """주요 부위 NRS"""
        return self.primary_body_part.nrs

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "demo_user_001",
                "demographics": {
                    "age": 55,
                    "sex": "female",
                    "height_cm": 160,
                    "weight_kg": 65
                },
                "body_parts": [
                    {
                        "code": "knee",
                        "primary": True,
                        "side": "both",
                        "symptoms": ["pain_medial", "stiffness_morning", "stairs_down"],
                        "nrs": 6,
                        "red_flags_checked": []
                    }
                ],
                "natural_language": {
                    "chief_complaint": "오른쪽 무릎 안쪽이 아파요",
                    "pain_description": "계단 내려갈 때 뻐근하고 아침에 30분 정도 뻣뻣합니다",
                    "history": "무리하게 운동한 이후부터 아파요"
                },
                "raw_survey_responses": {
                    "painStarted": "무리하게 운동한 이후부터 아파요",
                    "painTrigger": "오래 걷거나 서있을 때",
                    "painSensation": "뻐근/묵직",
                    "painDuration": "아침에 30분 정도"
                }
            }
        }


class DiagnosisResult(BaseModel):
    """버킷 추론 결과 (응답용)"""

    model_config = ConfigDict(populate_by_name=True)

    body_part: str
    final_bucket: str
    confidence: float
    bucket_scores: Dict[str, float]
    weight_ranking: List[str]
    search_ranking: List[str]
    evidence_summary: str
    llm_reasoning: str
    red_flag: Optional[RedFlagResult] = None
    inferred_at: datetime

    # 앱 호환 필드 (선택)
    diagnosis_percentage: Optional[int] = Field(
        default=None, alias="diagnosisPercentage", description="진단 확률 (0-100)"
    )
    diagnosis_type: Optional[str] = Field(
        default=None,
        alias="diagnosisType",
        description="진단 유형 (버킷 코드: OA/OVR/TRM/INF/STF)",
    )
    diagnosis_description: Optional[str] = Field(
        default=None, alias="diagnosisDescription", description="진단 설명 (사용자용)"
    )
    physical_score: Optional[int] = Field(
        default=None,
        alias="physicalScore",
        description="신체 점수 (0-100)",
    )

    @classmethod
    def from_bucket_output(
        cls,
        output: BucketInferenceOutput,
        physical_score: Optional[PhysicalScore] = None,
    ) -> "DiagnosisResult":
        """BucketInferenceOutput에서 생성"""
        # 버킷 → 설명 매핑 (부위별)
        bucket_desc_map = {
            "knee": {
                "OA": "무릎 연골이 약해지고 아침에 뻣뻣하며 점진적으로 통증이 나타나는 패턴",
                "OVR": "반복 사용/운동량 증가 후 앞무릎 통증이 심해지는 패턴",
                "TRM": "넘어짐·비틀림 등 외상 이후 급성 통증과 붓기가 동반되는 패턴",
                "INF": "염증·붓기·열감이 있고 아침 강직이 두드러지는 패턴",
            },
            "shoulder": {
                "OA": "어깨 관절 퇴행으로 뻣뻣함과 통증이 서서히 심해지는 패턴",
                "OVR": "팔을 올리거나 반복 사용 후 통증이 악화되는 과사용 패턴",
                "TRM": "외상 이후 힘 빠짐 또는 급성 통증이 동반되는 패턴",
                "STF": "야간통과 가동범위 제한이 특징인 경직/동결견 패턴",
            },
        }
        diag_desc = bucket_desc_map.get(output.body_part, {}).get(
            output.final_bucket, "해당 버킷 설명을 준비 중입니다."
        )
        diag_type = output.final_bucket
        physical_score_value = physical_score.total_score if physical_score else None

        return cls(
            body_part=output.body_part,
            final_bucket=output.final_bucket,
            confidence=output.confidence,
            bucket_scores=output.bucket_scores,
            weight_ranking=output.weight_ranking,
            search_ranking=output.search_ranking,
            evidence_summary=output.evidence_summary,
            llm_reasoning=output.llm_reasoning,
            red_flag=output.red_flag,
            inferred_at=output.inferred_at,
            diagnosis_percentage=int(round(output.confidence * 100)),
            diagnosis_type=diag_type,
            diagnosis_description=diag_desc,
            physical_score=physical_score_value,
        )


class ExercisePlanResult(BaseModel):
    """운동 추천 결과 (응답용)"""

    body_part: str
    bucket: str
    exercises: List[Dict[str, Any]]  # RecommendedExercise를 dict로
    routine_order: List[str]
    total_duration_min: int
    difficulty_level: str
    llm_reasoning: str
    personalization_note: Optional[str] = None
    recommended_at: datetime

    # 앱 호환 필드 (선택)
    routine_date: Optional[str] = Field(
        default=None, description="루틴 날짜 (YYYY-MM-DD)"
    )
    exercises_app: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="앱 스펙 호환 운동 목록 (exerciseId/nameKo/recommendedSets 등)"
    )

    @classmethod
    def from_exercise_output(
        cls,
        output: ExerciseRecommendationOutput,
        personalization_note: str = None,
    ) -> "ExercisePlanResult":
        """ExerciseRecommendationOutput에서 생성"""
        difficulty_map = {
            "beginner": "기초 단계",
            "standard": "표준 단계",
            "advanced": "강화 단계",
            "expert": "심화 단계",
            "low": "기초 단계",
            "medium": "표준 단계",
            "high": "강화 단계",
            "mixed": "표준 단계",
            "intermediate": "표준 단계",
        }

        # 앱 호환용 exercise 필드 생성
        exercises_app = []
        for idx, ex in enumerate(output.exercises, start=1):
            ex_dict = ex.model_dump()
            raw_diff = ex_dict.get("difficulty")
            diff_key = str(raw_diff).lower() if raw_diff is not None else None
            exercises_app.append(
                {
                    "exerciseId": ex_dict.get("exercise_id"),
                    "nameKo": ex_dict.get("name_kr"),
                    "difficulty": difficulty_map.get(diff_key, raw_diff),
                    "recommendedSets": ex_dict.get("sets"),
                    "recommendedReps": ex_dict.get("reps"),
                    "exerciseOrder": idx,
                    "videoUrl": ex_dict.get("youtube"),
                }
            )

        return cls(
            body_part=output.body_part,
            bucket=output.bucket,
            exercises=[ex.model_dump() for ex in output.exercises],
            routine_order=output.routine_order,
            total_duration_min=output.total_duration_min,
            difficulty_level=output.difficulty_level,
            llm_reasoning=output.llm_reasoning,
            personalization_note=personalization_note,
            recommended_at=output.recommended_at,
            routine_date=output.recommended_at.date().isoformat(),
            exercises_app=exercises_app,
        )


class UnifiedResponse(BaseModel):
    """통합 API 응답

    앱이 이 응답 전체를 백엔드에 저장하면 됨

    구성:
    1. survey_data: 원본 설문 (유저 프로필용)
    2. diagnosis: 버킷 추론 결과
    3. exercise_plan: 운동 추천 결과 (선택)
    4. metadata: 요청/응답 메타데이터
    """

    # 요청 식별
    request_id: str = Field(..., description="요청 고유 ID")
    user_id: str = Field(..., description="사용자 ID")

    # 원본 설문 데이터 (백엔드 저장용)
    survey_data: SurveyData = Field(..., description="원본 설문 데이터")

    # 버킷 추론 결과
    diagnosis: DiagnosisResult = Field(..., description="버킷 추론 결과")

    # 운동 추천 결과 (선택)
    exercise_plan: Optional[ExercisePlanResult] = Field(
        default=None,
        description="운동 추천 결과 (red_flag 시 null)"
    )

    # 처리 상태
    status: str = Field(
        default="success",
        description="처리 상태 (success, partial, error)"
    )
    message: Optional[str] = Field(
        default=None,
        description="상태 메시지 (red_flag 경고 등)"
    )

    # 메타데이터
    processed_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="처리 완료 시간"
    )
    processing_time_ms: Optional[int] = Field(
        default=None,
        description="총 처리 시간 (밀리초)"
    )

    @property
    def has_red_flag(self) -> bool:
        """Red Flag 여부"""
        return (
            self.diagnosis.red_flag is not None
            and self.diagnosis.red_flag.triggered
        )

    @property
    def has_exercise_plan(self) -> bool:
        """운동 추천 포함 여부"""
        return self.exercise_plan is not None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        json_schema_extra = {
            "example": {
                "request_id": "34568a35-9810-4afa-9cda-7805a8807550",
                "user_id": "demo_user_001",
                "survey_data": {
                    "demographics": {
                        "age": 55,
                        "sex": "female",
                        "height_cm": 160,
                        "weight_kg": 65
                    },
                    "body_parts": [
                        {
                            "code": "knee",
                            "primary": True,
                            "side": "both",
                            "symptoms": [
                                "pain_medial",
                                "stiffness_morning",
                                "stairs_down"
                            ],
                            "nrs": 6,
                            "red_flags_checked": []
                        }
                    ],
                    "natural_language": {
                        "chief_complaint": "오른쪽 무릎 안쪽이 아파요",
                        "pain_description": "계단 내려갈 때 뻐근하고 아침에 30분 정도 뻣뻣합니다",
                        "history": "무리하게 운동한 이후부터 아파요"
                    },
                    "physical_score": None,
                    "raw_responses": {
                        "painDuration": "아침에 30분 정도",
                        "painSensation": "뻐근/묵직",
                        "painStarted": "무리하게 운동한 이후부터 아파요",
                        "painTrigger": "오래 걷거나 서있을 때"
                    }
                },
                "diagnosis": {
                    "body_part": "knee",
                    "final_bucket": "OA",
                    "confidence": 0.75,
                    "diagnosis_percentage": 75,
                    "diagnosis_type": "OA",
                    "diagnosis_description": "퇴행성 관절염 패턴: 아침 뻣뻣함, 점진적 통증",
                    "bucket_scores": {
                        "OA": 6,
                        "OVR": 3,
                        "INF": 2,
                        "TRM": 0.5
                    },
                    "weight_ranking": ["OA", "OVR", "INF", "TRM"],
                    "search_ranking": ["OA", "OVR"],
                    "evidence_summary": "55세 여성 환자는 무릎의 내측 통증, 아침 뻣뻣함, 계단 내려갈 때 통증을 호소합니다. 이는 퇴행성관절염의 전형적인 증상입니다.",
                    "llm_reasoning": "환자의 나이와 증상은 퇴행성관절염(OA)의 전형적인 프로필과 일치합니다. 특히, 아침 뻣뻣함과 계단 내려갈 때의 통증은 OA의 일반적인 증상입니다.",
                    "red_flag": None,
                    "inferred_at": "2026-01-10T06:39:01.212125"
                },
                "exercise_plan": None,
                "status": "success",
                "message": None,
                "processed_at": "2026-01-10T06:39:01.214129",
                "processing_time_ms": 4942
            }
        }
