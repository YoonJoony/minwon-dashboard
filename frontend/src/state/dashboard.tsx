/* eslint-disable react-refresh/only-export-components -- 상태 Provider와 훅을 한 파일에 둡니다 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { Meta, Scenario } from '../api/client'
import {
  addDaysISO,
  clampPeriod,
  daysBetween,
  detectPreset,
  isShortPeriod,
  presetRange,
  type PresetKey,
} from '../lib/period'

/** 화면 선택값. 모두 URL 쿼리(?asof=&start=&end=&agency=&ppd=&demo=)에 저장해 링크로 같은 화면을 공유합니다. */
export type DashState = {
  asof: string
  start: string
  end: string
  agency: string | null
  ppd: number // 가정값: 1인당 하루 처리 건수
  demo: number | null // 시연 단계 (0부터)
}

/** 시연 순서: 평상시 → 폭염 → 블리자드 → 봄철 도로 파손 → 집중관리 */
const DEMO_ORDER = ['S4', 'S1', 'S2', 'S3', 'S5']

export function demoSteps(meta: Meta): Scenario[] {
  const byId = new Map(meta.scenarios.map((s) => [s.id, s]))
  const ordered = DEMO_ORDER.map((id) => byId.get(id)).filter((s): s is Scenario => s !== undefined)
  return [...ordered, ...meta.scenarios.filter((s) => !DEMO_ORDER.includes(s.id))]
}

export function readUrl(meta: Meta, search: string): DashState {
  const q = new URLSearchParams(search)
  const qa = q.get('asof')
  const asof = qa && meta.asofs.includes(qa) ? qa : meta.latest
  const def = presetRange(asof, '7d')
  const { start, end } = clampPeriod(asof, q.get('start') ?? def.start, q.get('end') ?? def.end, meta.max_days)
  const ag = q.get('agency')
  const agency = ag && meta.agencies.some((a) => a.code === ag) ? ag : null
  const p = Number(q.get('ppd'))
  const ppd = Number.isFinite(p) && p > 0 && p <= 200 ? p : meta.per_person_default
  const dm = Number(q.get('demo'))
  const demo = Number.isInteger(dm) && dm >= 1 && dm <= meta.scenarios.length ? dm - 1 : null
  return { asof, start, end, agency, ppd, demo }
}

function writeUrl(s: DashState, meta: Meta, push: boolean) {
  const q = new URLSearchParams({ asof: s.asof, start: s.start, end: s.end })
  if (s.agency) q.set('agency', s.agency)
  if (s.ppd !== meta.per_person_default) q.set('ppd', String(s.ppd))
  if (s.demo !== null) q.set('demo', String(s.demo + 1))
  const url = `${window.location.pathname}?${q.toString()}`
  if (url === window.location.pathname + window.location.search) return
  if (push) window.history.pushState(null, '', url)
  else window.history.replaceState(null, '', url)
}

type Ctx = {
  meta: Meta
  state: DashState
  period: { asof: string; start: string; end: string }
  preset: PresetKey | 'custom'
  days: number
  short: boolean
  isLatest: boolean
  steps: Scenario[]
  /** 지금 화면이 시나리오 설정과 같으면 그 시나리오 */
  scenario: Scenario | null
  demoScenario: Scenario | null
  agencyName: (code: string | null) => string
  agencyShort: (code: string) => string
  setAsof: (asof: string) => void
  setPreset: (key: PresetKey) => void
  setRange: (start: string, end: string) => void
  setAgency: (code: string | null) => void
  toggleAgency: (code: string) => void
  setPpd: (n: number) => void
  applyScenario: (sc: Scenario) => void
  startDemo: () => void
  gotoDemo: (i: number) => void
  stopDemo: () => void
  goLatest: () => void
  evidence: { open: boolean; section: string | null }
  openEvidence: (section?: string) => void
  closeEvidence: () => void
}

const DashContext = createContext<Ctx | null>(null)

export function DashboardProvider({ meta, children }: { meta: Meta; children: ReactNode }) {
  const [state, setState] = useState<DashState>(() => readUrl(meta, window.location.search))
  const [push, setPush] = useState(false)
  const [evidence, setEvidence] = useState<{ open: boolean; section: string | null }>({ open: false, section: null })
  const steps = useMemo(() => demoSteps(meta), [meta])

  // 처음에는 정리된 주소로 바꾸고(replace), 사용자가 바꾼 뒤에는 기록을 쌓습니다(push → 뒤로 가기 가능).
  useEffect(() => {
    writeUrl(state, meta, push)
  }, [state, meta, push])

  useEffect(() => {
    const onPop = () => {
      setPush(false)
      setState(readUrl(meta, window.location.search))
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [meta])

  const update = useCallback((fn: (s: DashState) => DashState) => {
    setPush(true)
    setState(fn)
  }, [])

  const applyScenarioState = useCallback(
    (s: DashState, sc: Scenario, demo: number | null): DashState => ({
      ...s,
      asof: sc.asof,
      start: sc.start,
      end: sc.end,
      agency: sc.agency ?? null,
      demo,
    }),
    [],
  )

  const value = useMemo<Ctx>(() => {
    const { asof, start, end } = state
    const preset = detectPreset(asof, start, end)
    const scenario =
      meta.scenarios.find((sc) => sc.asof === asof && sc.start === start && sc.end === end) ?? null
    const names = new Map(meta.agencies.map((a) => [a.code, a]))
    return {
      meta,
      state,
      period: { asof, start, end },
      preset,
      days: daysBetween(start, end),
      short: isShortPeriod(asof, end),
      isLatest: asof === meta.latest,
      steps,
      scenario,
      demoScenario: state.demo !== null ? (steps[state.demo] ?? null) : null,
      agencyName: (code) => (code ? (names.get(code)?.name ?? code) : '전체 부서'),
      agencyShort: (code) => names.get(code)?.short ?? code,
      setAsof: (a) =>
        update((s) => {
          const p = detectPreset(s.asof, s.start, s.end)
          if (p !== 'custom') return { ...s, asof: a, ...presetRange(a, p), demo: null }
          const n = daysBetween(s.start, s.end)
          return { ...s, asof: a, ...clampPeriod(a, a, addDaysISO(a, n - 1), meta.max_days), demo: null }
        }),
      setPreset: (key) => update((s) => ({ ...s, ...presetRange(s.asof, key), demo: null })),
      setRange: (st, en) => update((s) => ({ ...s, ...clampPeriod(s.asof, st, en, meta.max_days), demo: null })),
      setAgency: (code) => update((s) => ({ ...s, agency: code })),
      toggleAgency: (code) => update((s) => ({ ...s, agency: s.agency === code ? null : code })),
      setPpd: (n) => update((s) => ({ ...s, ppd: Math.min(200, Math.max(1, Math.round(n))) })),
      applyScenario: (sc) => update((s) => applyScenarioState(s, sc, null)),
      startDemo: () => update((s) => (steps[0] ? applyScenarioState(s, steps[0], 0) : s)),
      gotoDemo: (i) => update((s) => (steps[i] ? applyScenarioState(s, steps[i], i) : s)),
      stopDemo: () => update((s) => ({ ...s, demo: null })),
      goLatest: () => update((s) => ({ ...s, asof: meta.latest, ...presetRange(meta.latest, '7d'), demo: null })),
      evidence,
      openEvidence: (section) => setEvidence({ open: true, section: section ?? null }),
      closeEvidence: () => setEvidence((e) => ({ ...e, open: false })),
    }
  }, [state, meta, steps, update, applyScenarioState, evidence])

  return <DashContext.Provider value={value}>{children}</DashContext.Provider>
}

export function useDash(): Ctx {
  const ctx = useContext(DashContext)
  if (!ctx) throw new Error('DashboardProvider 안에서만 쓸 수 있습니다.')
  return ctx
}
