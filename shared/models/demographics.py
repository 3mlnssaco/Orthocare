"""인구통계학적 정보 모델 (공유)"""

from typing import Literal
from pydantic import BaseModel, Field


class Demographics(BaseModel):
    """인구통계학적 정보"""

    age: int = Field(..., ge=10, le=100, description="나이")
    sex: Literal["male", "female", "prefer_not_to_say"] = Field(
        ..., description="성별 (male/female/prefer_not_to_say)"
    )
    height_cm: float = Field(..., ge=100, le=250, description="키 (cm)")
    weight_kg: float = Field(..., ge=30, le=200, description="몸무게 (kg)")

    @property
    def bmi(self) -> float:
        """BMI 계산"""
        height_m = self.height_cm / 100
        return round(self.weight_kg / (height_m**2), 1)

    @property
    def age_code(self) -> str:
        """연령대 코드 반환"""
        if self.age >= 60:
            return "age_gte_60"
        elif self.age >= 50:
            return "age_gte_50"
        elif self.age >= 40:
            return "age_40s"
        elif self.age >= 30:
            return "age_30s"
        elif self.age >= 20:
            return "age_20s"
        else:
            return "age_teens"

    @property
    def bmi_code(self) -> str:
        """BMI 코드 반환"""
        bmi = self.bmi
        if bmi >= 30:
            return "bmi_gte_30"
        elif bmi >= 27:
            return "bmi_gte_27"
        elif bmi >= 25:
            return "bmi_gte_25"
        else:
            return "bmi_normal"

    @property
    def sex_code(self) -> str:
        """성별 코드 반환"""
        return f"sex_{self.sex}"
