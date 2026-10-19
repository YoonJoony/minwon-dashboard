"""민원 조기경보 대시보드 API.

실행 (프로젝트 루트에서):
    uv run uvicorn app.main:app --app-dir backend --reload

- API 문서: http://127.0.0.1:8000/docs
- 프런트엔드를 빌드(frontend/dist)해 두면 같은 서버의 / 에서 화면도 내보냅니다.
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import config

app = FastAPI(title="민원 조기경보 대시보드 API", version="0.1.0")


@app.get("/api/health")
def health() -> dict:
    """서버 상태와 필요한 데이터 파일이 있는지 알려 줍니다."""
    return {
        "status": "ok",
        "data": {
            "311 월별 원본": any(config.RAW_NYC311.glob("nyc311_*.csv")),
            "기상 원본": config.RAW_WEATHER.exists(),
            "날짜×기관 병합": (config.PROCESSED / "daily_agency_weather.csv").exists(),
            "날짜×이슈 병합": (config.PROCESSED / "daily_issue_weather.csv").exists(),
        },
    }


# API 라우트를 먼저 등록한 뒤 화면 파일을 붙여야 /api 요청이 가려지지 않습니다.
if config.FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=config.FRONTEND_DIST, html=True), name="frontend")
