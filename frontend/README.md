# 스마트 민원케어 — 화면 (React + TypeScript)

| 명령 | 내용 |
|---|---|
| `npm run dev` | 개발 서버 (http://localhost:5173, `/api`는 8000번 FastAPI로 전달) |
| `npm run build` | 타입 검사 후 `dist/` 생성 → FastAPI가 같은 서버에서 제공 |
| `npm test` | Vitest (기간 계산, 숫자 표기, 상단 지표 문구, 차트 보조 계산) |
| `npm run lint` | ESLint |
| `npm run gen:api` | 백엔드 응답 형식(`backend/app/schemas.py`)에서 `src/api/schema.d.ts` 다시 만들기 |

## 폴더

```
src/
├─ api/          openapi-fetch 클라이언트, TanStack Query 훅, 자동 생성 타입
├─ state/        화면 선택값(URL과 동기화), 시연 단계, 근거 창 상태
├─ components/   헤더·탭·제목·KPI·패널 6개·근거 창·시연 조작 막대, 공용 부품(ui.tsx)
├─ charts/       ECharts 훅, 예상 접수 추이·위험 매트릭스 옵션(이름표 겹침 피하기 포함)
├─ lib/          날짜·숫자 표기, 기간 규칙, 색, KPI 문구
└─ hooks/        요소 폭 감시
```

설계와 시안 반영 내용은 [../docs/개발설계.md](../docs/개발설계.md) 8장을 보세요.
