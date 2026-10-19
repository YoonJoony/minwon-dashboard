"""경로 설정. 모든 경로는 프로젝트 루트(minwon-dashboard/) 기준입니다."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:          # 계산 엔진(engine/) 패키지를 불러오기 위해
    sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "data"
RAW_NYC311 = DATA_DIR / "raw" / "nyc311"
RAW_WEATHER = DATA_DIR / "raw" / "weather" / "openmeteo_bronx_daily.csv"
PROCESSED = DATA_DIR / "processed"
ARTIFACTS = DATA_DIR / "artifacts"
FRONTEND_DIST = ROOT / "frontend" / "dist"
