# 병합 데이터 설명 (뉴욕 311 + Open-Meteo 기상)

`pipelines/merge_weather.py`로 만든 파일입니다. 원본 민원 컬럼은 `data/NYC311_컬럼설명.md`를 보세요.

## 기본 정보
| 항목 | 내용 |
|---|---|
| 민원 | 뉴욕 311 브롱크스 8개 기관, 2016-01-01 ~ 2026-10-12, 1,546,798건 |
| 기상 | Open-Meteo Archive, 격자점 위도 40.808 / 경도 -73.892, 일 단위 |
| 병합 키 | `date` = 민원 접수일시(`created_date`)의 **뉴욕 현지 날짜**. 기상도 `timezone=America/New_York` 기준이라 변환 없이 일치 |
| 기관 약어 통일 | 2020년 이전 `DCA` → `DCWP` (15,503건). 원래 값은 `agency_raw` |

## 파일
| 파일 | 행 단위 | 행 수 | 용도 |
|---|---|---|---|
| `weather_features_daily.csv` | 날짜 | 3,938 | 날짜별 기상 변수 (아래 표) |
| `daily_agency_weather.csv` | 날짜 × 기관 | 31,504 | 접수량 예측. `agency`, `count` + 기상 변수 |
| `daily_issue_weather.csv` | 날짜 × 이슈 | 39,380 | 예상 이슈 키워드. `issue`, `count` + 기상 변수 |
| `nyc311_weather_merged.csv.gz` | 민원 1건 | 1,546,798 | 장기처리 위험 모델. 원본 17열 + `agency_raw`, `date`, `issue` + 기상 변수 |

접수가 없는 날도 `count = 0`으로 채워져 있습니다.

## 기상 변수 (weather_features_daily.csv)
| 컬럼 | 뜻 | 단위 |
|---|---|---|
| `temperature_2m_max` / `_min` / `_mean` | 최고·최저·평균 기온 | °C |
| `apparent_temperature_max` / `_min` | 최고·최저 체감온도 | °C |
| `precipitation_sum` | 강수량 합계 (비 + 눈 환산) | mm |
| `rain_sum` | 비 | mm |
| `snowfall_sum` | 신적설 | cm |
| `precipitation_hours` | 강수 시간 | 시간 |
| `wind_speed_10m_max` | 최대 풍속 (평균 풍속이라 낮게 나옴) | km/h |
| `wind_gusts_10m_max` | 최대 돌풍 (**강풍 판단은 이 값 사용**) | km/h |
| `weather_code` | 대표 날씨 코드 (WMO 기준) | 코드 |
| `hot_hours` | 기온 32°C 이상인 시간 수 | 시간 |
| `freezing_hours` | 기온 0°C 이하인 시간 수 | 시간 |
| `precip_max_1h` | 1시간 최대 강수량 | mm |
| `snow_depth_max` | 최대 적설 깊이 | **m** |
| `*_lag1`, `*_lag2`, `*_lag3` | 1·2·3일 전 값 (최고기온, 강수량, 신적설, 돌풍, 폭염 시간) | 원래 단위 |
| `snowfall_3d` / `precipitation_3d` | 당일 포함 3일 누적 적설 / 강수 | cm / mm |
| `temperature_2m_max_3d` | 당일 포함 3일 중 최고기온 | °C |
| `hot_streak` | 폭염(최고 ≥ 32°C) 연속 일수 | 일 |
| `is_hot` | 최고기온 ≥ 32°C | 0/1 |
| `is_heavy_rain` | 강수량 ≥ 25mm | 0/1 |
| `is_snow` | 신적설 ≥ 2cm | 0/1 |
| `is_strong_gust` | 돌풍 ≥ 60km/h | 0/1 |
| `snow_within_3d` | 최근 3일 안에 적설일이 있었음 | 0/1 |
| `is_holiday` / `holiday_name` | 미국 연방 공휴일 (대체 휴일 반영) | 0/1 / 이름 |
| `dow` / `is_weekend` | 요일 (월=0 … 일=6) / 주말 | 숫자 / 0/1 |

`*_lag*` 값은 데이터 첫 1~3일(2016-01-01 ~ 03)에만 비어 있습니다.

## 이슈 묶음 (`issue`)
| 이슈 | 규칙 |
|---|---|
| 폭염·소화전 | 세부 유형에 `Hydrant` |
| 결빙·제설 | 유형이 `Snow`(2019년 이전) 또는 `Snow or Ice` |
| 폭우·침수 | 세부 유형에 `Sewer Backup`, `Catch Basin`, `Flooding` |
| 강풍·수목 | 유형 `Damaged Tree` |
| 도로 파손 | 세부 유형 `Pothole`, `Cave-in` |
| 수돗물 | 세부 유형에 `No Water`, `Dirty Water`, `Low Water Pressure`, `Water Main Break` |
| 쥐 / 보일러 / 가로등 | 유형 `Rodent` / `Boilers` / 세부 유형 `Street Light Out` |
| 기타 | 위에 해당하지 않는 민원 |

## 분석할 때 주의할 점 (연도별 건수에서 확인)
| 현상 | 내용 | 대응 |
|---|---|---|
| 교통국 2023년 급감 | 연 약 4만 건 → 2.5만 건. 가로등 민원이 연 1.2만 → 0.46만 건으로 줄어든 영향 | 2023년 이후 데이터로 학습하거나 시점 변수 추가 |
| 위생국 꾸준한 증가 | 2016년 2.1만 → 2025년 4.6만 건 | 추세 반영, 오래된 연도 가중치 낮추기 |
| 2020년 특이값 | 소비자보호국 7천 건(평소 약 3천), 공원국 1.6만 건(수목 민원 6.6천, 8월 열대폭풍) | 코로나·폭풍 연도로 표시 |
| 결빙·제설 연도 편차 | 2023년 35건(적설일 3일) vs 2026년 5,728건(블리자드) | 평균이 아니라 "N년 중 몇 년"의 빈도로 표현 |
| 2026년 | 10월 12일까지만 있음 | 연 단위 비교 시 제외 |
