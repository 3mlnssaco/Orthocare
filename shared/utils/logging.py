"""공유 로깅 유틸리티"""

import logging
import sys
from typing import Optional


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """로거 인스턴스 반환

    Args:
        name: 로거 이름
        level: 로그 레벨 (기본값: INFO)

    Returns:
        logging.Logger 인스턴스
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)

    logger.setLevel(level or logging.INFO)
    return logger
