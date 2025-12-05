"""Shared module - 버킷 추론과 운동 추천 모델이 공유하는 모듈"""

from shared.models.demographics import Demographics
from shared.models.body_part import BodyPartInput, PhysicalScore

__all__ = [
    "Demographics",
    "BodyPartInput",
    "PhysicalScore",
]
