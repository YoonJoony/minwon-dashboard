"""2차 공부 노트(파이썬 실습) 노트북을 만들고 처음부터 실행해 결과까지 저장합니다."""
import sys
from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

OUT = Path(sys.argv[1])
cells = []


def md(s):
    cells.append(nbf.v4.new_markdown_cell(s.strip("\n")))


def code(s):
    cells.append(nbf.v4.new_code_cell(s.strip("\n")))


# ====================================================================== 0
md(r"""
# 스마트 민원케어 공부 노트 2차 · 파이썬 실습

1차 노트에서 말로 배운 계산을 **직접 파이썬으로 짜 보고**, 실제 대시보드 계산 코드(`engine/`)가 낸 값과 **같은지 확인**하는 실습입니다.

| 실습 | 내용 | 1차 노트 |
|---|---|---|
| 1 | pandas로 민원 데이터 읽기 | 1·2장 |
| 2 | 평소(직전 28일 일평균) | 3.5 |
| 3 | 단기 예측 LightGBM: 입력 변수 → 학습 → 예측 → 오차 → 80% 범위 | 3.2·3.4 |
| 4 | 한 달 예측: 계절 지수 × 최근 수준 | 3.3 |
| 5 | 기상 특보 판정: 열지수와 폭염 단계 | 4.2 |
| 6 | 이슈 달력 빈도, 겨울 적설 → 봄 도로 파손 | 4.6·4.7 |
| 7 | 적체 배수 | 5.1·5.2 |
| 8 | 사분면 판정 | 5.4 |
| 9 | 인력 지원: 적체 증가, 인원 환산, 짝짓기 | 6장 |

**실습마다 순서가 같습니다:** ① 무엇을 계산하나 → ② 직접 계산 → ③ `engine/` 결과와 대조(`assert`). 대조가 통과하면 "화면에 나오는 숫자를 내가 직접 다시 만들 수 있다"는 뜻입니다.

**실행 방법** (프로젝트 폴더 `minwon-dashboard`에서)

```bash
uv sync --group study
uv run --group study jupyter lab study/2차_파이썬_실습.ipynb
```

위에서부터 셀을 하나씩 `Shift + Enter`로 실행합니다. 이 파일에는 실행 결과가 이미 저장돼 있어서, 실행하지 않고 읽기만 해도 됩니다. 데이터 폴더(`data/`)는 git에 없으므로 데이터가 있는 PC에서 실행해야 합니다.

**자바 개발자를 위한 짧은 대응**

| 파이썬 | 자바로 치면 |
|---|---|
| `pd.DataFrame` (표) | 메모리에 올린 DB 테이블. `df["열"]`은 열 하나(Series) |
| `df.loc[행 조건]` | `WHERE` |
| `df.groupby(...).sum()` | `GROUP BY ... SUM()` |
| `df.pivot(...)` | 피벗 테이블 (행 → 열로 펼치기) |
| `np.median`, `np.log` | `Math` 계열 정적 함수 |
| `assert 조건` | JUnit의 `assertTrue` |
| `f"{x:,.0f}"` | `String.format("%,.0f", x)` |
""")

code(r"""
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

# 노트가 study/ 폴더에 있으므로 한 단계 위가 프로젝트 폴더
ROOT = Path.cwd().parent if Path.cwd().name == "study" else Path.cwd()
sys.path.insert(0, str(ROOT))                 # engine/ 을 import 할 수 있게
sys.path.insert(0, str(ROOT / "backend"))     # 서버 계산(app/)도 import 할 수 있게
warnings.filterwarnings("ignore")
pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 20)

D = pd.Timedelta          # 날짜 더하기·빼기용: D(days=28)
DATA = ROOT / "data" / "processed"
print("프로젝트 폴더:", ROOT)
""")

# ====================================================================== 1
md(r"""
## 실습 1. pandas로 민원 데이터 읽기

전처리 결과 `daily_agency_weather.csv`에는 **날짜 × 부서마다 한 줄**씩 접수 건수가 들어 있습니다. 이것을 "날짜가 행, 부서가 열"인 표로 펼치면 이후 모든 계산이 쉬워집니다.
""")
code(r"""
raw = pd.read_csv(DATA / "daily_agency_weather.csv", usecols=["date", "agency", "count"], parse_dates=["date"])
print(f"{len(raw):,}행")
raw.head()
""")
code(r"""
# 피벗: 행 = 날짜, 열 = 부서, 값 = 접수 건수
cnt = raw.pivot(index="date", columns="agency", values="count").astype(float)
AGENCIES = ["DSNY", "DEP", "DOT", "DOB", "DOHMH", "DPR", "DCWP", "DHS"]
cnt = cnt[AGENCIES]

print("기간:", cnt.index.min().date(), "~", cnt.index.max().date(), f"({len(cnt):,}일)")
print(f"전체 접수: {cnt.sum().sum():,.0f}건")
cnt.tail(3)
""")
code(r"""
# 대조: 엔진이 쓰는 표와 완전히 같은가?
from engine.data import daily_counts

assert cnt.equals(daily_counts())
assert cnt.sum().sum() == 1_546_798
print("통과: 직접 만든 표 = 엔진의 daily_counts()")
""")
md(r"""
부서별 10년 합계와 2025년 하루 평균입니다. 하루 8건에서 127건까지 **16배** 차이 나서, 뒤에 나오는 계산은 건수를 그대로 비교하지 않고 "그 부서의 평소 대비 몇 배"로 봅니다.
""")
code(r"""
pd.DataFrame({
    "10년 합계": cnt.sum().map("{:,.0f}".format),
    "2025 하루 평균": cnt.loc["2025"].mean().round(0),
})
""")

# ====================================================================== 2
md(r"""
## 실습 2. 평소 = 직전 28일 일평균

화면의 "평소"(예상 접수 지표, 매트릭스 가로축, 인력 지원)는 **기준일 바로 전 28일의 하루 평균**입니다. 기준일 당일은 넣지 않습니다(아직 하루가 끝나지 않았으니까).

S1 폭염 시나리오(기준일 2025-06-20)로 계산해 봅니다.
""")
code(r"""
asof = pd.Timestamp("2025-06-20")

recent = cnt.loc[asof - D(days=28): asof - D(days=1)]     # 5/23 ~ 6/19, 28일
print("기간:", recent.index.min().date(), "~", recent.index.max().date(), len(recent), "일")

normal_day = recent.mean()          # 부서별 하루 평균
normal_7 = normal_day * 7           # 7일 기준 평소
pd.DataFrame({"하루 평균": normal_day.round(2), "7일 평소": normal_7.round(1)})
""")
code(r"""
# 화면 상단 "예상 접수"의 평소 = 8개 부서 합 × 7일
print(f"전체 평소(7일): {normal_7.sum():,.2f}건")
assert round(normal_7.sum(), 2) == 3011.75     # 화면: 평소 3,012건
assert normal_7["DEP"] == 481.75               # 1차 노트: 환경보호국 평소 482건
print("통과")
""")

# ====================================================================== 3
md(r"""
## 실습 3. 단기 예측 (LightGBM)

1차 노트 3.2의 내용을 그대로 코드로 옮깁니다.

- **예측 대상:** 부서마다 기준일부터 7일 합계(1~7일 블록)
- **목표값:** `log((실제 + 1) ÷ (평소 + 1))`, 즉 "평소의 몇 배인가"의 로그
- **입력 변수:** 최근 흐름, 과거 같은 시기 비율, 공휴일 수, 연중 위치(sin·cos), 부서, 블록

### 3-1. 입력 변수를 직접 만들기 (환경보호국, S1)
""")
code(r"""
from engine.data import holidays

hol = holidays()                    # 날짜 → 공휴일이면 1
ag = "DEP"
y = cnt[ag]
start, end = asof, asof + D(days=6)            # 1~7일 블록: 6/20 ~ 6/26

# ① 최근 흐름 = 직전 7일 평균 ÷ 직전 28일 평균
r28 = y.loc[asof - D(days=28): asof - D(days=1)].mean()
r7 = y.loc[asof - D(days=7): asof - D(days=1)].mean()
r7_r28 = r7 / r28

# ② 과거 같은 시기 비율 = 1~3년 전 같은 7일 합계 ÷ 그때의 평소(그때 직전 28일 평균 × 7), 세 해의 중앙값
ratios = []
for k in (1, 2, 3):
    ps, pe, pt = start - pd.DateOffset(years=k), end - pd.DateOffset(years=k), asof - pd.DateOffset(years=k)
    base_then = y.loc[pt - D(days=28): pt - D(days=1)].mean() * 7
    ratios.append(y.loc[ps:pe].sum() / base_then)
    print(f"{k}년 전 {ps.date()}~{pe.date()}: {y.loc[ps:pe].sum():.0f}건 ÷ 그때 평소 {base_then:.1f} = {ratios[-1]:.3f}")
season_ratio = np.median(ratios)

# ③ 공휴일 수, ④ 연중 위치(1년을 원으로 보고 각도로 표현 → 12/31과 1/1이 가깝게)
n_hol = hol.reindex(pd.date_range(start, end)).fillna(0).sum()
woy_sin = np.sin(2 * np.pi * start.dayofyear / 365.25)
woy_cos = np.cos(2 * np.pi * start.dayofyear / 365.25)

mine = {"r7_r28": r7_r28, "season_ratio": season_ratio, "holidays": n_hol, "woy_sin": woy_sin, "woy_cos": woy_cos,
        "base": r28 * 7}
pd.Series(mine).round(4)
""")
code(r"""
# 대조: 엔진이 같은 기준일에 만드는 입력 변수
from engine import forecast_short as fs

eng = fs.feature_rows(cnt, hol, [asof], require_actual=False)
eng_dep = eng[(eng.agency == ag) & (eng.block == 1)].iloc[0]
for k, v in mine.items():
    assert np.isclose(v, eng_dep[k]), k
print("통과: 직접 만든 입력 변수 = 엔진 feature_rows()")
eng[eng.block == 1][["agency", "base", "r7_r28", "season_ratio", "holidays"]].round(3)
""")
md(r"""
### 3-2. 학습 데이터 만들고 학습하기

학습 데이터는 2017년부터 **매주 월요일마다** 위 변수를 만든 것입니다(월요일 × 블록 2개 × 부서 8개). 정답(그 7일의 실제 합계)이 기준일 전에 나와 있어야 하므로, **블록 끝이 기준일 전인 월요일만** 씁니다. 이것이 1차 노트의 "데이터 누수 막기"입니다.

같은 변수 만들기를 수백 번 반복하는 것이라 여기서는 엔진 함수(`fs.feature_rows`)를 그대로 씁니다. 몇 초 걸립니다.
""")
code(r"""
import lightgbm as lgb

origins = pd.date_range("2017-01-02", cnt.index.max(), freq="W-MON")   # 모든 월요일
rows = fs.feature_rows(cnt, hol, origins)                              # 정답이 있는 행만
train = rows[rows.origin + D(days=13) < asof]                         # 기준일 2주 전까지 끝난 것만
print(f"전체 {len(rows):,}행 중 학습에 쓰는 행 {len(train):,}")
train[["origin", "block", "agency", "base", "actual", "r7_r28", "season_ratio", "target"]].tail(3)
""")
code(r"""
# 목표값이 정말 log((실제 + 1) ÷ (평소 + 1)) 인지 직접 확인
check = np.log((train.actual + 1) / (train.base + 1))
assert np.allclose(check, train.target)

FEATURES = ["agency", "block", "r7_r28", "season_ratio", "holidays", "woy_sin", "woy_cos"]
PARAMS = {"n_estimators": 400, "learning_rate": 0.03, "num_leaves": 15, "min_child_samples": 30, "subsample": 0.8,
          "subsample_freq": 1, "colsample_bytree": 0.8, "verbose": -1, "random_state": 0}
print("설정 (1차 노트 3.2):", PARAMS)

model = lgb.LGBMRegressor(**PARAMS).fit(train[FEATURES], train["target"])
print("학습 끝: 나무", model.n_estimators, "개")
""")
md(r"""
### 3-3. 예측하기: 모델 출력 → "평소의 몇 배" → 건수
""")
code(r"""
X = eng[FEATURES]                     # 기준일(6/20)의 입력 변수 (실습 3-1)
log_mult = model.predict(X)           # 모델 출력 = log(배수)
mult = np.exp(log_mult)               # 평소의 몇 배
pred = mult * (eng.base + 1) - 1      # 건수

result = pd.DataFrame({"agency": eng.agency.astype(str), "block": eng.block, "평소": eng.base.round(1),
                       "배수": mult.round(3), "예측": pred.round(0)})
result[result.block == 1]
""")
code(r"""
# 대조: 엔진의 예측 함수와 같은가? 환경보호국 1~7일 = 654건 (1차 노트 3.2)
eng_pred = fs.forecast(asof, rows, cnt, hol)
assert np.allclose(eng_pred.sort_values(["block", "agency"]).pred.to_numpy(),
                   pred[eng.sort_values(["block", "agency"]).index].to_numpy())
dep = result[(result.agency == "DEP") & (result.block == 1)].iloc[0]
assert round(dep["예측"]) == 654
print(f"통과: 환경보호국 1~7일 = 평소 {dep['평소']}건의 {dep['배수']}배 = {dep['예측']:.0f}건")
""")
md(r"""
### 3-4. 나무 400개가 더해지는 모습

예측값은 나무 400개의 끝 칸 숫자를 모두 더한 것입니다. 나무를 k개까지만 썼을 때 값이 어떻게 쌓이는지 봅니다(1차 노트의 "LightGBM 쉽게 이해하기").
""")
code(r"""
x_dep = X[(eng.agency == "DEP") & (eng.block == 1)]
for k in (1, 10, 50, 100, 200, 400):
    s = model.predict(x_dep, num_iteration=k)[0]
    print(f"나무 {k:>3}개까지 합 {s:+.3f} → 평소의 {np.exp(s):.3f}배")
""")
code(r"""
# 첫 번째 나무의 맨 위 조건들 (split_feature ≤ threshold 이면 왼쪽)
tree0 = model.booster_.trees_to_dataframe().query("tree_index == 0")
tree0[["node_depth", "split_feature", "threshold", "value", "count"]].head(6)
""")
md(r"""
### 3-5. 오차 직접 재기 (백테스트)

해마다 "그 전 해까지의 데이터로 학습 → 그해 매주를 예측"을 반복하고, `|예측 − 실제| ÷ 실제`의 평균을 냅니다. 비교 기준선은 "최근 4주 평균 × 7 그대로"(= 평소)입니다. 모델 5개를 학습하므로 30초쯤 걸립니다.
""")
code(r"""
bt = fs.backtest(rows)          # 2022~2026년, 해마다 다시 학습해 예측한 결과

def mape(pred_col):
    e = (bt[pred_col] - bt.actual).abs() / bt.actual.clip(lower=1)
    return e.groupby([bt.block, bt.agency.astype(str)]).mean().groupby(level=0).mean()

table = pd.DataFrame({"최근 4주 평균 그대로": mape("base"), "LightGBM": mape("pred")})
table.index = ["1~7일", "8~14일"]
(table * 100).round(1).astype(str) + "%"
""")
md(r"""
1차 노트의 숫자(1~7일 16.6%, 8~14일 18.1%, 기준선 19.2%·21.6%)가 그대로 다시 나옵니다. **모델이 "최근 4주 평균 그대로"보다 2.6~3.5%p 낫습니다.**

### 3-6. 80% 범위: 과거 오차의 10%·90% 지점
""")
code(r"""
# 기준일 전에 결과가 확정된 1~7일 블록 예측만, 환경보호국
past = bt[(bt.block == 1) & (bt.origin + D(days=6) < asof) & (bt.agency.astype(str) == "DEP")]
err = np.log((past.actual + 1) / (past.pred + 1))       # 실제가 예측의 몇 배였나(로그)
lo_ratio, hi_ratio = np.exp(err.quantile(0.1)), np.exp(err.quantile(0.9))
print(f"과거 예측 {len(past)}번 → 하한 배수 {lo_ratio:.3f}, 상한 배수 {hi_ratio:.3f}")
print(f"환경보호국 80% 범위: {654.2 * lo_ratio:,.0f} ~ {654.2 * hi_ratio:,.0f}건")

iv = fs.interval_ratios(bt, asof).query("agency == 'DEP' and block == 1").iloc[0]
assert np.isclose(lo_ratio, iv.lo_ratio) and np.isclose(hi_ratio, iv.hi_ratio)
print("통과: 엔진 interval_ratios()와 같음 (1차 노트: 488 ~ 862건)")
""")

# ====================================================================== 4
md(r"""
## 실습 4. 한 달 예측: 계절 지수 × 최근 수준

S4 평상시 시나리오(기준일 2025-10-01), 위생국 10월을 직접 계산합니다(1차 노트 3.3).

- **계절 지수:** 지난 최대 7년 "그 달 ÷ 그 달을 가운데 둔 12개월 평균"의 중앙값
- **최근 수준:** 직전 완료된 3개월 각각 "실적 ÷ 그 달 계절 지수"의 평균
- **예측:** 최근 수준 × 대상 달 계절 지수
""")
code(r"""
mo = cnt.groupby(cnt.index.to_period("M")).sum()     # 월별 합계 (행 = 2016-01, 2016-02, ...)
asof4 = pd.Timestamp("2025-10-01")
asof_m = asof4.to_period("M")
dsny = mo.loc[mo.index < asof_m, "DSNY"]             # 기준일이 속한 달 전까지만 (누수 방지)

def season_index(y, month, show=False):
    vals = []
    for k in range(1, 8):                            # 1~7년 전 같은 달
        p = month - 12 * k
        win = y.loc[p - 6: p + 5]                    # 그 달을 가운데 둔 12개월
        if len(win) == 12 and p + 5 < asof_m:
            vals.append(y.loc[p] / win.mean())
            if show:
                print(f"  {p}: {y.loc[p]:,.0f}건 ÷ 12개월 평균 {win.mean():,.0f} = {vals[-1]:.3f}")
    return float(np.median(vals))

target = pd.Period("2025-10", "M")
print("① 10월 계절 지수 후보")
si = season_index(dsny, target, show=True)
print(f"  → 중앙값 {si:.3f}")
""")
code(r"""
print("② 최근 수준: 직전 완료된 3개월")
last = dsny.index[-1]                                 # 2025-09
levels = []
for r in range(3):
    p = last - r
    s_p = season_index(dsny, p)
    levels.append(dsny.loc[p] / s_p)
    print(f"  {p}: {dsny.loc[p]:,.0f}건 ÷ {s_p:.3f} = {levels[-1]:,.0f}")
level = np.mean(levels)
pred_oct = level * si
print(f"  → 평균 {level:,.0f}")
print(f"③ 예측 = {level:,.0f} × {si:.3f} = {pred_oct:,.0f}건 (실제 {mo.loc[target, 'DSNY']:,.0f}건)")
""")
code(r"""
from engine import forecast_long as fl

eng_m = fl.seasonal_pred(mo, [target], asof4)[target]
assert np.isclose(pred_oct, eng_m["DSNY"]) and round(pred_oct) == 4157
print("통과: 엔진 seasonal_pred()와 같음\n")
print(pd.DataFrame({"예측": eng_m.round(0), "실제": mo.loc[target], "차이": (eng_m / mo.loc[target] - 1).map("{:+.1%}".format)}))
print(f"\n합계 예측 {eng_m.sum():,.0f} / 실제 {mo.loc[target].sum():,.0f}")
""")

# ====================================================================== 5
md(r"""
## 실습 5. 기상 특보 판정: 열지수와 폭염 단계

미국 기상청 폭염 기준은 기온이 아니라 **열지수**(기온 + 습도로 계산한 체감 더위, °F)입니다. 공식(Rothfusz 회귀식)을 직접 써 봅니다.
""")
code(r"""
def heat_index(t, rh):
    # t: 기온(°F), rh: 습도(%). NWS 공식의 핵심 부분 (보정 항은 엔진 코드 참고)
    simple = 0.5 * (t + 61.0 + (t - 68.0) * 1.2 + rh * 0.094)
    if (simple + t) / 2 < 80:
        return simple
    return (-42.379 + 2.04901523 * t + 10.14333127 * rh - 0.22475541 * t * rh - 0.00683783 * t**2
            - 0.05481717 * rh**2 + 0.00122874 * t**2 * rh + 0.00085282 * t * rh**2 - 0.00000199 * t**2 * rh**2)

for t_c, rh in [(32, 40), (32, 70), (35, 60)]:
    t_f = t_c * 1.8 + 32
    hi = heat_index(t_f, rh)
    print(f"기온 {t_c}°C, 습도 {rh}% → 열지수 {hi:.0f}°F ({(hi - 32) / 1.8:.0f}°C)")
""")
code(r"""
from engine.alerts import heat_index as eng_hi

t = pd.Series([89.6, 89.6, 95.0]); rh = pd.Series([40.0, 70.0, 60.0])
assert np.allclose([heat_index(a, b) for a, b in zip(t, rh)], eng_hi(t, rh))
print("통과: 같은 32°C라도 습하면 열지수가 훨씬 높습니다 → 폭염 주의보 기준 95°F를 넘김")
""")
md(r"""
하루 단위 판정 규칙(1차 노트 4.2): **주의보** = 하루 최고 열지수 95°F 이상이 이틀 연속, 또는 100°F 이상 / **경보** = 105°F 이상이 2시간 연속. 2025년 6월 폭염 주간의 실제 관측으로 확인합니다.
""")
code(r"""
from engine.alerts import daily_levels
from engine.data import hourly_obs

obs = hourly_obs()
week = obs[(obs.time >= "2025-06-20") & (obs.time < "2025-06-27")]
hi_hourly = eng_hi(week.t.reset_index(drop=True), week.rh.reset_index(drop=True))
hi_hourly.index = week.time.dt.normalize().to_numpy()
daily_max = hi_hourly.groupby(level=0).max()

lv = daily_levels(week)
pd.DataFrame({"하루 최고 열지수(°F)": daily_max.round(0), "판정(0 없음·1 주의보·2 경보)": lv.heat})
""")

# ====================================================================== 6
md(r"""
## 실습 6. 한 달·분기 이슈: 이슈 달력과 도로 파손

**그 달 급증** = 그 달 건수 ≥ 직전 12개월 월평균 × 1.5 **그리고** 30건 이상. **가능성** = 지난 해들 중 그 달에 급증한 해의 비율.

"결빙·제설"의 1월 가능성을 기준일 2026-01-05로 계산합니다.
""")
code(r"""
from engine.data import daily_issues

iss = daily_issues()
mi = iss.groupby(iss.index.to_period("M")).sum()          # 이슈 × 월
asof6 = pd.Timestamp("2026-01-05")
m = mi[mi.index < asof6.to_period("M")]                     # 기준일 전 달까지만

base12 = m.rolling(12).mean().shift(1)                      # 직전 12개월 월평균 (그 달 제외)
surge = ((m / base12 >= 1.5) & (m >= 30)).where(base12.notna())

jan = surge[surge.index.month == 1]["결빙·제설"].dropna()
print(jan.astype(int).rename(lambda p: p.year).to_string())
print(f"→ {len(jan)}년 중 {int(jan.sum())}년 급증, 가능성 {jan.mean():.0%}")
""")
code(r"""
from engine import issues as isu

cal = isu.calendar(mi, asof6, [pd.Period("2026-01", "M")])
eng_p = cal.query("issue == '결빙·제설'").groupby("year").surged.max().mean()
assert np.isclose(eng_p, jan.mean())
print("통과: 엔진 calendar()와 같음")
""")
md(r"""
**겨울 적설 → 봄 도로 파손** (1차 노트 4.7): 지난 겨울들의 (12~2월 적설, 3~4월 도로 파손 배수) 짝으로 `log(배수) = a × 적설 + b` 직선을 맞추고, 올겨울 적설을 넣습니다. 기준일 2026-03-01(S3).
""")
code(r"""
from engine.data import weather_daily

w = weather_daily()
pot = mi["도로 파손"]
pbase = pot.rolling(12).mean().shift(1)
xs, ys = [], []
for yr in range(2017, 2026):
    snow = w.loc[f"{yr - 1}-12-01":f"{yr}-02-28", "snowfall_sum"].sum()
    mult = pot.loc[[pd.Period(f"{yr}-03", "M"), pd.Period(f"{yr}-04", "M")]].mean() / pbase.loc[pd.Period(f"{yr}-03", "M")]
    xs.append(snow); ys.append(mult)
    print(f"{yr - 1}/{yr} 겨울 적설 {snow:5.1f}cm → 3~4월 도로 파손 평소의 {mult:.2f}배")

a, b = np.polyfit(xs, np.log(ys), 1)
snow_now = w.loc["2025-12-01":"2026-02-28", "snowfall_sum"].sum()
pred_mult = np.exp(a * snow_now + b)
print(f"\n올겨울 적설 {snow_now:.1f}cm → 예상 {pred_mult:.1f}배 (1.5배 이상이면 교통국에 '도로 파손 급증 예상')")
assert np.isclose(pred_mult, isu.pothole_outlook(w, mi, pd.Timestamp("2026-03-01"))["mult"])
print("통과: 엔진 pothole_outlook()과 같음")
""")

# ====================================================================== 7
md(r"""
## 실습 7. 적체 배수 (매트릭스 세로축)

- **처리 중 민원:** 측정일(월요일)에 최근 6개월 접수분 중 ① 처리완료일이 없거나 ② 처리완료일이 측정일 이후이거나 ③ 상태가 Closed가 아닌 것
- **적체 배수:** 처리 중 민원 수 ÷ 직전 52주(월요일) 측정값의 중앙값

S1 기준일(2025-06-20, 금요일)은 직전 월요일 6/16의 측정값을 씁니다. 민원 1건별 표(약 150만 건)를 읽어 직접 셉니다.
""")
code(r"""
from engine.data import complaints

df = complaints()
print(f"민원 1건별 표: {len(df):,}건")

def open_count(monday):
    w6 = df[(df.created >= monday - pd.DateOffset(months=6)) & (df.created < monday)]
    is_open = w6.closed.isna() | (w6.closed >= monday) | (w6.status != "Closed")
    return is_open.groupby(w6.agency).sum().reindex(AGENCIES)

monday = pd.Timestamp("2025-06-16")
now_open = open_count(monday)
now_open
""")
code(r"""
# 평소 = 직전 52주 월요일 값의 중앙값 (52번 세므로 10초쯤 걸립니다)
past_mondays = pd.date_range(end=monday - D(days=7), periods=52, freq="W-MON")
history = pd.DataFrame({m: open_count(m) for m in past_mondays}).T
normal_open = history.median().clip(lower=1)
multiple = now_open / normal_open

out = pd.DataFrame({"처리 중": now_open, "평소(52주 중앙값)": normal_open, "적체 배수": multiple.round(2)})
print(out)
print(f"\n전체: 처리 중 {now_open.sum():,.0f}건, 평소 {normal_open.sum():,.1f}건, {now_open.sum() / normal_open.sum():.2f}배")
""")
code(r"""
from engine import backlog as bl

weekly = bl.weekly_backlog(df, "2024-01-01", "2025-06-16")
mult_e, normal_e = bl.backlog_multiple(weekly)
assert np.allclose(mult_e.loc[monday].to_numpy(), multiple.to_numpy())
assert now_open.sum() == 6199                   # 화면 상단 "처리 중 민원" 6,199건 (1차 노트 5.7)
print("통과: 엔진 backlog_multiple()과 같음")
""")

# ====================================================================== 8
md(r"""
## 실습 8. 사분면 판정

1차 노트 5.4의 판정 순서를 함수로 짭니다. x = 접수 증가율(예상 일평균 ÷ 최근 4주 일평균 − 1), y = 적체 배수.
""")
code(r"""
X_TH, Y_TH, SUPPORT_X = 0.10, 1.3, -0.10

def quadrant(x, y, flagged=False):
    if x <= SUPPORT_X and y < Y_TH:
        q = "지원 가능"
    elif x >= X_TH:
        q = "집중관리" if y >= Y_TH else "접수증가 주의"
    else:
        q = "처리지연 주의" if y >= Y_TH else "안정"
    if flagged and q == "지원 가능":     # 기상 특보·도로 파손 부서는 남을 도울 수 없음
        q = "안정"
    return q

print(quadrant(0.315, 1.36))                 # S5 환경보호국 → 집중관리
print(quadrant(-0.123, 0.83))                # S2 위생국, 특보 규칙 없이 → 지원 가능
print(quadrant(-0.123, 0.83, flagged=True))  # 대설 특보 → 안정
""")
md(r"""
이제 서버가 쓰는 실제 값(사전 계산 결과)을 불러와 8개 부서 전부를 내 함수로 판정하고, 서버 판정과 비교합니다. S2 블리자드(2026-02-20, 7일).
""")
code(r"""
from app.store import get_store

store = get_store()                                   # 서버와 같은 저장소 (사전 계산 결과를 읽음)
a, s, e = store.period("2026-02-20", "2026-02-20", "2026-02-26")
mat = store._matrix(a, s, e)                          # 부서별 예측·평소·적체 배수·판정

mine = [quadrant(r.pred / r.base - 1, r.y, flagged=bool(r.flag)) for r in mat.itertuples()]
view = mat[["agency", "pred", "base", "y", "flag", "quadrant"]].assign(
    x=(mat.pred / mat.base - 1).round(3), 내_판정=mine)
assert (view.내_판정 == view.quadrant).all()
print("통과: 8개 부서 판정이 서버와 같음")
view.round(2)
""")

# ====================================================================== 9
md(r"""
## 실습 9. 인력 지원: 적체 증가 → 인원 → 짝짓기

S3 봄철 도로 파손(기준일 2026-03-01, 3~5월)으로 1차 노트 6장의 계산을 직접 합니다.

```
예상 적체 증가 = max(예상 − 평소, 0) × (1 − 즉시 종결 비율) × 적체 전환율   ← 접수 +10% 이상 부서만
지원 필요 인원 = 적체 증가 ÷ (1인당 하루 처리 건수 × 평일 수)
여유          = max(평소 − 예상, 0)                                       ← "지원 가능" 부서만
```
""")
code(r"""
from engine.config import CONV        # 부서별 적체 전환율 (1차 노트 6.2)

a, s, e = store.period("2026-03-01", "2026-03-01", "2026-05-31")
m3 = store._matrix(a, s, e).set_index("agency")
per_person_day = 10                                   # 가정값: 1인당 하루 10건
workdays = len(pd.bdate_range(s, e))                  # 평일(월~금) 수
print("평일 수:", workdays)

need = {}
for ag, r in m3.iterrows():
    if r.x >= X_TH:                                   # 접수 +10% 이상
        v = max(r.pred - r.base, 0) * (1 - r.instant_share) * CONV[ag]
        need[ag] = v
        print(f"{ag:5s} 예상−평소 {r.pred - r.base:7,.0f} × (1 − {r.instant_share:.3f}) × {CONV[ag]:.2f}"
              f" = {v:6,.1f}건 → {v / (per_person_day * workdays):.2f}명")

slack = {ag: max(r.base - r.pred, 0) for ag, r in m3.iterrows() if r.quadrant == "지원 가능"}
print("\n지원 가능 부서 여유:", {k: round(v) for k, v in slack.items()})
""")
code(r"""
# 짝짓기: 필요가 큰 부서부터, 여유가 큰 부서부터 차례로 채움
left = dict(sorted(slack.items(), key=lambda kv: -kv[1]))
pairs, covered = [], 0.0
for ag_need, v in sorted(need.items(), key=lambda kv: -kv[1]):
    remain = v
    for ag_give in left:
        give = min(remain, left[ag_give])
        if give >= 1:
            pairs.append((ag_give, ag_need, round(give, 1), round(give / (per_person_day * workdays), 2)))
            left[ag_give] -= give
            remain -= give
            covered += give
        if remain <= 0:
            break

total = sum(need.values())
print(pd.DataFrame(pairs, columns=["돕는 부서", "받는 부서", "건수", "인원"]).to_string(index=False))
print(f"\n지원 필요 {total:,.1f}건 ({total / (per_person_day * workdays):.2f}명), 지원 처리율 {covered / total:.0%}")
""")
code(r"""
from engine.dashboard import staffing

st = staffing(m3.reset_index(), s, e, per_person_day)
assert np.isclose(st["total_need"], total) and np.isclose(st["covered"], covered)
assert round(need["DPR"]) == 750                  # 1차 노트: 공원국 약 750건, 약 1.15명
print("통과: 엔진 staffing()과 같음")
""")

# ====================================================================== 10
md(r"""
## 정리와 연습 문제

여기까지 실행했다면 화면의 핵심 숫자(평소, 단기·월별 예측, 80% 범위, 특보 판정, 이슈 가능성, 적체 배수, 사분면, 지원 필요 인원)를 모두 직접 다시 계산해 본 것입니다.

**연습 문제** (값을 바꿔 셀을 다시 실행해 보세요)

1. 실습 9의 `per_person_day`를 15로 바꾸면 공원국 지원 필요 인원은 몇 명이 되나요? (인원은 가정값에 반비례)
2. 실습 2의 `asof`를 `2025-10-01`로 바꾸면 전체 평소(7일)는 얼마인가요?
3. 실습 6에서 `"결빙·제설"`을 `"보일러"`로 바꾸면 1월 가능성은? (1차 노트 이슈 달력: 9년 중 8년)
4. 실습 8의 `quadrant()`에서 `Y_TH`를 1.5로 올리면 S2의 판정이 바뀌는 부서가 있나요?
5. 실습 3-2의 `PARAMS`에서 `n_estimators`를 100으로 줄이면 환경보호국 예측은 어떻게 바뀌나요? (3-4의 표 참고)
""")

nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"] = {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
                  "language_info": {"name": "python"}}
OUT.parent.mkdir(parents=True, exist_ok=True)
NotebookClient(nb, timeout=900, kernel_name="python3", resources={"metadata": {"path": str(OUT.parent)}}).execute()
nbf.write(nb, OUT)
print("저장:", OUT)
