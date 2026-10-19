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
