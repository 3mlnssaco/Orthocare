"""App-facing request models for Gateway endpoints."""

from datetime import date
from typing import Optional, Literal, List

from pydantic import BaseModel, Field, ConfigDict


class AppDiagnoseRequest(BaseModel):
    """앱 버킷 추론 요청 스키마 (요구 필드만 노출)"""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
        json_schema_extra={
            "example": {
                "birthDate": "2000-01-01",
                "height": 170,
                "weight": 65,
                "gender": "FEMALE",
                "painArea": "무릎",
                "affectedSide": "양쪽",
                "painStartedDate": "무리하게 운동한 이후부터 아파요",
                "painLevel": 6,
                "painTrigger": "계단 내려갈 때",
                "painSensation": "뻐근함",
                "painDuration": "30분 이상",
                "redFlags": ""
            }
        },
    )

    birth_date: date = Field(..., alias="birthDate", description="생년월일 (YYYY-MM-DD)")
    height: int = Field(..., description="키 (cm)")
    weight: int = Field(..., description="몸무게 (kg)")
    gender: Literal["MALE", "FEMALE", "PREFER_NOT_TO_SAY"] = Field(
        ..., description="성별 (MALE/FEMALE/PREFER_NOT_TO_SAY)"
    )

    pain_area: str = Field(..., alias="painArea", description="통증 부위")
    affected_side: str = Field(..., alias="affectedSide", description="아픈 쪽")
    pain_started_date: str = Field(..., alias="painStartedDate", description="언제부터 아팠는지")
    pain_level: int = Field(..., alias="painLevel", ge=0, le=10, description="통증 정도 (0-10)")
    pain_trigger: str = Field(..., alias="painTrigger", description="언제 통증이 더 심해지는지")
    pain_sensation: str = Field(..., alias="painSensation", description="어떤 느낌으로 아픈지")
    pain_duration: str = Field(..., alias="painDuration", description="통증 지속 시간")
    red_flags: Optional[str] = Field(default=None, alias="redFlags", description="위험 신호")

class AppExerciseRequest(BaseModel):
    """앱 운동 추천 요청 스키마 (요구 필드만 노출)"""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
        json_schema_extra={
            "example": {
                "userId": 1,
                "routineDate": "2025-01-11",
                "painLevel": 5,
                "squatResponse": "10개",
                "pushupResponse": "5개",
                "stepupResponse": "15개",
                "plankResponse": "30초",
                "rpeResponse": None,
                "muscleStimulationResponse": None,
                "sweatResponse": None
            }
        },
    )

    user_id: str = Field(..., alias="userId", description="유저 ID")
    routine_date: date = Field(..., alias="routineDate", description="루틴 날짜 (YYYY-MM-DD)")
    pain_level: int = Field(..., alias="painLevel", ge=0, le=10, description="일일 통증 정도 (0-10)")
    squat_response: str = Field(..., alias="squatResponse", description="스쿼트 가능 횟수")
    pushup_response: str = Field(..., alias="pushupResponse", description="푸시업 가능 횟수")
    stepup_response: str = Field(..., alias="stepupResponse", description="스텝업 가능 횟수")
    plank_response: str = Field(..., alias="plankResponse", description="플랭크 가능 시간")

    rpe_response: Optional[str] = Field(default=None, alias="rpeResponse")
    muscle_stimulation_response: Optional[str] = Field(
        default=None, alias="muscleStimulationResponse"
    )
    sweat_response: Optional[str] = Field(default=None, alias="sweatResponse")


class AppExerciseItem(BaseModel):
    """앱 운동 추천 응답 아이템"""

    exercise_id: str = Field(..., alias="exerciseId")
    name_ko: str = Field(..., alias="nameKo")
    difficulty: str
    recommended_sets: int = Field(..., alias="recommendedSets")
    recommended_reps: int | str = Field(..., alias="recommendedReps")
    exercise_order: int = Field(..., alias="exerciseOrder")
    video_url: Optional[str] = Field(default=None, alias="videoUrl")


class AppExerciseResponse(BaseModel):
    """앱 운동 추천 응답 스키마"""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    user_id: str = Field(..., alias="userId")
    routine_date: date = Field(..., alias="routineDate")
    exercises: List[AppExerciseItem]
