import { useMemo } from 'react'
import { useForecast } from '../api/hooks'
import { forecastOption } from '../charts/forecastOption'
import { useEChart } from '../charts/useEChart'
import { C } from '../lib/theme'
import { useDash } from '../state/dashboard'
import { ErrorState, Panel, Skeleton } from './ui'

function Swatch({ kind }: { kind: 'history' | 'pred' | 'alert' | 'range' | 'actual' }) {
  if (kind === 'actual') return <span className="h-[3px] w-4 rounded-full" style={{ background: C.navy }} />
  if (kind === 'range')
    return (
      <span
        className="size-3.5 rounded-[4px] border border-[#dcd6fb]"
        style={{
          background:
            'repeating-linear-gradient(135deg, rgba(91,79,224,0.32) 0 1.5px, #f4f2fd 1.5px 5px)',
        }}
      />
    )
  const bg = kind === 'history' ? C.history : kind === 'pred' ? C.brandSoft : C.brandMid
  return <span className="size-3.5 rounded-[4px]" style={{ background: bg }} />
}

export function ForecastPanel({ className }: { className?: string }) {
  const { period, state, agencyName } = useDash()
  const { data, error, refetch, isFetching } = useForecast(period, state.agency)
  const option = useMemo(() => (data ? forecastOption(data) : null), [data])
  const ref = useEChart(option)
  const day = data?.granularity !== 'week'
  const hasActual = data?.series.some((p) => p.kind === 'forecast' && p.actual != null) ?? false
  const hasAlert = data?.series.some((p) => p.alert) ?? false

  return (
    <Panel
      title="예상 접수 추이"
      subtitle={`${agencyName(state.agency)} · ${day ? '일' : '주'} 단위 · 직전 ${day ? '2주' : '8주'} 실적과 선택 기간 예측`}
      evidenceKey="forecast"
      className={className}
    >
      <ul className="mb-3 flex flex-wrap gap-x-4 gap-y-1.5 text-[12px] text-mute">
        <li className="flex items-center gap-1.5">
          <Swatch kind="history" /> 실적
        </li>
        <li className="flex items-center gap-1.5">
          <Swatch kind="pred" /> 예측
        </li>
        {hasAlert && (
          <li className="flex items-center gap-1.5">
            <Swatch kind="alert" /> 기상 특보 예보일
          </li>
        )}
        <li className="flex items-center gap-1.5">
          <Swatch kind="range" /> 80% 범위 상한
        </li>
        {hasActual && (
          <li className="flex items-center gap-1.5">
            <Swatch kind="actual" /> 실제
          </li>
        )}
      </ul>
      <div className={`relative h-[300px] transition-opacity ${isFetching && data ? 'opacity-60' : ''}`}>
        <div ref={ref} className="absolute inset-0" role="img" aria-label="예상 접수 추이 막대 차트" />
        {!data && !error && <Skeleton className="absolute inset-0" />}
        {error && !data && (
          <div className="absolute inset-0 flex items-center">
            <ErrorState error={error} onRetry={() => refetch()} />
          </div>
        )}
      </div>
      {data && <p className="mt-3 text-[12px] leading-relaxed text-faint">{data.range_note}</p>}
    </Panel>
  )
}
