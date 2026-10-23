import clsx from 'clsx'
import { useState } from 'react'
import type { PastYear, WeatherDay, WeatherDayOut, WeatherHistory } from '../api/client'
import { useWeatherDay } from '../api/hooks'
import { fmtInt, fmtMD, fmtYMDW } from '../lib/format'
import { fmtBase, fmtExcess } from '../lib/weather'
import { LEVEL_TONE, SKY_ICON, WX_ALERT_ICON } from './icons'
import { ErrorState, Modal, Skeleton } from './ui'

/** 예보 띠에서 고른 날의 예보(지난 7일은 실제 관측). 그날 특보가 있으면 같은 특보의 과거 7년 실제 민원 접수·처리 표를 함께 */
export function WeatherModal({
  asof,
  date,
  hasAlert,
  onClose,
}: {
  asof: string
  date: string | null
  hasAlert: boolean
  onClose: () => void
}) {
  const { data, error, refetch } = useWeatherDay(asof, date)
  const ready = data && data.day.date === date
  const title = date ? `${fmtYMDW(date)} ${date < asof ? '관측 날씨' : '기상 예보'}` : ''
  return (
    <Modal open={date !== null} onClose={onClose} title={title} width={hasAlert ? 1000 : 560}>
      {error && !ready ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : !ready ? (
        <div className="space-y-3">
          <Skeleton className="h-24" />
          {hasAlert && <Skeleton className="h-10" />}
          {hasAlert && <Skeleton className="h-72" />}
        </div>
      ) : (
        <Body key={data.day.date} data={data} />
      )}
    </Modal>
  )
}

function Body({ data }: { data: WeatherDayOut }) {
  const [tab, setTab] = useState(0)
  // 특보 없는 날은 과거 7년 표 없이 그날 예보(관측)만
  if (!data.tabs.length) return <DaySummary d={data.day} />
  const h = data.tabs[Math.min(tab, data.tabs.length - 1)]
  return (
    <div>
      <DaySummary d={data.day} />
      <h3 className="mt-6 text-[15px] font-semibold text-ink">과거 7년 같은 특보 때 민원</h3>
      <div className="mt-3 flex flex-wrap gap-1.5" role="tablist" aria-label="기상 이슈">
        {data.tabs.map((t, i) => {
          const Icon = WX_ALERT_ICON[t.kind]
          const on = i === tab
          return (
            <button
              key={t.kind}
              type="button"
              role="tab"
              aria-selected={on}
              onClick={() => setTab(i)}
              className={clsx(
                'inline-flex h-10 items-center gap-2 rounded-xl px-3.5 text-[14px] font-semibold transition',
                on ? 'bg-ink text-white' : 'border border-line bg-white text-ink hover:border-line-strong',
              )}
            >
              <Icon size={16} aria-hidden="true" />
              {t.kind_label}
            </button>
          )
        })}
      </div>
      <History key={h.kind} h={h} />
      <p className="mt-4 text-[12px] leading-relaxed text-faint">{data.note}</p>
    </div>
  )
}

function DaySummary({ d }: { d: WeatherDay }) {
  const sky = d.icon ? SKY_ICON[d.icon] : null
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-3 rounded-2xl border border-line p-4">
      <div className="flex items-center gap-3">
        <span className="flex size-14 items-center justify-center rounded-2xl bg-page">
          {sky && <sky.icon size={30} color={sky.color} strokeWidth={1.8} aria-hidden="true" />}
        </span>
        <div>
          <p className="text-[16px] font-semibold text-ink">
            {d.icon_label ?? '정보 없음'}{' '}
            <span className="num">
              {d.tmax != null ? Math.round(d.tmax) : '–'}° / {d.tmin != null ? Math.round(d.tmin) : '–'}°
            </span>
          </p>
          <p className="text-[12px] text-mute num">
            {d.prcp != null && `강수 ${Math.round(d.prcp)}mm`}
            {d.snow != null && d.snow >= 1 && ` · 적설 ${Math.round(d.snow)}cm`}
            {d.gust != null && ` · 최대 돌풍 ${Math.round(d.gust)}km/h`}
          </p>
          <p className="mt-0.5 text-[12px] text-faint">
            {d.offset < 0 ? '실제 관측 (Open-Meteo 관측 기록)' : `${d.offset === 0 ? '전날' : '기준일'} 발표 예보 (${d.lead}일 전)`}
          </p>
        </div>
      </div>
      <ul className="flex min-w-0 flex-[1_1_160px] flex-wrap gap-2">
        {d.alerts.length === 0 && <li className="rounded-xl bg-page px-3 py-1.5 text-[13px] text-mute">특보 없음</li>}
        {d.alerts.map((a, i) => {
          const Icon = WX_ALERT_ICON[a.kind]
          const tone = LEVEL_TONE[a.level] ?? LEVEL_TONE[1]
          return (
            <li
              key={`${a.label}${i}`}
              className="inline-flex flex-wrap items-center gap-x-2 gap-y-0.5 rounded-xl px-3 py-1.5 text-[13px]"
              style={{ background: tone.bg, color: tone.fg }}
            >
              <Icon size={15} color={tone.icon} aria-hidden="true" />
              <b className="font-semibold">{a.label}</b>
              <span className="text-[12px] opacity-80">
                {a.source === 'NWS' ? `NWS 발표 ${a.issued ?? ''}` : `${a.source} 판정`}
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

const ISSUE_SHORT: Record<string, string> = {
  '폭염·소화전': '소화전',
  수돗물: '수돗물',
  '결빙·제설': '제설·결빙',
  '강풍·수목': '수목 피해',
  '폭우·침수': '하수 역류·침수',
}

function History({ h }: { h: WeatherHistory }) {
  const [issue, setIssue] = useState(0)
  const Icon = WX_ALERT_ICON[h.kind]
  const rate = h.total_events ? Math.round((h.surged_events / h.total_events) * 100) : null
  return (
    <section className="mt-4" aria-label={`${h.kind_label} 과거 7년`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-[13px] text-mute">
          <p>
            <b className="font-semibold text-ink">대상 민원</b> {h.issues.map((i) => ISSUE_SHORT[i] ?? i).join(' · ')} ·{' '}
            {h.window_rule}
          </p>
          <p className="mt-0.5 text-[12px] text-faint">
            사건 기준: {h.basis}
            {rate !== null && ` · 2016년 이후 ${h.total_events}회 중 ${h.surged_events}회(${rate}%) 민원 급증`}
          </p>
        </div>
        {h.issues.length > 1 && (
          <div className="inline-flex rounded-xl border border-line bg-page p-0.5" role="group" aria-label="대상 민원">
            {h.issues.map((name, i) => (
              <button
                key={name}
                type="button"
                aria-pressed={i === issue}
                onClick={() => setIssue(i)}
                className={clsx(
                  'h-8 rounded-lg px-3 text-[13px] font-semibold',
                  i === issue ? 'bg-white text-ink shadow-sm' : 'text-mute hover:text-ink',
                )}
              >
                {ISSUE_SHORT[name] ?? name}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[860px] border-separate border-spacing-y-1.5 text-[13px]">
          <thead>
            <tr className="text-left text-[12px] text-faint">
              <th className="px-3 font-medium">해</th>
              <th className="px-3 font-medium">사건 (날씨)</th>
              <th className="px-3 font-medium">영향 기간</th>
              <th className="px-3 text-right font-medium">평소 (하루)</th>
              <th className="px-3 text-right font-medium">접수</th>
              <th className="px-3 text-right font-medium">늘어난 건수</th>
              <th className="px-3 text-right font-medium">영향 기간 내 처리</th>
              <th className="px-3 text-right font-medium">미처리 (끝)</th>
              <th className="px-3 text-right font-medium">미처리 (+7일)</th>
            </tr>
          </thead>
          <tbody>
            {h.years.map((y) => (
              <YearRow key={y.year} y={y} issue={issue} Icon={Icon} kindLabel={h.kind_label} />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function YearRow({
  y,
  issue,
  Icon,
  kindLabel,
}: {
  y: PastYear
  issue: number
  Icon: (typeof WX_ALERT_ICON)[string]
  kindLabel: string
}) {
  const cell = 'bg-[#f8f8fb] px-3 py-2.5 first:rounded-l-xl last:rounded-r-xl'
  if (!y.event) {
    return (
      <tr>
        <td className={cell}>
          <b className="font-semibold text-ink num">{y.year}</b>
        </td>
        <td className={clsx(cell, 'text-mute')} colSpan={8}>
          같은 시기(앞뒤 4개월)에 {kindLabel} 사건 없음
        </td>
      </tr>
    )
  }
  const e = y.event
  const it = e.issues[Math.min(issue, e.issues.length - 1)]
  const tone = LEVEL_TONE[e.level] ?? LEVEL_TONE[1]
  return (
    <tr>
      <td className={cell}>
        <b className="font-semibold text-ink num">{y.year}</b>
        <span className="block whitespace-nowrap text-[11px] text-faint">같은 시기 {y.count}회</span>
      </td>
      <td className={cell}>
        <span className="flex items-center gap-2">
          <span className="flex size-7 shrink-0 items-center justify-center rounded-lg" style={{ background: tone.bg }}>
            <Icon size={15} color={tone.icon} aria-hidden="true" />
          </span>
          <span>
            <span className="whitespace-nowrap font-semibold text-ink num">
              {/* 겨울처럼 해를 넘는 시기는 사건 연도를 함께 */}
              {Number(e.start.slice(0, 4)) !== y.year && `${e.start.slice(0, 4)}. `}
              {fmtMD(e.start)}
              {e.end !== e.start && `~${fmtMD(e.end)}`}
            </span>{' '}
            <span className="whitespace-nowrap text-[12px] font-semibold" style={{ color: tone.fg }}>
              {e.level_label}
            </span>
            <span className="block text-[11px] text-faint">
              {e.nws.length ? `NWS: ${e.nws.join(', ')}` : 'NWS 특보 없음'}
            </span>
          </span>
        </span>
      </td>
      <td className={clsx(cell, 'num')}>
        {fmtMD(e.win_start)}~{fmtMD(e.win_end)} <span className="text-faint">({e.days}일)</span>
        <span
          className={clsx(
            'mt-0.5 block w-fit rounded-md px-1.5 text-[11px] font-semibold',
            it.surge ? 'bg-[#fdf0ef] text-[#c2362d]' : 'bg-white text-faint',
          )}
        >
          {it.surge ? '민원 급증' : '급증 없음'}
        </span>
      </td>
      <td className={clsx(cell, 'text-right num')}>{fmtBase(it.base)}건</td>
      <td className={clsx(cell, 'text-right num')}>
        <b className="font-semibold text-ink">{fmtInt(it.received)}</b>
        <span className="block text-[11px] text-faint">최대 하루 {fmtInt(it.peak)}</span>
      </td>
      <td className={clsx(cell, 'text-right font-semibold num', it.excess > 0.5 ? 'text-up' : 'text-faint')}>
        {fmtExcess(it.excess)}
      </td>
      <td className={clsx(cell, 'text-right num')}>{fmtInt(it.processed)}</td>
      <td className={clsx(cell, 'text-right num')}>{fmtInt(it.open_end)}</td>
      <td className={clsx(cell, 'text-right num')}>{it.open_7 == null ? '집계 전' : fmtInt(it.open_7)}</td>
    </tr>
  )
}
