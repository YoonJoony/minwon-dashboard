import { useCallback, useMemo } from 'react'
import { useMatrix } from '../api/hooks'
import { MATRIX_HEIGHT, matrixOption } from '../charts/matrixOption'
import { useEChart, type EClick } from '../charts/useEChart'
import { QUADRANT_COLOR, QUADRANT_DESC, QUADRANTS } from '../lib/theme'
import { useWidth } from '../hooks/useWidth'
import { useDash } from '../state/dashboard'
import { ErrorState, Panel, Skeleton } from './ui'

export function MatrixPanel({ className }: { className?: string }) {
  const { period, state, toggleAgency } = useDash()
  const { data, error, refetch, isFetching } = useMatrix(period)
  // 이름표 자리 계산에 차트 폭이 필요합니다.
  const [box, width] = useWidth<HTMLDivElement>(640)
  const option = useMemo(
    () => (data ? matrixOption(data, state.agency, Math.max(320, width)) : null),
    [data, state.agency, width],
  )
  const items = data?.items
  const onClick = useCallback<EClick>(
    (p) => {
      if (p.seriesName === '부서' && items?.[p.dataIndex]) toggleAgency(items[p.dataIndex].agency)
    },
    [items, toggleAgency],
  )
  const ref = useEChart(option, onClick)
  const hasActual = data?.period.has_actual ?? false
  const hit = data && hasActual ? data.items.filter((i) => i.in_range).length : 0

  return (
    <Panel
      title="부서 위험 매트릭스"
      subtitle="가로: 접수 증가율 · 세로: 적체 배수 · 원 크기: 처리 중 민원 · 가로 막대: 80% 예측 범위"
      evidenceKey="matrix"
      className={className}
    >
      <div
        ref={box}
        className={`relative transition-opacity ${isFetching && data ? 'opacity-60' : ''}`}
        style={{ height: MATRIX_HEIGHT }}
      >
        <div ref={ref} className="absolute inset-0" role="img" aria-label="부서 위험 매트릭스 산점도" />
        {!data && !error && <Skeleton className="absolute inset-0" />}
        {error && !data && (
          <div className="absolute inset-0 flex items-center">
            <ErrorState error={error} onRetry={() => refetch()} />
          </div>
        )}
      </div>
      {data && (
        <>
          <ul className="mt-4 flex flex-wrap gap-2">
            {QUADRANTS.map((q) => (
              <li
                key={q}
                className="flex items-center gap-2 rounded-xl bg-page px-3 py-2 text-[13px]"
                title={QUADRANT_DESC[q]}
              >
                <span className="size-2.5 rounded-full" style={{ background: QUADRANT_COLOR[q] }} />
                <span className="text-ink">{q}</span>
                <b className="font-bold text-ink num">{data.counts[q] ?? 0}</b>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-[12px] leading-relaxed text-faint">
            기준: 접수 증가율 +{Math.round(data.thresholds.x * 100)}%, 적체 배수 {data.thresholds.y}배 · 지원 가능은 접수
            증가율 {Math.round(data.thresholds.support_x * 100)}% 이하이면서 적체가 기준 미만인 부서 · 점선 테두리는 기상
            특보·봄철 도로 파손 영향 부서로, 범위를 넓히고 지원 후보에서 뺍니다.
            {hasActual && ` × 표시는 실제 결과 (8개 부서 중 ${hit}곳이 80% 범위 안).`} 원을 누르면 그 부서로 화면이 바뀝니다.
          </p>
        </>
      )}
    </Panel>
  )
}
