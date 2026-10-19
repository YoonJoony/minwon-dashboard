"""화면 문구: 시연 시나리오와 검증 근거. 수치는 docs/검증결과_10년.md, docs/리허설_검증.md와 같아야 합니다."""

SCENARIOS = [
    {
        "id": "S4", "title": "평상시 한 달", "asof": "2025-10-01", "start": "2025-10-01", "end": "2025-10-31", "agency": None,
        "narration": "특별한 기상 이슈가 없는 달입니다. 계절 지수와 최근 수준으로 한 달 접수량을 예측합니다.",
        "result": "전체 예측 12,257건, 실제 11,809건 (오차 4%). 8개 부서 모두 80% 범위 안.",
        "focus": ["예상 접수 추이", "부서별 현황"],
    },
    {
        "id": "S1", "title": "폭염 경보", "asof": "2025-06-20", "start": "2025-06-20", "end": "2025-06-26", "agency": None,
        "narration": "6월 20일 기준, 2일 뒤(6/22) 폭염 경보가 예보됐습니다. 환경보호국에 '기상 특보'를 표시하고 예측 범위를 넓힙니다.",
        "result": "실제 6월 24일 소화전 민원 2,377건 (평소 26건의 91배). 급증 규모는 숫자로 맞히기 어려워 경보·범위로 대응합니다.",
        "focus": ["예상 이슈", "부서 위험 매트릭스"],
    },
    {
        "id": "S2", "title": "블리자드", "asof": "2026-02-20", "start": "2026-02-20", "end": "2026-02-26", "agency": None,
        "narration": "2일 뒤 대설·강풍 주의보가 예보됐습니다. 위생국은 평소 기준으로는 접수가 줄어 보이지만, 특보 영향 부서라 지원 후보에서 뺍니다.",
        "result": "실제 2월 24일 제설 민원 1,105건 (평소 52건의 21배), 위생국 주간 접수 2,550건.",
        "focus": ["인력 지원 권고", "예상 이슈"],
    },
    {
        "id": "S3", "title": "봄철 도로 파손", "asof": "2026-03-01", "start": "2026-03-01", "end": "2026-05-31", "agency": None,
        "narration": "지난겨울 적설 77.7cm로 3~4월 도로 파손이 평소보다 크게 늘 것으로 예상됩니다. 교통국을 '도로 파손 급증 예상'으로 표시합니다.",
        "result": "실제 3월 도로 파손 민원 평소의 7.9배. 분기 전체 예측 오차 8%.",
        "focus": ["예상 이슈", "인력 지원 권고"],
    },
    {
        "id": "S5", "title": "집중관리 부서", "asof": "2024-06-24", "start": "2024-06-24", "end": "2024-06-30", "agency": None,
        "narration": "환경보호국과 노숙자서비스국이 '접수 증가 + 적체 증가'로 집중관리에 들어간 주입니다.",
        "result": "실제로 두 부서 모두 접수가 평소보다 10% 이상 늘었습니다.",
        "focus": ["부서 위험 매트릭스", "인력 지원 권고"],
    },
]

EVIDENCE = [
    {"key": "forecast", "title": "예상 건수", "items": [
        {"label": "1~7일 예측 오차", "value": "16.6%", "note": "부서별 주간 평균 오차, 2022~2026 백테스트 247주"},
        {"label": "8~14일 예측 오차", "value": "18.1%", "note": "같은 조건"},
        {"label": "한 달 예측 오차", "value": "14%", "note": "계절 지수 × 최근 수준, 2022-01~2026-09 57개월"},
        {"label": "분기 예측 오차", "value": "12%", "note": "19개 분기"},
        {"label": "80% 범위 실제 포함률", "value": "70~89%", "note": "부서별, 목표 80%"},
        {"label": "기상 정보 효과", "value": "없음", "note": "부서 전체 건수에는 기상을 넣어도 정확도 변화 없음 → 기상은 이슈 경보에만 사용"},
    ]},
    {"key": "alerts", "title": "기상 경보 (미국 기상청 뉴욕 지청 기준)", "items": [
        {"label": "폭염 주의보 수준 날 → 소화전 민원 급증", "value": "78%", "note": "관측 10년, 93일 (경보 83%)"},
        {"label": "폭염: 1일 전 예보가 실제를 미리 잡은 비율", "value": "97%", "note": "실제 예보 기록 2024~2026 (3일 전 68%)"},
        {"label": "대설 경보 수준 → 제설 민원 급증", "value": "75%", "note": "관측 10년, 12일"},
        {"label": "강풍 경보 수준 → 수목 민원 급증", "value": "73%", "note": "관측 10년, 15일"},
        {"label": "호우", "value": "참고", "note": "NWS 고정 기준 없음, 1시간 강수 대체 지표 적중 38%"},
        {"label": "특보 영향 부서 처리", "value": "범위 확대·지원 제외", "note": "특보 주 예측상 '지원 가능' 부서의 33%가 실제로는 급증 (특보 없을 때 5%)"},
    ]},
    {"key": "issues", "title": "장기 이슈 확률", "items": [
        {"label": "과거 빈도 70% 이상 이슈의 실제 급증", "value": "73%", "note": "2021~2026 평가, 빈도가 확률처럼 맞음"},
        {"label": "과거 빈도 0~10% 이슈의 실제 급증", "value": "3%", "note": ""},
        {"label": "겨울 적설 → 봄 도로 파손", "value": "순위상관 0.94", "note": "10개 겨울, 방향은 확실하나 크기는 과소 추정 경향"},
    ]},
    {"key": "matrix", "title": "부서 위험 매트릭스", "items": [
        {"label": "가로축", "value": "접수 증가율", "note": "선택 기간 예상 일평균 ÷ 최근 4주 일평균 − 1, 기준 +10%"},
        {"label": "세로축", "value": "적체 배수", "note": "처리 중 민원 수 ÷ 부서 평소(직전 52주 중앙값), 기준 1.3배"},
        {"label": "예측상 집중관리의 실제 접수 증가 비율", "value": "44%", "note": "가능성으로 해석"},
        {"label": "부서·주 중 집중관리 비율", "value": "5.3%", "note": "2018~2026"},
    ]},
    {"key": "staffing", "title": "인력 지원", "items": [
        {"label": "과부하 주에 지원 가능 부서가 함께 있던 비율", "value": "73%", "note": "2018~2026 주 단위"},
        {"label": "초과 업무를 지원 가능 부서 여유로 메운 비율", "value": "평균 61%", "note": "전부 메운 경우 51%"},
        {"label": "적체 전환율 (급증 주 늘어난 접수 중 적체로 남은 비율)", "value": "11~75%",
         "note": "노숙자 11%, 환경보호 17%, 교통 27%, 소비자보호 28%, 위생 51%, 공원 66%, 건축 75%"},
        {"label": "명 단위 환산", "value": "가정값", "note": "뉴욕 데이터에 민원 처리 인원 없음. 국내 적용 시 실제 정원·현원 사용"},
    ]},
    {"key": "risk", "title": "지연 위험 민원", "items": [
        {"label": "지연 위험 모델 AUC", "value": "0.83", "note": "로지스틱 회귀, 2022-01~2026-03 월별 재학습 51개월 (부서 평균 0.79)"},
        {"label": "소비자보호국", "value": "경과일 기준", "note": "모델 AUC 0.62로 구별력이 낮아 확률 대신 경과일 ÷ 기준처리기간"},
    ]},
    {"key": "limits", "title": "한계", "items": [
        {"label": "데이터", "value": "뉴욕시 브롱크스", "note": "국내 적용 시 국내 기관 데이터로 재학습·재검증 필요"},
        {"label": "기상 사건 주의 부서 건수", "value": "숫자로 못 맞힘", "note": "폭염 주 환경보호국 예측 654건 vs 실제 6,289건 → 경보·범위로 대응"},
        {"label": "예보 기록", "value": "2024~2026", "note": "습도·강수·적설·바람 예보 기록이 2024-01-19부터라 기준일도 2024-02-05부터"},
    ]},
]

# 지연 위험 민원 목록의 민원 유형(뉴욕 311 원문) → 화면 표기. 원문은 화면에 작게 함께 보여 줍니다.
COMPLAINT_KO = {
    "Consumer Complaint": "소비자 피해", "Lot Condition": "공터 관리 불량", "Construction Lead Dust": "공사 납 먼지",
    "Encampment": "노숙 텐트", "New Tree Request": "가로수 식재 요청", "Special Projects Inspection Team (SPIT)": "특별 점검팀 점검",
    "Root/Sewer/Sidewalk Condition": "나무뿌리·하수·보도 손상", "Sewer": "하수도", "Building/Use": "건물 용도 위반",
    "Water Maintenance": "상수도 유지보수", "Sidewalk Condition": "보도 파손", "Curb Condition": "연석 파손",
    "Street Condition": "도로 파손", "Day Care": "어린이집", "Elevator": "승강기", "Water System": "상수도 설비",
    "Smoking": "흡연", "Street Light Condition": "가로등 고장", "SNW": "제설·결빙", "Lead": "납 오염",
    "Homeless Person Assistance": "노숙인 지원 요청", "Maintenance or Facility": "공원 시설 관리", "Water Quality": "수질",
    "Plumbing": "배관", "General Construction/Plumbing": "일반 공사·배관", "Highway Condition": "고속도로 파손",
    "Smoking or Vaping": "흡연·전자담배", "Sewer Maintenance": "하수도 유지보수", "Noise": "소음",
    "Overgrown Tree/Branches": "웃자란 나무·가지", "Bridge Condition": "교량 상태", "Dead/Dying Tree": "고사 나무",
    "E-Scooter": "전동킥보드", "Street Sign - Damaged": "도로 표지 파손", "Broken Parking Meter": "주차 미터기 고장",
    "Graffiti": "낙서", "Damaged Tree": "나무 손상", "Adopt-A-Basket": "가로 쓰레기통 관리", "Illegal Tree Damage": "불법 수목 훼손",
    "Borough Office": "자치구 사무소 문의", "Street Sign - Missing": "도로 표지 분실", "Plant": "식물 관리",
    "Harboring Bees/Wasps": "벌집", "Missed Collection": "수거 누락", "Food Establishment": "음식점 위생",
    "Hazardous Material": "유해 물질", "Poison Ivy": "독성 식물", "Outdoor Dining": "야외 영업",
    "Highway Sign - Missing": "고속도로 표지 분실", "Bike Rack": "자전거 거치대", "Mobile Food Vendor": "이동 음식 판매",
    "Highway Sign - Damaged": "고속도로 표지 파손", "Green Infrastructure": "녹색 인프라",
}
