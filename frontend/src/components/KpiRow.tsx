import clsx from 'clsx'
import { useSummary } from '../api/hooks'
import { buildKpis, type ChipTone } from '../lib/kpi'
import { useDash } from '../state/dashboard'
import { Chip, ErrorState, Skeleton, Trend } from './ui'

const CHIP: Record<ChipTone, string> = {
  danger: 'bg-[#fdecea] text-[#c2362d]',
  warning: 'bg-[#fdf3e2] text-[#a35a07]',
  ok: 'bg-[#e5f5ed] text-[#17955a]',
  muted: 'bg-[#efeff4] text-[#55556a]',
}

const cell = 'min-w-0 border-line px-5 py-6 lg:px-8 max-xl:border-b xl:border-l xl:first:border-l-0'

export function KpiRow() {
  const { period, state, days } = useDash()
  const { data, error, refetch, isFetching } = useSummary(period, state.agency, state.ppd)

  return (
    <div className="mx-auto max-w-[1680px] px-0 lg:px-2">
      <div
        className={clsx('grid grid-cols-2 transition-opacity md:grid-cols-3 xl:grid-cols-5', isFetching && data && 'opacity-70')}
        aria-busy={isFetching}
      >
        {error && !data ? (
          <div className="col-span-full px-5 py-6 lg:px-8">
            <ErrorState error={error} onRetry={() => refetch()} />
          </div>
        ) : !data ? (
          Array.from({ length: 5 }, (_, i) => (
            <div key={i} className={cell}>
              <Skeleton className="h-4 w-24" />
              <Skeleton className="mt-5 h-9 w-32" />
              <Skeleton className="mt-4 h-4 w-40" />
            </div>
          ))
        ) : (
          buildKpis(data, { days, ppd: state.ppd, agencySelected: state.agency !== null }).map((k) => (
            <div key={k.key} className={cell}>
              <p className="text-[15px] font-medium text-ink/80">{k.label}</p>
              <p className="mt-3.5 flex items-baseline gap-1">
                <span
                  className="truncate text-[32px] font-bold tracking-[-0.025em] num lg:text-[34px]"
                  style={{ color: k.valueColor ?? '#16161d' }}
                >
                  {k.value}
                </span>
                {k.unit && <span className="text-[22px] font-semibold text-faint">{k.unit}</span>}
              </p>
              <div className="mt-2.5 flex min-h-6 flex-wrap items-center gap-x-2.5 gap-y-1 text-[14px] text-mute">
                {k.note && <span className="truncate">{k.note}</span>}
                {k.trend !== undefined && <Trend value={k.trend} />}
                {k.chip && <Chip className={CHIP[k.chip.tone]}>{k.chip.text}</Chip>}
              </div>
              <p className="mt-1 text-[12px] leading-snug text-faint">{k.sub}</p>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
