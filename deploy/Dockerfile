# 배포 이미지 (SSH 서버·Hugging Face Space 공용). deploy/deploy.py가 만든 배포 폴더를 그대로 빌드합니다.
# 로컬과 같은 순서: 화면 빌드 → 파이썬 환경 → 사전 계산(engine.build, 리허설 대조 실패 시 빌드 실패) → 서버

# ---------------------------------------------------------------- 1) 화면 빌드 (React → frontend/dist)
FROM node:22-slim AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------- 2) 파이썬 환경 + 사전 계산 + 서버
FROM python:3.12-slim
# LightGBM이 쓰는 OpenMP
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.13.1

WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1

# 의존성은 uv.lock 그대로 (개발·실습용 그룹 제외)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/ backend/
COPY engine/ engine/
COPY analysis/results/ analysis/results/
COPY data/ data/
COPY --from=web /app/frontend/dist frontend/dist

# 사전 계산: 기준일 145개 × 예측·특보·이슈·적체·지연 위험 → data/artifacts (로컬 약 3분)
RUN python -m engine.build

# 서버는 메모리에서만 계산하고 파일을 쓰지 않습니다 (Space는 1000번 사용자로 실행). 7860번 포트
EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "7860"]
