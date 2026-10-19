"""경로 설정. 모든 경로는 프로젝트 루트(minwon-dashboard/) 기준입니다."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_NYC311 = DATA_DIR / "raw" / "nyc311"
RAW_WEATHER = DATA_DIR / "raw" / "weather" / "openmeteo_bronx_daily.csv"
PROCESSED = DATA_DIR / "processed"
FRONTEND_DIST = ROOT / "frontend" / "dist"
