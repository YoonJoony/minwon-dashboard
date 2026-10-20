import type { SummaryOut } from '../api/client'
import { fmtInt, fmtMult, fmtPeople } from './format'
import { QUADRANT_COLOR, QUADRANT_DESC } from './theme'

export type ChipTone = 'danger' | 'warning' | 'ok' | 'muted'

export type KpiView = {
  key: string
  label: string
  value: string
  unit?: string
  valueColor?: string
  note: string
  trend?: number
  chip?: { text: string; tone: ChipTone }
  sub: string
}

/** 상단 핵심 지표 5칸의 문구를 만듭니다 (화면과 테스트가 함께 씀). */
export function buildKpis(s: SummaryOut, o: { days: number; ppd: number; agencySelected: boolean }): KpiView[] {
  const k = s.kpis
  const f = k.forecast
  const q = k.agency_quadrant
  return [
    {
      key: 'forecast',
      label: `예상 접수 · ${o.days}일`,
      value: fmtInt(f.pred),
      unit: '건',
      note: `평소 ${fmtInt(f.base)}건`,
      trend: f.change,
      sub: `80% 범위 ${fmtInt(f.lo)} ~ ${fmtInt(f.hi)}건` + (f.actual != null ? ` · 실제 ${fmtInt(f.actual)}건` : ''),
    },
    {
      key: 'alerts',
      label: '기상 특보 예보 · 7일',
      value: k.alert_count > 0 ? String(k.alert_count) : '없음',
      unit: k.alert_count > 0 ? '건' : undefined,
      note: k.alert_top ? '' : '특보 수준 날씨 예보 없음',
      chip: k.alert_top ? { text: k.alert_top, tone: k.alert_top.includes('경보') ? 'danger' : 'warning' } : undefined,
      sub: k.alert_detail,
    },
    o.agencySelected && q
      ? {
          key: 'focus',
          label: '부서 판정',
          value: q,
          valueColor: QUADRANT_COLOR[q],
          note: `전체 집중관리 ${k.focus_count}곳`,
          sub: QUADRANT_DESC[q] ?? '',
        }
      : {
          key: 'focus',
          label: '집중관리 부서',
          value: String(k.focus_count),
          unit: '곳',
          valueColor: k.focus_count > 0 ? QUADRANT_COLOR['집중관리'] : undefined,
          note: k.focus_count > 0 ? k.focus_names.join(', ') : '해당 부서 없음',
          sub: `접수 증가 + 적체 증가 · 접수증가 주의 ${k.increase_count}곳`,
        },
    {
      key: 'backlog',
      label: '처리 중 민원',
      value: fmtInt(k.backlog_open),
      unit: '건',
      note: `평소 ${fmtInt(k.backlog_normal)}건`,
      chip: { text: fmtMult(k.backlog_multiple), tone: k.backlog_multiple >= 1.3 ? 'warning' : 'muted' },
      sub: '최근 6개월 접수분 중 미처리 (주 단위 집계)',
    },
    {
      key: 'staff',
      label: '지원 필요 인원',
      value: k.need_people > 0 && k.need_people < 0.05 ? '<0.1' : fmtPeople(k.need_people),
      unit: '명',
      note: k.need_count >= 1 ? `적체 증가 예상 ${fmtInt(k.need_count)}건` : '적체 증가 예상 부서 없음',
      sub:
        `1인 하루 ${o.ppd}건 · 지원 가능 ${k.support_count}곳` +
        (k.coverage != null ? ` · 충당 ${Math.round(k.coverage * 100)}%` : ''),
    },
  ]
}
