FROM python:3.11-slim

WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 공유 모듈 복사
COPY ../shared /app/shared

# 애플리케이션 코드 복사
COPY . /app/bucket_inference

# 데이터 디렉토리는 볼륨으로 마운트
# VOLUME /app/data

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "bucket_inference.main:app", "--host", "0.0.0.0", "--port", "8000"]
