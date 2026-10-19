# 민원 조기경보 대시보드

부서와 기간을 선택하면 그 기간의 **민원 집중도(예상 건수, 예상 이슈, 2×2 위험 매트릭스)** 를 미리 보여 주고, 집중도가 높은 부서에 인력을 연결하도록 돕는 행정 지원 대시보드입니다. 전무님 평가용 시연을 목표로 합니다.

- 기획 기준 문서: [docs/서비스기획_정리.md](docs/서비스기획_정리.md)
- 실현 가능성 검증: [docs/수정안_실현가능성_검토.md](docs/수정안_실현가능성_검토.md)
- 데이터 설명: [data/NYC311_컬럼설명.md](data/NYC311_컬럼설명.md), [data/processed/README.md](data/processed/README.md)

## 구성

```
minwon-dashboard/
├─ pyproject.toml       Python 패키지 (uv로 관리, Python 3.12)
├─ backend/app/         FastAPI 서버
├─ frontend/            React + TypeScript (Vite) + ECharts
├─ pipelines/           데이터 수집·병합 스크립트
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
```
