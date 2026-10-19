import clsx from 'clsx'
import { CircleCheck, CircleX } from 'lucide-react'
import type { MatrixItem } from '../api/client'
import { useMatrix } from '../api/hooks'
import { useWidth } from '../hooks/useWidth'
import { fmtInt, fmtMult } from '../lib/format'
import { QUADRANT_COLOR, QUADRANTS } from '../lib/theme'
import { useDash } from '../state/dashboard'
import { AgencyIcon, ErrorState, Panel, QuadrantChip, Skeleton, Trend } from './ui'

const order = (q: string) => QUADRANTS.indexOf(q as (typeof QUADRANTS)[number])

/** 패널 폭에 따라 열 구성을 바꿉니다: 넓으면 범위·평소 대비·실제를 각각 열로, 좁으면 한 칸에 두 줄로 */
type Layout = { wide: boolean; actualCol: boolean; cols: string }
function layoutFor(width: number, hasActual: boolean): Layout {
  const wide = width >= 600
  const actualCol = hasActual && width >= 700
  // Tailwind가 클래스를 찾을 수 있도록 전체 이름을 그대로 적습니다.
  const cols = !wide
    ? 'grid-cols-[minmax(0,1.4fr)_minmax(84px,1fr)_56px_minmax(88px,auto)]'
    : actualCol
      ? 'grid-cols-[minmax(0,1.5fr)_minmax(96px,1fr)_70px_60px_minmax(92px,auto)_88px]'
      : 'grid-cols-[minmax(0,1.5fr)_minmax(96px,1fr)_70px_60px_minmax(92px,auto)]'
  return { wide, actualCol, cols }
}

export function DeptPanel({ className }: { className?: string }) {
  const { period, state, meta, toggleAgency } = useDash()
  const { data, error, refetch, isFetching } = useMatrix(period)
  const [box, width] = useWidth<HTMLDivElement>(640)
  const items = [...(data?.items ?? [])].sort((a, b) => order(a.quadrant) - order(b.quadrant) || b.x - a.x)
  const total = items.reduce((s, i) => s + i.pred, 0)
  const hasActual = data?.period.has_actual ?? false
  const desc = new Map(meta.agencies.map((a) => [a.code, a.desc]))
  const lay = layoutFor(width, hasActual)

  return (
    <Panel
      title="부서별 현황"
      subtitle="선택 기간 부서별 예상 접수와 판정 · 위험한 부서부터 · 행을 누르면 그 부서로 화면이 바뀝니다"
      evidenceKey="forecast"
      className={className}
    >
      <div ref={box}>
        {error && !data ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : !data ? (
          <div className="space-y-2">
            {Array.from({ length: 8 }, (_, i) => (
              <Skeleton key={i} className="h-[52px]" />
            ))}
          </div>
        ) : (
          <div className={clsx('transition-opacity', isFetching && 'opacity-60')}>
            <div className={clsx('grid gap-3 px-4 pb-2 text-[12px] font-medium text-faint', lay.cols)}>
              <span>부서 (예상 비중)</span>
              <span className="text-right">{lay.wide ? '예상 접수 · 80% 범위' : '예상 접수 · 평소 대비'}</span>
              {lay.wide && <span className="text-right">평소 대비</span>}
              <span className="text-right">적체</span>
              <span className="text-right">판정</span>
              {lay.actualCol && <span className="text-right">실제</span>}
            </div>
            <ul className="space-y-1.5">
              {items.map((it) => (
                <Row
                  key={it.agency}
                  it={it}
                  lay={lay}
                  share={total > 0 ? it.pred / total : 0}
                  desc={desc.get(it.agency) ?? ''}
                  selected={state.agency === it.agency}
                  hasActual={hasActual}
                  onClick={() => toggleAgency(it.agency)}
                />
              ))}
            </ul>
          </div>
        )}
      </div>
    </Panel>
  )
}

function InRange({ it }: { it: MatrixItem }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 text-[11px] font-semibold',
        it.in_range ? 'text-[#17955a]' : 'text-[#c2362d]',
      )}
    >
      {it.in_range ? <CircleCheck size={12} /> : <CircleX size={12} />}
      {it.in_range ? '범위 안' : '범위 밖'}
    </span>
  )
}

function Row({
  it,
  lay,
  share,
  desc,
  selected,
  hasActual,
  onClick,
}: {
  it: MatrixItem
  lay: Layout
  share: number
  desc: string
  selected: boolean
  hasActual: boolean
  onClick: () => void
}) {
  const actualText = hasActual ? `실제 ${fmtInt(it.actual)}건 · ${it.in_range ? '80% 범위 안' : '80% 범위 밖'}` : ''
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        aria-pressed={selected}
        title={`${it.name} · 예상 ${fmtInt(it.pred)}건 (80% 범위 ${fmtInt(it.lo)}~${fmtInt(it.hi)}) · 평소 ${fmtInt(it.base)}건${actualText ? ` · ${actualText}` : ''}`}
        className={clsx(
          'grid w-full items-center gap-3 rounded-xl px-4 py-2.5 text-left text-[14px] transition',
          lay.cols,
          selected ? 'bg-brand-tint ring-1 ring-brand/30' : 'bg-[#f8f8fb] hover:bg-[#f2f2f7]',
        )}
      >
        <span className="flex min-w-0 items-center gap-2.5">
          <span className="h-7 w-1 shrink-0 rounded-full" style={{ background: QUADRANT_COLOR[it.quadrant] }} />
          <AgencyIcon code={it.agency} size={17} className="shrink-0 text-mute" />
          <span className="min-w-0">
            <span className="flex min-w-0 items-baseline gap-1.5">
              <b className="truncate font-semibold text-ink">{it.name}</b>
              <span className="shrink-0 text-[12px] text-faint num">{Math.round(share * 100)}%</span>
            </span>
            <span className="block truncate text-[12px] text-mute">{desc}</span>
          </span>
        </span>
        <span className="text-right num">
          <b className="font-bold text-ink">{fmtInt(it.pred)}</b>
          <span className="text-mute">건</span>
          {lay.wide ? (
            <span className="block text-[12px] text-faint">
              {fmtInt(it.lo)} ~ {fmtInt(it.hi)}
            </span>
          ) : (
            <span className="flex items-center justify-end gap-1.5">
              <Trend value={it.x} className="text-[12px]" />
            </span>
          )}
        </span>
        {lay.wide && (
          <span className="text-right">
            <Trend value={it.x} />
          </span>
        )}
        <span className={clsx('text-right font-semibold num', it.y >= 1.3 ? 'text-[#b77412]' : 'text-ink')}>
          {fmtMult(it.y, 2)}
        </span>
        <span className="flex flex-col items-end gap-1">
          <QuadrantChip q={it.quadrant} />
          {it.flag && <span className="text-right text-[11px] font-semibold text-[#c2362d]">{it.flag_reason}</span>}
          {hasActual && !lay.actualCol && <InRange it={it} />}
        </span>
        {lay.actualCol && (
          <span className="text-right num">
            <b className="font-semibold text-ink">{fmtInt(it.actual)}</b>
            <span className="text-mute">건</span>
            <span className="mt-0.5 flex justify-end">
              <InRange it={it} />
            </span>
          </span>
        )}
      </button>
    </li>
  )
}
