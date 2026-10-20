import clsx from 'clsx'
import { Fragment, useState } from 'react'
import type { WeatherDay } from '../api/client'
import { useWeatherStrip } from '../api/hooks'
import { fmtMD, fmtMDW } from '../lib/format'
import { summarizeAlerts } from '../lib/weather'
import { useDash } from '../state/dashboard'
import { LEVEL_TONE, SKY_ICON, WX_ALERT_ICON } from './icons'
import { WeatherModal } from './WeatherModal'

const round = (v: number | null | undefined) => (v == null ? '–' : String(Math.round(v)))

function dayTitle(d: WeatherDay) {
  const lines = [
    `${fmtMDW(d.date)} · ${d.icon_label ?? '정보 없음'} ${round(d.tmax)}/${round(d.tmin)}°C`,
    `${d.offset === 0 ? '전날' : '기준일'} 발표 예보 (${d.lead}일 전) · ${d.mode === '예보' ? '예보' : '참고(가능성)'}`,
  ]
  if (d.prcp != null && d.prcp >= 1) lines.push(`강수 ${Math.round(d.prcp)}mm`)
  if (d.snow != null && d.snow >= 1) lines.push(`적설 ${Math.round(d.snow)}cm`)
  for (const a of d.alerts) lines.push(a.source === 'NWS' ? `${a.label} — NWS 발표 ${a.issued ?? ''}` : `${a.label} (예보 판정)`)
  lines.push('누르면 과거 7년 같은 기상 이슈를 봅니다')
  return lines.join('\n')
}

function DayCell({ d, selected, onClick }: { d: WeatherDay; selected: boolean; onClick: () => void }) {
  const sky = d.icon ? SKY_ICON[d.icon] : null
  const kinds = summarizeAlerts(d.alerts)
  return (
    <button
      type="button"
      onClick={onClick}
      title={dayTitle(d)}
      aria-label={`${fmtMDW(d.date)} 예보 ${d.icon_label ?? ''}${kinds.length ? ', 특보 ' + kinds.map((k) => k.labels[0]).join(', ') : ''}`}
      className={clsx(
        'flex w-[66px] shrink-0 flex-col items-center rounded-xl px-1 pb-1 pt-1.5 transition',
        selected ? 'bg-brand-tint ring-1 ring-brand/40' : 'hover:bg-white',
        d.mode === '참고' && !selected && 'opacity-60 hover:opacity-100',
      )}
    >
      <span className="whitespace-nowrap text-[11px] leading-none">
        <b className={clsx('font-semibold', d.offset === 0 ? 'text-brand' : 'text-ink')}>{d.label}</b>{' '}
        <span className="text-faint num">{fmtMD(d.date)}</span>
      </span>
      <span className="mt-1 flex items-center gap-1">
        {sky ? <sky.icon size={18} color={sky.color} strokeWidth={1.9} aria-hidden="true" /> : <span className="text-faint">–</span>}
        <span className="text-[12px] font-semibold text-ink num">{round(d.tmax)}°</span>
        <span className="text-[11px] text-faint num">{round(d.tmin)}°</span>
      </span>
      <span className="mt-1 flex h-4 items-center gap-0.5">
        {kinds.map((k) => {
          const Icon = WX_ALERT_ICON[k.kind]
          const tone = LEVEL_TONE[k.level] ?? LEVEL_TONE[1]
          return (
            <span
              key={k.kind}
              className={clsx('flex size-4 items-center justify-center rounded', k.nws && 'ring-1')}
              style={{ background: tone.bg, color: tone.icon, ['--tw-ring-color' as string]: tone.icon }}
            >
              <Icon size={11} strokeWidth={2.4} aria-hidden="true" />
            </span>
          )
        })}
        {kinds.length === 0 && d.prcp != null && d.prcp >= 1 && (
          <span className="text-[10px] font-medium text-[#3b82f6] num">{Math.round(d.prcp)}mm</span>
        )}
      </span>
    </button>
  )
}

/** 탭 줄 가운데 7일 기상 예보 띠 (기준일 포함 8칸). 칸을 누르면 과거 7년 모달 */
export function WeatherStrip({ className }: { className?: string }) {
  const { state } = useDash()
  const { data, error } = useWeatherStrip(state.asof)
  const [open, setOpen] = useState<string | null>(null)
  if (error) return null
  const firstRef = data ? data.days.findIndex((d) => d.mode === '참고') : -1
  return (
    <div className={clsx('min-w-0', className)} role="group" aria-label="7일 기상 예보">
      <div className="no-scrollbar flex items-stretch gap-0.5 overflow-x-auto rounded-2xl border border-line bg-[#fbfbfd] p-0.5">
        {!data
          ? Array.from({ length: 8 }, (_, i) => <div key={i} className="skeleton h-[60px] w-[66px] shrink-0" />)
          : data.days.map((d, i) => (
              <Fragment key={d.date}>
                {i === firstRef && (
                  <span className="mx-0.5 flex shrink-0 flex-col items-center justify-center gap-1 text-[10px] text-faint" title="+4일부터는 가능성만 보여 주는 참고 예보입니다">
                    <span className="h-5 w-px bg-line-strong" />
                    참고
                    <span className="h-5 w-px bg-line-strong" />
                  </span>
                )}
                <DayCell d={d} selected={open === d.date} onClick={() => setOpen(d.date)} />
              </Fragment>
            ))}
      </div>
      <WeatherModal asof={state.asof} date={open} onClose={() => setOpen(null)} />
    </div>
  )
}
