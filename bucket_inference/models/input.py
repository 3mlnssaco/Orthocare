"""버킷 추론 입력 모델"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

import sys
sys.path.insert(0, str(__file__).rsplit("/", 3)[0])

from shared.models import Demographics, BodyPartInput


class NaturalLanguageInput(BaseModel):
    """사용자 자연어 입력"""

    chief_complaint: Optional[str] = Field(
        default=None,
        description="주호소 - 사용자가 직접 입력한 증상 설명"
    )
    pain_description: Optional[str] = Field(
        default=None,
        description="통증 설명 - 언제, 어떻게, 어디가 아픈지"
    )
    history: Optional[str] = Field(
        default=None,
        description="병력 - 이전 치료, 부상 경험 등"
    )

    @property
    def has_content(self) -> bool:
        """내용이 있는지 확인"""
        return any([
            self.chief_complaint,
            self.pain_description,
            self.history,
        ])

    def to_text(self) -> str:
        """전체 텍스트로 변환 (LLM 컨텍스트용)"""
        parts = []
        if self.chief_complaint:
            parts.append(f"주호소: {self.chief_complaint}")
        if self.pain_description:
            parts.append(f"통증 설명: {self.pain_description}")
        if self.history:
            parts.append(f"병력: {self.history}")
        return "\n".join(parts) if parts else ""


class BucketInferenceInput(BaseModel):
    """버킷 추론 입력

    API 엔드포인트: POST /api/v1/infer-bucket
    사용 빈도: 2주 1회

    예시:
    {
        "demographics": {"age": 55, "sex": "male", "height_cm": 175, "weight_kg": 80},
        "body_parts": [{"code": "knee", "symptoms": ["pain_stairs", "stiffness_morning"], "nrs": 6}],
        "natural_language": {"chief_complaint": "무릎이 아파요"}
    }
    """

    demographics: Demographics = Field(..., description="인구통계학적 정보")
    body_parts: List[BodyPartInput] = Field(
        ...,
        min_length=1,
        description="부위별 증상 입력"
    )
    natural_language: Optional[NaturalLanguageInput] = Field(
        default=None,
        description="자연어 입력 (선택)"
    )
    survey_responses: Optional[Dict[str, Any]] = Field(
        default=None,
        description="원본 설문 응답 (디버깅용)"
    )

    @property
    def primary_body_part(self) -> BodyPartInput:
        """주요 부위 반환"""
        for bp in self.body_parts:
            if bp.primary:
                return bp
        return self.body_parts[0]

    @property
    def is_multi_body_part(self) -> bool:
        """복합 부위 여부"""
        return len(self.body_parts) > 1

    def get_all_symptoms(self) -> List[str]:
        """모든 증상 코드 반환 (인구통계 포함)"""
        symptoms = [
            self.demographics.sex_code,
            self.demographics.age_code,
            self.demographics.bmi_code,
        ]
        for bp in self.body_parts:
            symptoms.extend(bp.symptoms)
        return list(set(symptoms))
