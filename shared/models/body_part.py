"""부위별 입력 및 신체 점수 모델 (공유)"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator


class PhysicalScore(BaseModel):
    """신체 점수 (Lv A/B/C/D) - 신체 자가평가 4문항 총점

    사전 평가 4문항:
    1. 한발 서기 유지 시간 (1-4점)
    2. 앉았다 일어서기 횟수/30초 (1-4점)
    3. 계단 오르내리기 자신감 (1-4점)
    4. 걷기 지속 시간 (1-4점)

    총점 범위: 4-16점
    """

    total_score: int = Field(..., ge=4, le=16, description="총점 (4-16)")

    @property
    def level(self) -> Literal["A", "B", "C", "D"]:
        """
        점수에 따른 레벨 반환
        - A: 14-16점 (상위 근력)
        - B: 11-13점 (평균 이상)
        - C: 8-10점 (기본 기능)
        - D: 4-7점 (기능 저하)
        """
        if self.total_score >= 14:
            return "A"
        elif self.total_score >= 11:
            return "B"
        elif self.total_score >= 8:
            return "C"
        else:
            return "D"

    @property
    def allowed_difficulties(self) -> List[str]:
        """허용된 운동 난이도"""
        level_map = {
            "A": ["low", "medium", "high"],
            "B": ["low", "medium", "high"],
            "C": ["low", "medium"],
            "D": ["low"],
        }
        return level_map[self.level]


class BodyPartInput(BaseModel):
    """부위별 입력"""

    code: str = Field(..., description="부위 코드 (knee, shoulder 등)")
    primary: bool = Field(default=True, description="주요 부위 여부")
    side: Optional[Literal["left", "right", "both"]] = Field(
        default=None, description="좌우 구분"
    )
    symptoms: List[str] = Field(default_factory=list, description="증상 코드 리스트")
    nrs: int = Field(..., ge=0, le=10, description="통증 점수 (0-10)")
    red_flags_checked: List[str] = Field(
        default_factory=list, description="확인된 레드플래그"
    )

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        valid_codes = ["knee", "shoulder", "back", "neck", "ankle"]
        if v not in valid_codes:
            raise ValueError(f"지원하지 않는 부위: {v}. 가능한 값: {valid_codes}")
        return v
