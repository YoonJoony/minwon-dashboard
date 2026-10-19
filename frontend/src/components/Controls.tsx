import clsx from 'clsx'
import { CalendarDays, CalendarRange, Check, ChevronDown, Minus, Plus, Settings } from 'lucide-react'
import { useMemo, useState } from 'react'
import { fmtDate, fmtDateW, fmtRange } from '../lib/format'
import { addDaysISO, isShortPeriod, presetRange, PRESET_KEYS } from '../lib/period'
import { useDash } from '../state/dashboard'
import { IconButton, Popover } from './ui'

const triggerCls =
  'inline-flex h-11 items-center gap-2 rounded-xl border border-line bg-white px-3.5 text-[14px] font-medium text-ink transition hover:border-line-strong'

/* ------------------------------------------------------------------ 기준일 */

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

  const badge = isLatest ? '최신' : scenario ? scenario.title : '과거 재현'
  const close = () => setOpen(false)

  return (
    <Popover
      open={open}
      onOpenChange={(v) => {
        setOpen(v)
        if (v) setYear(state.asof.slice(0, 4))
      }}
      align="right"
      width={420}
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
      <div className="p-1">
        <p className="px-2 pb-1.5 pt-1 text-[12px] font-semibold text-mute">빠른 선택</p>
        <PickRow
          active={isLatest}
          title="최신"
          meta={fmtDateW(meta.latest)}
          desc="민원 데이터 마지막 날"
          onClick={() => {
            setAsof(meta.latest)
            close()
          }}
        />
        {steps.map((sc) => (
          <PickRow
            key={sc.id}
            active={scenario?.id === sc.id}
            title={sc.title}
            meta={fmtDate(sc.asof)}
            desc={`시연 시나리오 · ${fmtRange(sc.start, sc.end)}`}
            onClick={() => {
              applyScenario(sc)
              close()
            }}
          />
        ))}
        <div className="mt-2 border-t border-line px-2 pt-3">
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
                      onClick={() => {
                        setAsof(d)
                        close()
                      }}
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
    </Popover>
  )
}

function PickRow({
  active,
  title,
  meta,
  desc,
  onClick,
}: {
  active: boolean
  title: string
  meta: string
  desc: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx(
        'flex w-full items-center gap-3 rounded-xl px-2.5 py-2 text-left transition',
        active ? 'bg-brand-tint' : 'hover:bg-page',
      )}
    >
      <span className="min-w-0 flex-1">
        <span className="flex items-baseline gap-2">
          <span className={clsx('text-[14px] font-semibold', active ? 'text-brand' : 'text-ink')}>{title}</span>
          <span className="text-[12px] text-mute num">{meta}</span>
        </span>
        <span className="block truncate text-[12px] text-mute">{desc}</span>
      </span>
      {active && <Check size={16} className="text-brand" />}
    </button>
  )
}

/* ------------------------------------------------------------------ 기간 */

export function PeriodPicker() {
  const { meta, state, preset, days, setPreset, setRange } = useDash()
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState({ start: state.start, end: state.end })
  const last = addDaysISO(state.asof, meta.max_days - 1)
  const label = preset === 'custom' ? '직접 지정' : meta.presets.find((p) => p.key === preset)?.label
  const invalid = draft.start < state.asof || draft.end < draft.start || draft.end > last

  return (
    <Popover
      open={open}
      onOpenChange={(v) => {
        setOpen(v)
        if (v) setDraft({ start: state.start, end: state.end })
      }}
      align="right"
      width={360}
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
        <div className="mt-2 border-t border-line px-2 pt-3">
          <p className="text-[12px] font-semibold text-mute">직접 지정 · 기준일부터 최대 {meta.max_days}일</p>
          <div className="mt-2 grid grid-cols-2 gap-2">
            <label className="text-[12px] text-mute">
              시작
              <input
                type="date"
                value={draft.start}
                min={state.asof}
                max={last}
                onChange={(e) => setDraft((d) => ({ ...d, start: e.target.value }))}
                className="mt-1 h-9 w-full rounded-lg border border-line px-2 text-[13px] text-ink num"
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
                className="mt-1 h-9 w-full rounded-lg border border-line px-2 text-[13px] text-ink num"
              />
            </label>
          </div>
          <div className="mt-2 flex items-center justify-between gap-2 pb-1">
            <span className={clsx('text-[12px]', invalid ? 'text-up' : 'text-faint')}>
              {invalid ? `${fmtDate(state.asof)} ~ ${fmtDate(last)} 사이에서 고르세요` : '15일 이후가 포함되면 월별 방식으로 예측'}
            </span>
            <button
              type="button"
              disabled={invalid}
              onClick={() => {
                setRange(draft.start, draft.end)
                setOpen(false)
              }}
              className="h-8 shrink-0 rounded-lg bg-ink px-3 text-[13px] font-semibold text-white disabled:opacity-30"
            >
              적용
            </button>
          </div>
        </div>
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
