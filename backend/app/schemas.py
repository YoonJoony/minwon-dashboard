"""API 응답 형식. 프런트엔드 타입은 이 정의에서 자동 생성합니다 (frontend: npm run gen:api)."""
from pydantic import BaseModel


class Agency(BaseModel):
    code: str
    name: str
    short: str
    desc: str


class Scenario(BaseModel):
    id: str
    title: str
    asof: str
    start: str
    end: str
    agency: str | None = None
    narration: str
    result: str
    focus: list[str]


class Preset(BaseModel):
    key: str
    label: str


class Thresholds(BaseModel):
    x: float               # 접수 증가율 기준 (+10%)
    y: float               # 적체 배수 기준 (1.3배)
    support_x: float       # 지원 가능: 접수 증가율 이 값 이하 (−10%)


class Meta(BaseModel):
    app_name: str
    agencies: list[Agency]
    asofs: list[str]
    latest: str
    data_end: str
    scenarios: list[Scenario]
    presets: list[Preset]
    max_days: int
    thresholds: Thresholds
    per_person_default: float
    built_at: str
    data_note: str


class Period(BaseModel):
    asof: str
    start: str
    end: str
    days: int
    source: str            # short(1~14일 모델) / long(월별 방식)
    has_actual: bool


class Amount(BaseModel):
    pred: float
    lo: float
    hi: float
    base: float            # 평소 수준 = 최근 4주 일평균 × 기간 일수
    change: float          # 예측 ÷ 평소 − 1
    actual: float | None = None


class AgencyForecast(Amount):
    agency: str
    flag: str
    flag_reason: str


class SeriesPoint(BaseModel):
    start: str
    end: str
    label: str
    kind: str              # history(기준일 전 실적) / forecast(예측)
    pred: float | None = None
    lo: float | None = None
    hi: float | None = None
    actual: float | None = None
    alert: str | None = None


class ForecastOut(BaseModel):
    period: Period
    agency: str | None
    granularity: str       # day / week
    total: Amount
    by_agency: list[AgencyForecast]
    series: list[SeriesPoint]
    range_note: str


class AlertItem(BaseModel):
    date: str
    offset: int
    type: str
    type_label: str
    level: int
    level_label: str
    source: str            # 예보 / 관측
    lead_days: int
    value: str
    issues: list[str]
    agencies: list[str]
    hit_rate: float
    confidence: str


class OutlookItem(BaseModel):
    issue: str
    agency: str
    prob: float
    surged: int
    total: int
    months: list[int]


class Pothole(BaseModel):
    snow_cm: float
    mult: float
    n_winters: int
    flag: bool
    actual_mult: float | None = None


class IssueCard(BaseModel):
    kind: str              # alert / pothole / outlook
    icon: str
    title: str
    agency: str
    tag: str
    when: str
    basis: str
    metric_label: str
    metric: str
    tone: str              # danger / warning / info


class ActualSurge(BaseModel):
    issue: str
    date: str
    count: float
    normal: float


class Headline(BaseModel):
    title: str
    detail: str
    tone: str


class IssuesOut(BaseModel):
    period: Period
    alerts: list[AlertItem]
    outlook: list[OutlookItem]
    pothole: Pothole | None
    cards: list[IssueCard]
    headline: Headline
    actual_surges: list[ActualSurge]


class MatrixItem(BaseModel):
    agency: str
    name: str
    short: str
    x: float
    x_lo: float
    x_hi: float
    y: float
    quadrant: str
    flag: str
    flag_reason: str
    pred: float
    lo: float
    hi: float
    base: float
    backlog_open: float
    backlog_normal: float
    actual: float | None = None
    x_actual: float | None = None
    quadrant_actual: str | None = None
    in_range: bool | None = None


class MatrixOut(BaseModel):
    period: Period
    thresholds: Thresholds
    items: list[MatrixItem]
    counts: dict[str, int]


class NeedItem(BaseModel):
    agency: str
    excess: float
    conv: float
    instant_share: float
    need: float
    people: float
    covered: float
    quadrant: str
    flag: str


class SupportItem(BaseModel):
    agency: str
    slack: float
    people: float


class PairItem(BaseModel):
    from_agency: str
    to_agency: str
    amount: float
    people: float


class StaffingOut(BaseModel):
    period: Period
    per_person_day: float
    workdays: int
    needs: list[NeedItem]
    supports: list[SupportItem]
    pairs: list[PairItem]
    total_need: float
    total_people: float
    covered: float
    coverage: float | None


class Kpis(BaseModel):
    forecast: Amount
    alert_count: int
    alert_top: str | None
    alert_detail: str
    focus_count: int
    increase_count: int
    focus_names: list[str]
    agency_quadrant: str | None
    backlog_open: float
    backlog_normal: float
    backlog_multiple: float
    need_people: float
    need_count: float
    support_count: int
    coverage: float | None


class SummaryOut(BaseModel):
    period: Period
    agency: str | None
    kpis: Kpis


class RiskItem(BaseModel):
    unique_key: str
    agency: str
    complaint_type: str    # 뉴욕 311 원문
    type_ko: str           # 화면 표기
    descriptor: str
    created: str
    elapsed_days: float
    threshold_days: float
    ratio: float
    prob: float | None
    method: str
    factors: str


class RiskCount(BaseModel):
    agency: str
    open: int
    over_threshold: int
    high_risk: int


class RiskOut(BaseModel):
    asof: str
    agency: str | None
    counts: list[RiskCount]
    items: list[RiskItem]
    note: str


class EvidenceItem(BaseModel):
    label: str
    value: str
    note: str


class EvidenceSection(BaseModel):
    key: str
    title: str
    items: list[EvidenceItem]


class EvidenceOut(BaseModel):
    sections: list[EvidenceSection]
    sources: list[str]


# ------------------------------------------------------------------ 7일 기상 예보 띠 · 과거 7년 모달
class WeatherAlert(BaseModel):
    kind: str              # heat / snow / wind / rain
    kind_label: str        # 폭염 / 대설 / 강풍 / 호우
    level: int             # 0 예비특보 · 1 주의보 · 2 경보
    label: str             # "폭염경보 수준"(예보 판정) 또는 "극한 폭염 경보"(NWS 발표)
    source: str            # 예보 / NWS
    issued: str | None = None   # NWS 발표 시각 (뉴욕 시각)


class WeatherDay(BaseModel):
    date: str
    offset: int            # 기준일부터 며칠 뒤 (0 = 기준일)
    label: str             # 오늘 / 월 / 화 …
    lead: int              # 며칠 전 발표된 예보인지
    mode: str              # 예보(앞 4칸) / 참고(뒤 4칸, 가능성). 화면은 8칸을 같은 모양으로 표시
    icon: str | None       # clear / partly / cloudy / rain / snow / thunder
    icon_label: str | None
    tmax: float | None     # °C
    tmin: float | None
    prcp: float | None     # mm
    snow: float | None     # cm
    gust: float | None     # km/h
    alerts: list[WeatherAlert]


class WeatherStripOut(BaseModel):
    asof: str
    days: list[WeatherDay]
    note: str


class PastIssue(BaseModel):
    issue: str
    base: float            # 평소 하루 건수
    received: int          # 영향 기간 접수
    excess: float          # 늘어난 건수 = 접수 − 평소 × 영향 일수
    processed: int         # 영향 기간 내 처리
    open_end: int          # 미처리 (영향 기간 끝)
    open_7: int | None     # 미처리 (영향 기간 끝 + 7일). 기준일에 아직 알 수 없으면 없음
    peak: int              # 영향 기간 중 하루 최대 접수
    surge: bool            # 민원 급증 여부 (평소의 2배 이상이고 20건 이상인 날이 있었나)


class PastEvent(BaseModel):
    start: str
    end: str
    level: int
    level_label: str
    win_start: str
    win_end: str
    days: int
    nws: list[str]         # 그 기간 실제 발표된 NWS 특보
    surge: bool
    issues: list[PastIssue]


class PastYear(BaseModel):
    year: int
    compare_date: str      # 그 해 같은 날짜
    count: int             # 같은 시기(앞뒤 120일) 같은 종류 사건 수
    event: PastEvent | None


class WeatherHistory(BaseModel):
    kind: str
    kind_label: str
    issues: list[str]      # 대상 민원
    window_rule: str
    basis: str
    total_events: int      # 기준일 전에 끝난 같은 종류 사건 수 (2016~)
    surged_events: int     # 그중 민원 급증
    years: list[PastYear]


class WeatherDayOut(BaseModel):
    asof: str
    day: WeatherDay
    tabs: list[WeatherHistory]   # 그날 특보가 있는 종류만 (없으면 빈 목록)
    note: str
