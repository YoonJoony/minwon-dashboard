import clsx from 'clsx'
import { useState } from 'react'
import type { WeatherDay } from '../api/client'
import { useWeatherStrip } from '../api/hooks'
import { fmtMD, fmtMDW } from '../lib/format'
import { summarizeAlerts } from '../lib/weather'
import { useDash } from '../state/dashboard'
import { LEVEL_TONE, SKY_ICON, WX_ALERT_ICON } from './icons'
import { WeatherModal } from './WeatherModal'

const round = (v: number | null | undefined) => (v == null ? '–' : String(Math.round(v)))
// 좁은 칸(모바일)에서도 넘치지 않게 특보 아이콘은 2개까지, 더 있으면 1개 + '+n'
const MAX_BADGES = 2

function dayTitle(d: WeatherDay) {
  const lines = [
    `${fmtMDW(d.date)} · ${d.icon_label ?? '정보 없음'} ${round(d.tmax)}/${round(d.tmin)}°C`,
    `${d.offset === 0 ? '전날' : '기준일'} 발표 예보 (${d.lead}일 전)`,
  ]
  if (d.prcp != null && d.prcp >= 1) lines.push(`강수 ${Math.round(d.prcp)}mm`)
  if (d.snow != null && d.snow >= 1) lines.push(`적설 ${Math.round(d.snow)}cm`)
  for (const a of d.alerts) lines.push(a.source === 'NWS' ? `${a.label} — NWS 발표 ${a.issued ?? ''}` : `${a.label} (예보 판정)`)
  lines.push('누르면 이날 예보를 자세히 봅니다')
  return lines.join('\n')
}

/**
 * 하루 칸. 넓은 화면(lg~)은 세 줄(요일·날짜 / 아이콘·기온 / 특보),
 * 좁은 화면은 8칸이 한 줄에 들어가도록 세로로 쌓음. 칸마다 줄 높이가 같아 위아래가 맞음.
 */
function DayCell({ d, selected, onClick }: { d: WeatherDay; selected: boolean; onClick: () => void }) {
  const sky = d.icon ? SKY_ICON[d.icon] : null
  const kinds = summarizeAlerts(d.alerts)
  const shown = kinds.length > MAX_BADGES ? kinds.slice(0, MAX_BADGES - 1) : kinds
  const more = kinds.length - shown.length
  return (
    <button
      type="button"
      onClick={onClick}
      title={dayTitle(d)}
      aria-label={`${fmtMDW(d.date)} 예보 ${d.icon_label ?? ''}${kinds.length ? ', 특보 ' + kinds.map((k) => k.labels[0]).join(', ') : ''}`}
      className={clsx(
        'flex min-w-0 flex-col items-center gap-1 rounded-xl px-0.5 py-1.5 transition lg:px-1',
        selected ? 'bg-brand-tint ring-1 ring-brand/40' : 'hover:bg-white',
      )}
    >
      <span className="flex flex-col items-center whitespace-nowrap leading-tight lg:flex-row lg:items-baseline lg:gap-1">
        <b className={clsx('text-[12px] font-semibold sm:text-[13px]', d.offset === 0 ? 'text-brand' : 'text-ink')}>{d.label}</b>
        <span className="text-[10.5px] text-faint num sm:text-[12px]">{fmtMD(d.date)}</span>
      </span>
      <span className="flex flex-col items-center gap-0.5 lg:flex-row lg:gap-1.5">
        {sky ? (
          <sky.icon className="size-[22px] shrink-0 sm:size-6" color={sky.color} strokeWidth={1.8} aria-hidden="true" />
        ) : (
          <span className="flex size-[22px] items-center justify-center text-faint sm:size-6">–</span>
        )}
        <span className="flex flex-col items-center whitespace-nowrap leading-tight lg:flex-row lg:items-baseline lg:gap-1">
          <span className="text-[14px] font-semibold text-ink num sm:text-[15px]">{round(d.tmax)}°</span>
          <span className="text-[11.5px] text-faint num sm:text-[12.5px]">{round(d.tmin)}°</span>
        </span>
      </span>
      {/* 특보 (없으면 강수량). 칸마다 같은 높이로 비워 둠 */}
      <span className="flex h-[18px] items-center justify-center gap-0.5 lg:h-5">
        {shown.map((k) => {
          const Icon = WX_ALERT_ICON[k.kind]
          const tone = LEVEL_TONE[k.level] ?? LEVEL_TONE[1]
          return (
            <span
              key={k.kind}
              className={clsx('flex size-[18px] items-center justify-center rounded-md lg:size-5', k.nws && 'ring-1')}
              style={{ background: tone.bg, color: tone.icon, ['--tw-ring-color' as string]: tone.icon }}
            >
              <Icon className="size-3 lg:size-[13px]" strokeWidth={2.4} aria-hidden="true" />
            </span>
          )
        })}
        {more > 0 && <span className="text-[10px] font-semibold text-mute">+{more}</span>}
        {kinds.length === 0 && d.prcp != null && d.prcp >= 1 && (
          <span className="whitespace-nowrap text-[10.5px] font-medium text-[#3b82f6] num sm:text-[11.5px]">
            {Math.round(d.prcp)}
            <span className="text-[9px] sm:text-[10.5px]">mm</span>
          </span>
        )}
      </span>
    </button>
  )
}

/** 탭 줄 가운데 7일 기상 예보 띠 (기준일 포함 8칸). 칸을 누르면 그날 예보 모달 */
export function WeatherStrip({ className }: { className?: string }) {
  const { state } = useDash()
  const { data, error } = useWeatherStrip(state.asof)
  const [open, setOpen] = useState<string | null>(null)
  if (error) return null
  const sel = data?.days.find((d) => d.date === open)
  return (
    <div className={clsx('min-w-0', className)} role="group" aria-label="7일 기상 예보">
      <div className="grid w-full max-w-[640px] grid-cols-8 gap-0.5 rounded-2xl border border-line bg-[#fbfbfd] p-1 lg:max-w-[880px]">
        {!data
          ? Array.from({ length: 8 }, (_, i) => <div key={i} className="skeleton h-[118px] rounded-xl sm:h-[126px] lg:h-[82px]" />)
          : data.days.map((d) => <DayCell key={d.date} d={d} selected={open === d.date} onClick={() => setOpen(d.date)} />)}
      </div>
      <WeatherModal asof={state.asof} date={open} hasAlert={(sel?.alerts.length ?? 0) > 0} onClose={() => setOpen(null)} />
    </div>
  )
}
