"""계산 기준값. 모든 값은 검증 문서(docs/검증결과_10년.md, docs/리허설_검증.md)에서 정한 것입니다."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROCESSED = DATA / "processed"
RAW_WEATHER = DATA / "raw" / "weather"
RAW_NWS = DATA / "raw" / "nws"
ARTIFACTS = DATA / "artifacts"

# 기준일: 습도·적설 예보 기록(2024-01-19~)이 1~7일 전 발표분까지 모두 갖춰지는 첫 월요일부터 데이터 마지막 날까지
ASOF_START = "2024-02-05"
LATEST = "2026-10-12"          # 민원 데이터 마지막 날(월요일). 이 날 이전 데이터만 씀
MAX_DAYS = 92                  # 선택 기간 최대 길이 (기준일부터)
SHORT_DAYS = 14                # 단기 모델이 맡는 기간 (이하면 단기, 넘으면 월별 방식)

AGENCIES = ["DSNY", "DEP", "DOT", "DOB", "DOHMH", "DPR", "DCWP", "DHS"]   # 화면 표시 순서 (접수 규모 순)
AGENCY_INFO = {
    "DSNY": {"name": "위생국", "short": "위생", "desc": "청소·폐기물·제설"},
    "DEP": {"name": "환경보호국", "short": "환경보호", "desc": "상하수도·소음·대기"},
    "DOT": {"name": "교통국", "short": "교통", "desc": "도로·가로등·신호"},
    "DOB": {"name": "건축국", "short": "건축", "desc": "건축물·승강기·공사"},
    "DOHMH": {"name": "보건정신위생국", "short": "보건", "desc": "위생·방역·실내 공기"},
    "DPR": {"name": "공원휴양국", "short": "공원", "desc": "공원·가로수"},
    "DCWP": {"name": "소비자·근로자보호국", "short": "소비자보호", "desc": "소비자 피해"},
    "DHS": {"name": "노숙자서비스국", "short": "노숙자", "desc": "노숙인 지원"},
}

# 2×2 매트릭스 (리허설 검증 3장)
X_TH = 0.10                    # 접수 증가율 기준
Y_TH = 1.3                     # 적체 배수 기준
SUPPORT_X = -0.10              # 지원 가능: 접수가 평소보다 10% 이상 적음

# 적체 전환율 (검증 ⑨, 보건국은 처리 기록이 고르지 않아 보수적으로 1.0)
CONV = {"DHS": 0.11, "DEP": 0.17, "DOT": 0.27, "DCWP": 0.28, "DSNY": 0.51, "DPR": 0.66, "DOB": 0.75, "DOHMH": 1.0}

# 기상 특보 영향 부서의 범위 상한 배수 (특보 주 실제÷예측 90% 지점, 리허설 2장)
WIDEN = {"DEP": 1.6, "DPR": 3.1, "DSNY": 3.1}
WIDEN_DEFAULT = 2.6

PER_PERSON_DEFAULT = 10        # 시연용 가정값: 1인당 하루 처리 건수

# 예보 시점: 기준일 + k일의 날씨는 k일 전 발표 예보 (4일 → 5일 전, 6일 → 7일 전 발표분)
LEAD = {0: 1, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6}   # 기준일 + k일 → k일 전 발표 예보 (기준일 당일은 전날 발표)

# 특보 → 관련 이슈 → 부서, 영향받는 날 (특보일 기준 며칠 뒤)
LINKS = [("heat", "폭염·소화전", "DEP", (0, 1)), ("heat", "수돗물", "DEP", (0, 1)),
         ("snow", "결빙·제설", "DSNY", (1, 2)), ("wind", "강풍·수목", "DPR", (0, 1)),
         ("rain", "폭우·침수", "DEP", (0, 1))]

ALERT_INFO = {   # 검증 ⑩: 관측 10년 특보 수준 날 뒤 민원 급증 비율, 예보 신뢰도
    "heat": {"label": "폭염", "levels": {1: "폭염주의보", 2: "폭염경보"}, "hit": {1: 0.78, 2: 0.83},
             "confidence": "높음", "issues": ["폭염·소화전", "수돗물"]},
    "snow": {"label": "대설", "levels": {1: "대설주의보", 2: "대설경보"}, "hit": {1: 0.48, 2: 0.75},
             "confidence": "높음 (1일 전)", "issues": ["결빙·제설"]},
    "wind": {"label": "강풍", "levels": {1: "강풍주의보", 2: "강풍경보"}, "hit": {1: 0.54, 2: 0.73},
             "confidence": "중간", "issues": ["강풍·수목"]},
    "rain": {"label": "호우", "levels": {1: "강한 비", 2: "매우 강한 비"}, "hit": {1: 0.38, 2: 0.38},
             "confidence": "참고", "issues": ["폭우·침수"]},
}

ISSUE_INFO = {   # 이슈 → 담당 부서
    "폭염·소화전": "DEP", "수돗물": "DEP", "폭우·침수": "DEP", "결빙·제설": "DSNY", "강풍·수목": "DPR",
    "도로 파손": "DOT", "가로등": "DOT", "쥐": "DOHMH", "보일러": "DOB",
}

# 이슈 달력: 그 달 건수 ≥ 직전 12개월 월평균 × 1.5 이고 30건 이상이면 급증 (검증 ⑤)
SURGE_RATIO, SURGE_MIN = 1.5, 30
POTHOLE_FLAG_MULT = 1.5        # 겨울 적설 → 봄 도로 파손 배수가 이 이상이면 교통국 표시

RISK_TOP_K = 40                # 기준일·부서마다 저장할 지연 위험 민원 수


# ------------------------------------------------------------------ 7일 기상 예보 띠 · 과거 7년 모달 (docs/기상예보_기능_검증.md)
STRIP_DAYS = 8                 # 기준일 포함 8칸
STRIP_FORECAST_DAYS = 4        # 앞 4칸(오늘 ~ +3일)은 "예보", 뒤 4칸은 "참고"(가능성)
STRIP_PAST_DAYS = 7            # 띠를 왼쪽으로 넘기면 보이는 지난 7일 (실제 관측)
WEATHER_LABEL = {"heat": "폭염", "snow": "대설", "wind": "강풍", "rain": "호우"}
WEATHER_ISSUES = {k: [i for kind, i, _, _ in LINKS if kind == k] for k in WEATHER_LABEL}
# 영향 기간 = [사건 첫날 + a일, 마지막 날 + b일]: 10년치 급증 사건에서 민원이 늘기 시작한 날·마지막으로 늘어난 날의 중앙값
# (analysis/verify_weather_events.py). 호우는 실제 발표된 NWS 홍수 특보로 사건을 만든 결과.
WEATHER_WINDOW = {"heat": (-1, 2), "snow": (0, 5), "wind": (0, 2), "rain": (0, 1)}
HISTORY_YEARS = 7
HISTORY_SEASON_DAYS = 120      # 해마다 "같은 시기" = 그 해 같은 날짜 앞뒤 120일 안에서 가장 가까운 사건
# 실제 발표된 NWS 특보 (VTEC 종류, 단계) → (기상 종류, 단계: 0 예비특보 · 1 주의보 · 2 경보, 화면 이름)
NWS_ALERTS = {
    ("HT", "Y"): ("heat", 1, "폭염 주의보"), ("EH", "W"): ("heat", 2, "폭염 경보"), ("XH", "W"): ("heat", 2, "극한 폭염 경보"),
    ("EH", "A"): ("heat", 0, "폭염 예비특보"), ("XH", "A"): ("heat", 0, "극한 폭염 예비특보"),
    ("WI", "Y"): ("wind", 1, "강풍 주의보"), ("HW", "W"): ("wind", 2, "강풍 경보"), ("HW", "A"): ("wind", 0, "강풍 예비특보"),
    ("WW", "Y"): ("snow", 1, "겨울 날씨 주의보"), ("WS", "W"): ("snow", 2, "겨울 폭풍 경보"), ("BZ", "W"): ("snow", 2, "눈보라 경보"),
    ("WS", "A"): ("snow", 0, "겨울 폭풍 예비특보"), ("BZ", "A"): ("snow", 0, "눈보라 예비특보"),
    ("FA", "Y"): ("rain", 1, "홍수 주의보"), ("FF", "W"): ("rain", 2, "돌발 홍수 경보"), ("FF", "A"): ("rain", 0, "돌발 홍수 예비특보"),
    ("FA", "A"): ("rain", 0, "홍수 예비특보"),
}
