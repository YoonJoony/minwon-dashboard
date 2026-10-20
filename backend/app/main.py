"""스마트 민원케어 — 민원 조기경보 대시보드 API.

실행 (프로젝트 루트에서):
    uv run python -m engine.build                                  # 사전 계산 (처음 한 번)
    uv run uvicorn app.main:app --app-dir backend --reload         # 개발
- API 문서: http://127.0.0.1:8000/docs
- 프런트엔드를 빌드(frontend/dist)해 두면 같은 서버의 / 에서 화면도 내보냅니다.

모든 응답은 기준일(asof)까지의 데이터와 그날 발표된 예보만으로 계산한 값입니다.
"""
from typing import Annotated

from fastapi import Depends, FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import config, schemas
from app.store import Store, get_store
from engine.config import AGENCIES, PER_PERSON_DEFAULT

app = FastAPI(
    title="스마트 민원케어 API",
    version="0.2.0",
    description="부서·기간별 민원 집중도(예상 건수, 예상 이슈, 위험 매트릭스, 인력 지원)를 제공합니다. "
                "데이터: 뉴욕시 311 브롱크스, Open-Meteo 기상, 미국 기상청 뉴욕 지청 특보 기준.",
)

StoreDep = Annotated[Store, Depends(get_store)]
AsOf = Annotated[str, Query(description="기준일 (YYYY-MM-DD). /api/meta의 asofs 중 하나")]
Start = Annotated[str | None, Query(description="기간 시작 (기본: 기준일)")]
End = Annotated[str | None, Query(description="기간 끝 (기본: 기준일 + 6일, 최대 기준일 + 91일)")]
AgencyQ = Annotated[str | None, Query(description=f"부서 코드 ({', '.join(AGENCIES)}). 없으면 전체", pattern="^(" + "|".join(AGENCIES) + ")$")]
PerPerson = Annotated[float, Query(description="가정값: 1인당 하루 처리 건수", gt=0, le=200)]


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
            "사전 계산 결과": (config.ARTIFACTS / "manifest.json").exists(),
        },
    }


@app.get("/api/meta", response_model=schemas.Meta)
def meta(store: StoreDep):
    """부서 목록, 기준일 목록, 시연 시나리오, 기간 빠른 선택, 매트릭스 기준값."""
    return store.meta()


@app.get("/api/summary", response_model=schemas.SummaryOut)
def summary(store: StoreDep, asof: AsOf, start: Start = None, end: End = None, agency: AgencyQ = None,
            per_person_day: PerPerson = PER_PERSON_DEFAULT):
    """상단 핵심 지표: 예상 접수, 기상 특보, 집중관리 부서, 처리 중 민원, 지원 필요 인원."""
    return store.summary(asof, start, end, agency, per_person_day)


@app.get("/api/forecast", response_model=schemas.ForecastOut)
def forecast(store: StoreDep, asof: AsOf, start: Start = None, end: End = None, agency: AgencyQ = None):
    """선택 기간 예상 접수 건수, 80% 범위, 부서별 값, 추이(직전 실적 + 기간 예측)."""
    return store.forecast(asof, start, end, agency)


@app.get("/api/issues", response_model=schemas.IssuesOut)
def issues(store: StoreDep, asof: AsOf, start: Start = None, end: End = None, agency: AgencyQ = None):
    """예상 이슈: 향후 7일 기상 특보 예보, 겨울 적설 → 봄 도로 파손, 같은 시기 이슈 급증 빈도."""
    return store.issues(asof, start, end, agency)


@app.get("/api/matrix", response_model=schemas.MatrixOut)
def risk_matrix(store: StoreDep, asof: AsOf, start: Start = None, end: End = None):
    """부서 위험 매트릭스: 가로 접수 증가율, 세로 적체 배수, 사분면, 특보 표시, 80% 범위."""
    return store.matrix(asof, start, end)


@app.get("/api/staffing", response_model=schemas.StaffingOut)
def staffing(store: StoreDep, asof: AsOf, start: Start = None, end: End = None,
             per_person_day: PerPerson = PER_PERSON_DEFAULT):
    """인력 지원: 부서별 예상 적체 증가 건수, 지원 필요 인원(가정값), 지원 가능 부서와 짝."""
    return store.staffing(asof, start, end, per_person_day)


@app.get("/api/risk-list", response_model=schemas.RiskOut)
def risk_list(store: StoreDep, asof: AsOf, agency: AgencyQ = None,
              limit: Annotated[int, Query(ge=1, le=40)] = 15):
    """지연 위험 민원: 기준일에 처리 중인 민원 중 늦어질 가능성이 큰 순서."""
    return store.risk(asof, agency, limit)


@app.get("/api/weather/strip", response_model=schemas.WeatherStripOut)
def weather_strip(store: StoreDep, asof: AsOf):
    """7일 기상 예보 띠: 기준일 포함 8일의 날씨 아이콘·기온·강수, 특보 수준(예보 판정), 기준일까지 발표된 NWS 특보."""
    return store.weather_strip(asof)


@app.get("/api/weather/day", response_model=schemas.WeatherDayOut)
def weather_day(store: StoreDep, asof: AsOf, date: Annotated[str, Query(description="예보 띠에서 고른 날짜 (기준일 ~ +7일)")]):
    """예보 띠에서 고른 날: 그날 예보와, 같은 기상 이슈의 과거 7년 실제 민원 접수·처리 (특보 종류별 탭)."""
    return store.weather_day(asof, date)


@app.get("/api/evidence", response_model=schemas.EvidenceOut)
def evidence(store: StoreDep):
    """화면 수치의 검증 근거."""
    return store.evidence()


# API 라우트를 먼저 등록한 뒤 화면 파일을 붙여야 /api 요청이 가려지지 않습니다.
if config.FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        """화면(React) 파일. 주소에 기준일·기간이 붙어도 index.html을 돌려줍니다."""
        f = config.FRONTEND_DIST / path
        return FileResponse(f if path and f.is_file() else config.FRONTEND_DIST / "index.html")
