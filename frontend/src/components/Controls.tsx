import clsx from 'clsx'
import { CalendarDays, CalendarRange, Check, ChevronDown, Minus, Plus, Settings } from 'lucide-react'
import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { fmtDate, fmtDateW, fmtRange } from '../lib/format'
import { addDaysISO, daysBetween, isShortPeriod, presetRange, PRESET_KEYS, SHORT_DAYS } from '../lib/period'
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
          <div className="px-2 pt-1">
            <p className="text-[12px] font-semibold text-mute">최신 · 시연 시나리오</p>
            <ChoiceSelect
              label="최신 · 시연 시나리오"
              value={value}
              choices={[
                { value: 'latest', title: '최신', meta: fmtDateW(meta.latest), desc: '민원 데이터 마지막 날' },
                ...choices.map((sc) => ({
                  value: sc.id,
                  title: sc.title,
                  meta: fmtDate(sc.asof),
                  desc: `시연 시나리오 · ${fmtRange(sc.start, sc.end)}`,
                })),
              ]}
              fallback={{
                value: 'other',
                title: scenario ? scenario.title : '목록에서 고른 날',
                meta: fmtDate(state.asof),
                desc: '아래 기준일 목록에서 고른 날',
              }}
              onChange={(v) => {
                // 최신·시나리오를 고르면 창을 닫음 (목록에서 날짜를 고르거나 기간을 고칠 때는 열어 둠)
                setOpen(false)
                if (v === value) return
                const sc = choices.find((x) => x.id === v)
                if (sc) applyScenario(sc)
                else setAsof(meta.latest)
                setYear((sc?.asof ?? meta.latest).slice(0, 4))
              }}
            />
          </div>
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

/** 기간 시작~끝 직접 지정 (기준일부터 최대 92일). 선택한 기간 요약을 보여 주고 적용 버튼은 맨 아래 */
function RangeEditor({ onApplied }: { onApplied: () => void }) {
  const { meta, state, setRange } = useDash()
  const [draft, setDraft] = useState({ start: state.start, end: state.end })
  const last = addDaysISO(state.asof, meta.max_days - 1)
  const invalid = draft.start < state.asof || draft.end < draft.start || draft.end > last
  return (
    <div className="flex min-w-0 flex-col rounded-xl bg-page p-3">
      <p className="text-[12px] font-semibold text-mute">기간 직접 지정</p>
      <p className="mt-0.5 text-[12px] leading-snug text-faint">
        기준일부터 최대 {meta.max_days}일 · 가장 긴 분기(3개월)가 {meta.max_days}일이라 그만큼 미리 계산해 둠
      </p>
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
      {invalid ? (
        <p className="mt-3 rounded-lg bg-white px-2.5 py-2 text-[12px] leading-snug text-up">
          {fmtDate(state.asof)} ~ {fmtDate(last)} 사이에서 고르세요
        </p>
      ) : (
        <RangeSummary asof={state.asof} start={draft.start} end={draft.end} maxDays={meta.max_days} />
      )}
      <button
        type="button"
        disabled={invalid}
        onClick={() => {
          setRange(draft.start, draft.end)
          onApplied()
        }}
        className="mt-auto h-10 w-full shrink-0 rounded-lg bg-ink text-[13px] font-semibold text-white transition hover:bg-[#2a2563] disabled:opacity-30 max-sm:mt-3"
      >
        기간 적용
      </button>
    </div>
  )
}

/** 고른 기간 요약: 일수·예측 방식, 그리고 기준일부터 92일 안에서 어디쯤인지 막대로 (앞 14일 = 단기 모델 구간) */
function RangeSummary({ asof, start, end, maxDays }: { asof: string; start: string; end: string; maxDays: number }) {
  const days = daysBetween(start, end)
  const short = isShortPeriod(asof, end)
  const from = ((daysBetween(asof, start) - 1) / maxDays) * 100
  const width = (days / maxDays) * 100
  return (
    <div className="mb-3 mt-3 rounded-lg bg-white p-2.5">
      <p className="flex items-baseline justify-between gap-2 text-[12px] text-mute">
        <span className="font-semibold text-ink num">{fmtRange(start, end)}</span>
        <span className="num">{days}일</span>
      </p>
      <div className="relative mt-2 h-2 rounded-full bg-page" aria-hidden="true">
        <span className="absolute inset-y-0 left-0 rounded-l-full bg-brand-tint" style={{ width: `${(SHORT_DAYS / maxDays) * 100}%` }} />
        <span className="absolute inset-y-0 rounded-full bg-brand" style={{ left: `${from}%`, width: `${Math.max(width, 1.5)}%` }} />
      </div>
      <p className="mt-1 flex justify-between text-[10.5px] text-faint num">
        <span>기준일</span>
        <span>{SHORT_DAYS}일</span>
        <span>{maxDays}일</span>
      </p>
      <p className="mt-2 text-[12px] leading-snug text-mute">
        <b className="font-semibold text-ink">{short ? '단기 예측 모델' : '월별 계절 지수 방식'}</b>
        {short ? ' · 기준일부터 14일 안' : ' · 15일 이후가 포함됨'}
      </p>
    </div>
  )
}

/** 프로젝트 스타일 드롭다운 (최신·시나리오). 방향키·Enter·Esc로도 고를 수 있음 */
type Choice = { value: string; title: string; meta: string; desc: string }
function ChoiceSelect({
  label,
  value,
  choices,
  fallback,
  onChange,
}: {
  label: string
  value: string
  choices: Choice[]
  fallback: Choice
  onChange: (v: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const wrap = useRef<HTMLDivElement>(null)
  const btn = useRef<HTMLButtonElement>(null)
  const list = useRef<HTMLUListElement>(null)
  const id = useId()
  const cur = choices.find((c) => c.value === value) ?? fallback

  useEffect(() => {
    if (!open) return
    list.current?.focus()
    const onDown = (e: MouseEvent) => {
      if (!wrap.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [open])

  const show = () => {
    setActive(Math.max(0, choices.findIndex((c) => c.value === value)))
    setOpen(true)
  }
  const pick = (i: number) => {
    setOpen(false)
    btn.current?.focus()
    onChange(choices[i].value) // 이미 고른 항목을 다시 골라도 부름 (바깥 창 닫기 등)
  }
  const onListKey = (e: KeyboardEvent) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((a) => (a + (e.key === 'ArrowDown' ? 1 : choices.length - 1)) % choices.length)
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      pick(active)
    } else if (e.key === 'Escape') {
      e.stopPropagation() // 바깥 기준일 창은 닫지 않고 목록만 닫음
      setOpen(false)
      btn.current?.focus()
    } else if (e.key === 'Tab') setOpen(false)
  }

  return (
    <div ref={wrap} className="relative mt-1.5">
      <button
        ref={btn}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`${label}: ${cur.title} ${cur.meta}`}
        onClick={() => (open ? setOpen(false) : show())}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault()
            show()
          }
        }}
        className={clsx(
          'flex h-12 w-full items-center gap-3 rounded-xl border bg-white px-3 text-left transition',
          open ? 'border-brand ring-2 ring-brand/15' : 'border-line hover:border-line-strong',
        )}
      >
        <span className="min-w-0 flex-1">
          <span className="flex items-baseline gap-2">
            <span className="truncate text-[14px] font-semibold text-ink">{cur.title}</span>
            <span className="shrink-0 text-[12px] text-mute num">{cur.meta}</span>
          </span>
          <span className="block truncate text-[11.5px] text-faint">{cur.desc}</span>
        </span>
        <ChevronDown size={16} className={clsx('shrink-0 text-mute transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <ul
          ref={list}
          role="listbox"
          tabIndex={-1}
          aria-label={label}
          aria-activedescendant={`${id}-${active}`}
          onKeyDown={onListKey}
          className="absolute inset-x-0 top-full z-50 mt-1.5 max-h-[300px] overflow-y-auto rounded-xl border border-line bg-white p-1 shadow-[0_14px_36px_-14px_rgba(22,22,29,0.3)] outline-none"
        >
          {choices.map((c, i) => {
            const sel = c.value === value
            return (
              <li
                key={c.value}
                id={`${id}-${i}`}
                role="option"
                aria-selected={sel}
                onMouseEnter={() => setActive(i)}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => pick(i)}
                className={clsx(
                  'flex cursor-pointer items-center gap-3 rounded-lg px-2.5 py-2',
                  sel ? 'bg-brand-tint' : i === active ? 'bg-page' : '',
                )}
              >
                <span className="min-w-0 flex-1">
                  <span className="flex items-baseline gap-2">
                    <span className={clsx('text-[14px] font-semibold', sel ? 'text-brand' : 'text-ink')}>{c.title}</span>
                    <span className="text-[12px] text-mute num">{c.meta}</span>
                  </span>
                  <span className="block truncate text-[12px] text-mute">{c.desc}</span>
                </span>
                {sel && <Check size={16} className="shrink-0 text-brand" />}
              </li>
            )
          })}
        </ul>
      )}
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
