# 민원 조기경보 대시보드

부서와 기간을 선택하면 그 기간의 **민원 집중도(예상 건수, 예상 이슈, 2×2 위험 매트릭스)** 를 미리 보여 주고, 집중도가 높은 부서에 인력을 연결하도록 돕는 행정 지원 대시보드입니다. 전무님 평가용 시연을 목표로 합니다.

- 기획 기준 문서: [docs/서비스기획_정리.md](docs/서비스기획_정리.md)
- 검증 결과 (10년치): [docs/검증결과_10년.md](docs/검증결과_10년.md)
- 데이터 설명: [data/NYC311_컬럼설명.md](data/NYC311_컬럼설명.md), [data/processed/README.md](data/processed/README.md)

## 구성

```
minwon-dashboard/
├─ pyproject.toml       Python 패키지 (uv로 관리, Python 3.12)
├─ backend/app/         FastAPI 서버
├─ frontend/            React + TypeScript (Vite) + ECharts
├─ pipelines/           데이터 수집·병합 스크립트
├─ analysis/            검증 스크립트 (결과는 analysis/results/)
├─ data/
│  ├─ raw/nyc311/       뉴욕 311 브롱크스 월별 원본 (2016-01 ~ 2026-10)
│  ├─ raw/weather/      Open-Meteo 일별 기상 (2016-01-01 ~ 2026-10-13)
│  └─ processed/        병합 결과
└─ docs/                기획·검증 문서
```

`data/raw`, `data/processed`의 데이터 파일은 git에 넣지 않습니다.

## 실행

### 처음 한 번
```bash
brew install uv libomp      # uv(파이썬 관리), libomp(LightGBM용)
uv sync                     # Python 3.12 가상환경과 패키지 설치
cd frontend && npm install
```

### 개발 모드 (화면 수정이 바로 반영됨)
```bash
uv run uvicorn app.main:app --app-dir backend --reload    # API: http://127.0.0.1:8000/docs
cd frontend && npm run dev                                 # 화면: http://localhost:5173
```

### 시연 모드 (서버 하나로 실행)
```bash
cd frontend && npm run build && cd ..
uv run uvicorn app.main:app --app-dir backend               # http://127.0.0.1:8000
```

## 데이터 다시 만들기

```bash
# 뉴욕 311 (이미 받은 달은 건너뜀)
uv run python pipelines/fetch_nyc311.py --start 2016-01-01 --end 2026-10-13 --borough BRONX \
    --agency DSNY DEP DOT DOB DOHMH DPR DCWP DCA DHS
# 기상
uv run python pipelines/fetch_openmeteo.py --start 2016-01-01 --end 2026-10-13
# 병합 (월별 폴더를 그대로 읽음)
uv run python pipelines/merge_weather.py
# 과거 예보 기록 (경보 검증·과거 시점 재현용)
uv run python pipelines/fetch_openmeteo_forecasts.py --start 2022-01-01 --end 2026-10-12
# 시간별 관측·예보, 미국 단위 (NWS 특보 기준 계산용)
uv run python pipelines/fetch_openmeteo_hourly.py --start 2016-01-01 --end 2026-10-12 --forecast-start 2022-01-01
```

## 검증 다시 실행하기

```bash
uv run python analysis/build_complaint_features.py   # 민원 1건별 분석 변수 (먼저 실행)
uv run python analysis/verify_risk.py                # 장기처리 위험 모델, 매트릭스 세로축 (약 10분)
uv run python analysis/verify_matrix_axis.py         # 세로축 대안, 사분면 기준
uv run python analysis/verify_short_term.py          # 단기 건수 예측, 관측 기상 경보
uv run python analysis/verify_short_term_issue.py    # 이슈 단위 기상 효과, 강도별 경보
uv run python analysis/verify_forecast_alerts.py     # 실제 예보 기반 경보
uv run python analysis/verify_capacity.py            # 처리능력·적체 전환율
uv run python analysis/verify_nws_alerts.py          # 미국 기상청(NWS) 특보 기준 경보
uv run python analysis/verify_complementarity.py     # 과부하·지원 가능 부서 동시 발생
```
한 달·분기 예측과 이슈 빈도 검증 결과는 [docs/검증결과_10년.md](docs/검증결과_10년.md) ①·⑤를 보세요.
