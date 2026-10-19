import clsx from 'clsx'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { useState } from 'react'
import type { RiskOut } from '../api/client'
import { useRisk } from '../api/hooks'
import { fmtInt, fmtMD } from '../lib/format'
import { useDash } from '../state/dashboard'
import { ErrorState, OutlineButton, Panel, Skeleton } from './ui'

type Item = RiskOut['items'][number]
const SHORT = 6
const LONG = 15

/** 위험 확률(또는 경과 비율)을 막대 색으로: 높을수록 빨강 */
const riskColor = (v: number) => (v >= 0.8 ? '#e5484d' : v >= 0.5 ? '#ef8354' : v >= 0.3 ? '#e39b2d' : '#a3a3b5')

export function RiskPanel({ className }: { className?: string }) {
  const { state, agencyName } = useDash()
  const [more, setMore] = useState(false)
  const { data, error, refetch, isFetching } = useRisk(state.asof, state.agency, LONG)
  const counts = data?.counts.filter((c) => state.agency === null || c.agency === state.agency) ?? []
  const over = counts.reduce((s, c) => s + c.over_threshold, 0)
  const high = counts.reduce((s, c) => s + c.high_risk, 0)
  const items = (data?.items ?? []).slice(0, more ? LONG : SHORT)

  return (
    <Panel
      title="지연 위험 민원"
      subtitle={`${agencyName(state.agency)} · 기준일에 처리 중인 민원 중 늦어질 가능성이 큰 순서 (최근 6개월 접수분)`}
      evidenceKey="risk"
      className={className}
    >
      {error && !data ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : !data ? (
        <div className="space-y-2">
          {Array.from({ length: SHORT }, (_, i) => (
            <Skeleton key={i} className="h-[58px]" />
          ))}
        </div>
      ) : (
        <div className={clsx('transition-opacity', isFetching && 'opacity-60')}>
          <div className="mb-3 grid grid-cols-2 gap-2">
            <div className="rounded-2xl bg-page px-4 py-3">
              <p className="text-[12px] text-mute">기준처리기간을 넘긴 민원</p>
              <p className="mt-0.5 text-[20px] font-bold text-ink num">
                {fmtInt(over)}
                <span className="text-[14px] font-semibold text-faint">건</span>
              </p>
            </div>
            <div className="rounded-2xl bg-page px-4 py-3">
              <p className="text-[12px] text-mute">지연 위험 확률 50% 이상</p>
              <p className="mt-0.5 text-[20px] font-bold text-ink num">
                {state.agency === 'DCWP' ? '–' : fmtInt(high)}
                <span className="text-[14px] font-semibold text-faint">{state.agency === 'DCWP' ? '' : '건'}</span>
              </p>
            </div>
          </div>
          {items.length === 0 ? (
            <p className="rounded-xl bg-page px-4 py-6 text-center text-[13px] text-mute">처리 중인 민원이 없습니다.</p>
          ) : (
            <ol className="space-y-1.5">
              {items.map((it, k) => (
                <RiskRow key={it.unique_key} it={it} rank={k + 1} />
              ))}
            </ol>
          )}
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
            <p className="text-[12px] leading-relaxed text-faint">{data.note}</p>
            {data.items.length > SHORT && (
              <OutlineButton className="h-8 px-3 text-[13px]" onClick={() => setMore(!more)}>
                {more ? '접기' : `${data.items.length}건까지 보기`}
                {more ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
              </OutlineButton>
            )}
          </div>
        </div>
      )}
    </Panel>
  )
}

function RiskRow({ it, rank }: { it: Item; rank: number }) {
  const { agencyShort } = useDash()
  const model = it.method === 'model' && it.prob != null
  const v = model ? (it.prob as number) : Math.min(1, it.ratio / 3)
  const color = riskColor(model ? v : it.ratio >= 2 ? 0.8 : it.ratio >= 1 ? 0.5 : 0.2)
  return (
    <li className="grid grid-cols-[22px_minmax(0,1fr)_auto] items-center gap-3 rounded-xl bg-[#f8f8fb] px-3.5 py-2.5">
      <span className="text-center text-[13px] font-bold text-faint num">{rank}</span>
      <div className="min-w-0">
        <p className="flex min-w-0 items-center gap-2 text-[14px]">
          <b className="truncate font-semibold text-ink">{it.type_ko}</b>
          <span className="shrink-0 rounded-md bg-white px-1.5 py-0.5 text-[11px] font-semibold text-mute">
            {agencyShort(it.agency)}
          </span>
        </p>
        <p className="truncate text-[12px] text-mute" title={`${it.complaint_type} · ${it.descriptor} · ${it.factors}`}>
          {it.descriptor} · 접수 {fmtMD(it.created)} · 경과 {Math.round(it.elapsed_days)}일 / 기준 {Math.round(it.threshold_days)}일
        </p>
      </div>
      <div className="w-[118px] text-right">
        <p className="text-[14px] font-bold num" style={{ color }}>
          {model ? `${Math.round(v * 100)}%` : `경과 ${it.ratio.toFixed(1)}배`}
        </p>
        <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white">
          <div className="h-full rounded-full" style={{ width: `${Math.max(4, v * 100)}%`, background: color }} />
        </div>
      </div>
    </li>
  )
}
