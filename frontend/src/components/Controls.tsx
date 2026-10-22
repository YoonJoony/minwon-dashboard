import clsx from 'clsx'
import { CalendarDays, CalendarRange, ChevronDown, Minus, Plus, Settings } from 'lucide-react'
import { useMemo, useState } from 'react'
import { fmtDate, fmtDateW, fmtRange } from '../lib/format'
import { addDaysISO, isShortPeriod, presetRange, PRESET_KEYS } from '../lib/period'
import { useDash } from '../state/dashboard'
import { IconButton, Popover } from './ui'

const triggerCls =
  'inline-flex h-11 items-center gap-2 rounded-xl border border-line bg-white px-3.5 text-[14px] font-medium text-ink transition hover:border-line-strong'

/* ------------------------------------------------------------------ 기준일 */

/** 기준일 창 드롭다운에서 빼는 시나리오 (시연 모드 단계에는 그대로 남음) */
const HIDDEN_IN_PICKER = new Set(['S4'])

/**
 * 기준일 창: 왼쪽은 최신·시나리오 드롭다운과 월요일 달력, 오른쪽은 기간 시작~끝 직접 지정.
 * 기준일을 바꾸면 창은 열린 채로 두어 이어서 기간을 고칠 수 있게 함.
 */
export function AsofPicker() {
  const { meta, state, steps, setAsof, applyScenario, scenario, isLatest } = useDash()
  const [open, setOpen] = useState(false)
  const years = useMemo(() => [...new Set(meta.asofs.map((d) => d.slice(0, 4)))], [meta.asofs])
  const [year, setYear] = useState(state.asof.slice(0, 4))
  const months = useMemo(() => {
    const m = new Map<string, string[]>()
    for (const d of meta.asofs.filter((x) => x.startsWith(year))) {
      const k = d.slice(5, 7)
      m.set(k, [...(m.get(k) ?? []), d])
    }
    return [...m.entries()]
  }, [meta.asofs, year])
  const choices = steps.filter((sc) => !HIDDEN_IN_PICKER.has(sc.id))
  // 드롭다운 값: 처음(기본)은 최신. 시나리오면 그 시나리오, 달력에서 고른 날이면 '목록에서 고른 날'
  const value = isLatest ? 'latest' : scenario && !HIDDEN_IN_PICKER.has(scenario.id) ? scenario.id : 'other'

  const badge = isLatest ? '최신' : scenario ? scenario.title : '과거 재현'

  return (
    <Popover
      open={open}
      onOpenChange={(v) => {
        setOpen(v)
        if (v) setYear(state.asof.slice(0, 4))
      }}
      align="right"
      width={700}
      trigger={
        <button type="button" className={triggerCls} onClick={() => setOpen(!open)} aria-haspopup="dialog" aria-expanded={open}>
          <CalendarDays size={17} strokeWidth={1.9} className="text-mute" />
          <span className="text-mute">기준일</span>
          <span className="num font-semibold">{fmtDateW(state.asof)}</span>
          <span
            className={clsx(
              'rounded-md px-1.5 py-0.5 text-[11px] font-semibold',
              isLatest ? 'bg-[#e5f5ed] text-[#17955a]' : 'bg-brand-tint text-brand',
            )}
          >
            {badge}
          </span>
          <ChevronDown size={16} className="text-mute" />
        </button>
      }
    >
      <div className="grid gap-3 p-1 sm:grid-cols-[minmax(0,1fr)_260px]">
        {/* 왼쪽: 최신·시나리오 드롭다운 + 기준일 목록 */}
        <div className="min-w-0">
          <label className="block px-2 pt-1">
            <span className="text-[12px] font-semibold text-mute">최신 · 시연 시나리오</span>
            <span className="relative mt-1.5 block">
              <select
                aria-label="최신 · 시연 시나리오"
                value={value}
                onChange={(e) => {
                  const v = e.target.value
                  if (v === 'latest') setAsof(meta.latest)
                  else {
                    const sc = choices.find((s) => s.id === v)
                    if (sc) applyScenario(sc)
                  }
                  setYear((v === 'latest' ? meta.latest : (choices.find((s) => s.id === v)?.asof ?? state.asof)).slice(0, 4))
                }}
                className="h-10 w-full appearance-none rounded-xl border border-line bg-white pl-3 pr-9 text-[14px] font-semibold text-ink hover:border-line-strong"
              >
                <option value="latest">최신 · {fmtDateW(meta.latest)}</option>
                {choices.map((sc) => (
                  <option key={sc.id} value={sc.id}>
                    {sc.title} · {fmtDate(sc.asof)} ({fmtRange(sc.start, sc.end)})
                  </option>
                ))}
                {value === 'other' && (
                  <option value="other" disabled>
                    {scenario ? scenario.title : '목록에서 고른 날'} · {fmtDate(state.asof)}
                  </option>
                )}
              </select>
              <ChevronDown size={16} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-mute" />
            </span>
          </label>
          <div className="mt-3 border-t border-line px-2 pt-3">
            <div className="flex items-center justify-between">
              <p className="text-[12px] font-semibold text-mute">기준일 목록 · 매주 월요일</p>
              <div className="flex gap-1" role="tablist" aria-label="연도">
                {years.map((y) => (
                  <button
                    key={y}
                    type="button"
                    role="tab"
                    aria-selected={y === year}
                    onClick={() => setYear(y)}
                    className={clsx(
                      'rounded-lg px-2 py-1 text-[12px] font-semibold num',
                      y === year ? 'bg-ink text-white' : 'text-mute hover:bg-page',
                    )}
                  >
                    {y}
                  </button>
                ))}
              </div>
            </div>
            <div className="mt-2 max-h-[232px] space-y-1 overflow-y-auto pb-1 pr-1">
              {months.map(([mm, ds]) => (
                <div key={mm} className="flex items-center gap-2">
                  <span className="w-9 shrink-0 text-[12px] text-faint num">{Number(mm)}월</span>
                  <div className="flex flex-wrap gap-1">
                    {ds.map((d) => (
                      <button
                        key={d}
                        type="button"
                        onClick={() => setAsof(d)}
                        title={fmtDateW(d)}
                        className={clsx(
                          'h-7 min-w-8 rounded-lg px-1.5 text-[12px] font-medium num transition',
                          d === state.asof ? 'bg-brand text-white' : 'bg-page text-ink hover:bg-brand-tint',
                        )}
                      >
                        {Number(d.slice(8, 10))}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
        {/* 오른쪽: 기간 직접 지정 (기준일이 바뀌면 새 기준일 기준으로 다시 채움) */}
        <RangeEditor key={`${state.asof}|${state.start}|${state.end}`} onApplied={() => setOpen(false)} />
      </div>
    </Popover>
  )
}

/** 기간 시작~끝 직접 지정 (기준일부터 최대 92일) */
function RangeEditor({ onApplied }: { onApplied: () => void }) {
  const { meta, state, setRange } = useDash()
  const [draft, setDraft] = useState({ start: state.start, end: state.end })
  const last = addDaysISO(state.asof, meta.max_days - 1)
  const invalid = draft.start < state.asof || draft.end < draft.start || draft.end > last
  return (
    <div className="min-w-0 rounded-xl bg-page p-3 sm:self-start">
      <p className="text-[12px] font-semibold text-mute">기간 직접 지정</p>
      <p className="mt-0.5 text-[12px] text-faint">기준일부터 최대 {meta.max_days}일</p>
      <div className="mt-2.5 grid grid-cols-2 gap-2 sm:grid-cols-1">
        <label className="text-[12px] text-mute">
          시작
          <input
            type="date"
            value={draft.start}
            min={state.asof}
            max={last}
            onChange={(e) => setDraft((d) => ({ ...d, start: e.target.value }))}
            className="mt-1 h-9 w-full rounded-lg border border-line bg-white px-2 text-[13px] text-ink num"
          />
        </label>
        <label className="text-[12px] text-mute">
          끝
          <input
            type="date"
            value={draft.end}
            min={draft.start || state.asof}
            max={last}
            onChange={(e) => setDraft((d) => ({ ...d, end: e.target.value }))}
            className="mt-1 h-9 w-full rounded-lg border border-line bg-white px-2 text-[13px] text-ink num"
          />
        </label>
      </div>
      <p className={clsx('mt-2 text-[12px] leading-snug', invalid ? 'text-up' : 'text-faint')}>
        {invalid ? `${fmtDate(state.asof)} ~ ${fmtDate(last)} 사이에서 고르세요` : '15일 이후가 포함되면 월별 방식으로 예측'}
      </p>
      <button
        type="button"
        disabled={invalid}
        onClick={() => {
          setRange(draft.start, draft.end)
          onApplied()
        }}
        className="mt-2.5 h-9 w-full rounded-lg bg-ink text-[13px] font-semibold text-white disabled:opacity-30"
      >
        기간 적용
      </button>
    </div>
  )
}

/* ------------------------------------------------------------------ 기간 */

/** 빠른 선택(기준일부터 7일·한 달·분기). 직접 지정은 기준일 창 오른쪽에 있음 */
export function PeriodPicker() {
  const { meta, state, preset, days, setPreset } = useDash()
  const [open, setOpen] = useState(false)
  const label = preset === 'custom' ? '직접 지정' : meta.presets.find((p) => p.key === preset)?.label

  return (
    <Popover
      open={open}
      onOpenChange={setOpen}
      align="right"
      width={320}
      trigger={
        <button type="button" className={triggerCls} onClick={() => setOpen(!open)} aria-haspopup="dialog" aria-expanded={open}>
          <CalendarRange size={17} strokeWidth={1.9} className="text-mute" />
          <span className="font-semibold">{label}</span>
          <span className="text-mute num">
            {fmtRange(state.start, state.end)} · {days}일
          </span>
          <ChevronDown size={16} className="text-mute" />
        </button>
      }
    >
      <div className="p-1">
        <p className="px-2 pb-1.5 pt-1 text-[12px] font-semibold text-mute">빠른 선택 (기준일부터)</p>
        {PRESET_KEYS.map((k) => {
          const r = presetRange(state.asof, k)
          const lbl = meta.presets.find((p) => p.key === k)?.label ?? k
          const short = isShortPeriod(state.asof, r.end)
          return (
            <button
              key={k}
              type="button"
              onClick={() => {
                setPreset(k)
                setOpen(false)
              }}
              className={clsx(
                'flex w-full items-center justify-between gap-3 rounded-xl px-2.5 py-2 text-left transition',
                preset === k ? 'bg-brand-tint' : 'hover:bg-page',
              )}
            >
              <span>
                <span className={clsx('block text-[14px] font-semibold', preset === k ? 'text-brand' : 'text-ink')}>{lbl}</span>
                <span className="block text-[12px] text-mute num">{fmtRange(r.start, r.end)}</span>
              </span>
              <span className="rounded-md bg-page px-1.5 py-0.5 text-[11px] font-medium text-mute">
                {short ? '단기 모델' : '월별 방식'}
              </span>
            </button>
          )
        })}
        <p className="px-2 pb-1 pt-2 text-[12px] text-faint">날짜를 직접 정하려면 기준일 창 오른쪽에서 고르세요</p>
      </div>
    </Popover>
  )
}

/* ------------------------------------------------------------------ 가정값 */

export function PpdStepper({ compact = false }: { compact?: boolean }) {
  const { state, setPpd } = useDash()
  return (
    <div className={clsx('inline-flex items-center rounded-xl border border-line bg-white', compact ? 'h-8' : 'h-10')}>
      <button
        type="button"
        aria-label="1인당 하루 처리 건수 줄이기"
        onClick={() => setPpd(state.ppd - 1)}
        disabled={state.ppd <= 1}
        className="flex h-full w-8 items-center justify-center text-mute hover:text-ink disabled:opacity-30"
      >
        <Minus size={15} />
      </button>
      <input
        aria-label="1인당 하루 처리 건수"
        type="number"
        min={1}
        max={200}
        value={state.ppd}
        onChange={(e) => {
          const n = Number(e.target.value)
          if (Number.isFinite(n) && n >= 1) setPpd(n)
        }}
        className="h-full w-11 border-x border-line text-center text-[14px] font-semibold text-ink num [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none"
      />
      <button
        type="button"
        aria-label="1인당 하루 처리 건수 늘리기"
        onClick={() => setPpd(state.ppd + 1)}
        disabled={state.ppd >= 200}
        className="flex h-full w-8 items-center justify-center text-mute hover:text-ink disabled:opacity-30"
      >
        <Plus size={15} />
      </button>
    </div>
  )
}

export function SettingsButton() {
  const { meta, state, setPpd } = useDash()
  const [open, setOpen] = useState(false)
  return (
    <Popover
      open={open}
      onOpenChange={setOpen}
      align="right"
      width={340}
      trigger={
        <IconButton label="가정값 설정" className="size-11" onClick={() => setOpen(!open)}>
          <Settings size={19} strokeWidth={1.9} />
        </IconButton>
      }
    >
      <div className="p-3">
        <p className="text-[14px] font-semibold text-ink">가정값</p>
        <div className="mt-3 flex items-center justify-between gap-3">
          <span className="text-[13px] text-ink">1인당 하루 처리 건수</span>
          <PpdStepper />
        </div>
        <p className="mt-3 rounded-xl bg-page px-3 py-2.5 text-[12px] leading-relaxed text-mute">
          뉴욕 데이터에는 민원 처리 인원이 없어 지원 필요 인원을 이 가정값으로 환산합니다. 국내 적용 시 실제 정원·현원 자료로 바꿉니다.
        </p>
        {state.ppd !== meta.per_person_default && (
          <button
            type="button"
            onClick={() => setPpd(meta.per_person_default)}
            className="mt-2 text-[12px] font-semibold text-brand"
          >
            기본값({meta.per_person_default}건)으로 되돌리기
          </button>
        )}
      </div>
    </Popover>
  )
}
