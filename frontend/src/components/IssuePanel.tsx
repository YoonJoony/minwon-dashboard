import { ArrowRight, ChevronLeft, ChevronRight, Siren, Sparkles, TriangleAlert } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import type { IssueCard, IssuesOut } from '../api/client'
import { useIssues } from '../api/hooks'
import { fmtInt, fmtMD, fmtMDW } from '../lib/format'
import { TONE, toneOf } from '../lib/theme'
import { useWidth } from '../hooks/useWidth'
import { useDash } from '../state/dashboard'
import { ALERT_ICON, ISSUE_ICON } from './icons'
import { Drawer, ErrorState, IconButton, OutlineButton, Panel, Skeleton } from './ui'

/** 패널 폭에 따라 한 번에 보여 줄 카드 수 */
const perPageFor = (w: number) => (w >= 600 ? 3 : w >= 380 ? 2 : 1)
const COLS = { 1: 'grid-cols-1', 2: 'grid-cols-2', 3: 'grid-cols-3' } as const
const SPAN = { 1: '', 2: 'col-span-2', 3: 'col-span-3' } as const

export function IssuePanel({ className }: { className?: string }) {
  const { period, state, openEvidence } = useDash()
  const { data, error, refetch, isFetching } = useIssues(period, state.agency)
  const [box, width] = useWidth<HTMLDivElement>(640)
  const PER_PAGE = perPageFor(width)
  const [page, setPage] = useState(0)
  const [drawer, setDrawer] = useState(false)
  const cards = data?.cards ?? []
  const start = Math.min(page, Math.max(0, cards.length - PER_PAGE))
  const visible = cards.slice(start, start + PER_PAGE)

  return (
    <Panel
      title="예상 이슈"
      subtitle="단기: 기준일에 발표된 기상 특보 예보 · 장기: 같은 시기 과거 급증 빈도와 겨울 적설"
      className={className}
      actions={
        <>
          <IconButton label="이전 이슈" disabled={start === 0} onClick={() => setPage(Math.max(0, start - 1))}>
            <ChevronLeft size={18} />
          </IconButton>
          <IconButton
            label="다음 이슈"
            disabled={start + PER_PAGE >= cards.length}
            onClick={() => setPage(Math.min(cards.length - PER_PAGE, start + 1))}
          >
            <ChevronRight size={18} />
          </IconButton>
          <OutlineButton onClick={() => setDrawer(true)} disabled={!data}>
            전체 보기
          </OutlineButton>
        </>
      }
    >
      <div ref={box}>
        {error && !data ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : !data ? (
          <div className={`grid gap-3 ${COLS[PER_PAGE]}`}>
            {Array.from({ length: PER_PAGE }, (_, i) => (
              <Skeleton key={i} className="h-[226px]" />
            ))}
          </div>
        ) : (
          <div className={isFetching ? 'opacity-60 transition-opacity' : 'transition-opacity'}>
            <div className={`grid gap-3 ${COLS[PER_PAGE]}`}>
              {visible.map((c, i) => (
                <IssueCardView key={`${c.kind}-${c.title}-${start + i}`} c={c} />
              ))}
              {visible.length < PER_PAGE && (
                <OutlookMini data={data} span={(PER_PAGE - visible.length) as 1 | 2 | 3} />
              )}
            </div>
            {cards.length > PER_PAGE && (
              <p className="mt-2 text-right text-[12px] text-faint num">
                {start + 1}–{Math.min(start + PER_PAGE, cards.length)} / {cards.length}
              </p>
            )}
            <Headline data={data} onEvidence={() => openEvidence('alerts')} />
            {data.actual_surges.length > 0 && (
              <div className="mt-3 flex flex-wrap items-center gap-2 text-[12px]">
                <span className="font-semibold text-ink">실제로 급증한 이슈</span>
                {data.actual_surges.map((s) => (
                  <span key={s.issue} className="rounded-lg bg-page px-2 py-1 text-mute">
                    <b className="font-semibold text-ink">{s.issue}</b> {fmtMD(s.date)} {fmtInt(s.count)}건
                    <span className="text-faint"> (평소 {fmtInt(s.normal)}건)</span>
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
      <IssueDrawer open={drawer} onClose={() => setDrawer(false)} data={data} />
    </Panel>
  )
}

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <dt className="shrink-0 text-mute">{label}</dt>
      <dd className="truncate text-right font-semibold text-ink num">{value}</dd>
    </div>
  )
}

function IssueCardView({ c }: { c: IssueCard }) {
  const { agencyName } = useDash()
  const Icon = ISSUE_ICON[c.icon] ?? Sparkles
  const t = TONE[toneOf(c.tone)]
  return (
    <article className="flex min-w-0 flex-col rounded-2xl border border-line bg-white p-4">
      <div className="flex items-center gap-3">
        <span
          className="flex size-12 shrink-0 items-center justify-center rounded-xl"
          style={{ background: t.bg, color: t.icon }}
        >
          <Icon size={22} strokeWidth={1.9} />
        </span>
        <div className="min-w-0">
          <p className="truncate text-[16px] font-semibold text-ink">{c.title}</p>
          <p className="truncate text-[13px] text-mute">{agencyName(c.agency)}</p>
        </div>
      </div>
      <div className="my-3.5 h-px bg-line" />
      <dl className="space-y-2.5 text-[14px]">
        <Row label="시기" value={c.when} />
        <Row label="구분" value={c.tag} />
        <Row
          label={c.metric_label}
          value={
            <span className="text-[16px] font-bold" style={{ color: t.fg }}>
              {c.metric}
            </span>
          }
        />
      </dl>
      <p className="mt-3 text-[12px] leading-snug text-faint">{c.basis}</p>
    </article>
  )
}

/** 카드가 3장보다 적을 때 남는 칸: 같은 시기 과거 급증 빈도 상위 이슈 */
function OutlookMini({ data, span }: { data: IssuesOut; span: 1 | 2 | 3 }) {
  const { agencyName } = useDash()
  const shown = new Set(data.cards.filter((c) => c.kind === 'outlook').map((c) => c.title.replace(/ 급증$/, '')))
  const rest = data.outlook.filter((o) => !shown.has(o.issue)).slice(0, span === 3 ? 5 : span === 2 ? 4 : 3)
  return (
    <div className={SPAN[span]} aria-label="같은 시기 과거 급증 빈도">
      <div className="flex h-full min-h-[226px] flex-col rounded-2xl border border-dashed border-line-strong p-4">
        <p className="text-[14px] font-semibold text-ink">
          {data.cards.length === 0 ? '예상되는 특이 이슈가 없습니다' : '그 밖의 이슈'}
        </p>
        <p className="mt-0.5 text-[12px] leading-snug text-mute">
          {span === 1
            ? '같은 시기 과거 급증 빈도'
            : '같은 시기 과거 급증 빈도 · 기간이 속한 달에 평소의 1.5배 이상이던 해의 비율'}
        </p>
        <ul className="mt-3 flex-1 space-y-2.5">
          {rest.map((o) => (
            <li key={o.issue} className="text-[13px]">
              <div className="flex items-center justify-between gap-3">
                <span className="truncate">
                  <b className="font-semibold text-ink">{o.issue}</b>
                  {span > 1 && <span className="text-mute"> {agencyName(o.agency)}</span>}
                </span>
                <span className="shrink-0 font-semibold text-ink num">
                  {Math.round(o.prob * 100)}%
                  {span > 1 && <span className="font-normal text-faint"> · {o.total}년 중 {o.surged}년</span>}
                </span>
              </div>
              <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-page">
                <div className="h-full rounded-full bg-brand-soft" style={{ width: `${Math.max(2, o.prob * 100)}%` }} />
              </div>
            </li>
          ))}
          {rest.length === 0 && <li className="text-[13px] text-mute">추가로 볼 이슈가 없습니다.</li>}
        </ul>
      </div>
    </div>
  )
}

function Headline({ data, onEvidence }: { data: IssuesOut; onEvidence: () => void }) {
  const h = data.headline
  const tone = toneOf(h.tone)
  const t = TONE[tone]
  const Icon = tone === 'danger' ? Siren : tone === 'warning' ? TriangleAlert : Sparkles
  return (
    <div
      className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-2xl border px-4 py-3.5"
      style={{ background: t.bg, borderColor: t.border }}
    >
      <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-white" style={{ color: t.icon }}>
        <Icon size={20} />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-[15px] font-semibold text-ink">{h.title}</p>
        <p className="mt-0.5 text-[13px] text-mute">{h.detail}</p>
      </div>
      <button
        type="button"
        onClick={onEvidence}
        className="inline-flex items-center gap-1.5 text-[14px] font-semibold hover:underline"
        style={{ color: t.fg }}
      >
        근거 보기 <ArrowRight size={16} />
      </button>
    </div>
  )
}

function IssueDrawer({ open, onClose, data }: { open: boolean; onClose: () => void; data?: IssuesOut }) {
  const { agencyName } = useDash()
  if (!data) return null
  const months = [...new Set(data.outlook.flatMap((o) => o.months))]
  return (
    <Drawer
      open={open}
      onClose={onClose}
      title="예상 이슈 전체"
      subtitle={`기준일 ${data.period.asof} · 기간 ${data.period.start} ~ ${data.period.end}`}
      width={620}
    >
      <h3 className="text-[15px] font-semibold text-ink">기상 특보 (관측·예보)</h3>
      <p className="mt-1 text-[12px] text-mute">미국 기상청 뉴욕 지청 기준. 예보는 기준일에 발표된 값만 씁니다.</p>
      {data.alerts.length === 0 ? (
        <p className="mt-3 rounded-xl bg-page px-4 py-3 text-[13px] text-mute">선택 기간에 특보 수준 날씨가 없습니다.</p>
      ) : (
        <ul className="mt-3 divide-y divide-line rounded-2xl border border-line">
          {data.alerts.map((a) => {
            const Icon = ALERT_ICON[a.type] ?? Siren
            const danger = a.level === 2
            return (
              <li key={`${a.type}${a.date}${a.source}`} className="flex gap-3 px-4 py-3 text-[13px]">
                <span
                  className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg"
                  style={{ background: danger ? '#fdf0ef' : '#fdf5e8', color: danger ? '#e0483f' : '#d97706' }}
                >
                  <Icon size={16} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center justify-between gap-2">
                    <b className="font-semibold text-ink">
                      {a.level_label} · {fmtMDW(a.date)}
                    </b>
                    <span className="rounded-md bg-page px-1.5 py-0.5 text-[11px] font-semibold text-mute">
                      {a.source === '관측' ? '관측' : `${a.lead_days}일 전 예보`}
                    </span>
                  </p>
                  <p className="mt-0.5 text-mute">{a.value}</p>
                  <p className="mt-0.5 text-mute">
                    {a.agencies.map((g) => agencyName(g)).join(', ')} · {a.issues.join(', ')} · 과거 민원 급증{' '}
                    {Math.round(a.hit_rate * 100)}% · 신뢰도 {a.confidence}
                  </p>
                </div>
              </li>
            )
          })}
        </ul>
      )}

      {data.pothole && (
        <>
          <h3 className="mt-7 text-[15px] font-semibold text-ink">겨울 적설 → 봄철 도로 파손</h3>
          <div className="mt-3 grid grid-cols-3 gap-2 text-center">
            <Stat label="지난겨울 적설" value={`${data.pothole.snow_cm.toFixed(1)}cm`} />
            <Stat label="예상 배수 (3~4월)" value={`${data.pothole.mult.toFixed(1)}배`} />
            <Stat
              label="실제 배수"
              value={data.pothole.actual_mult != null ? `${data.pothole.actual_mult.toFixed(1)}배` : '집계 전'}
            />
          </div>
          <p className="mt-2 text-[12px] text-mute">
            과거 {data.pothole.n_winters}개 겨울의 적설과 봄철 도로 파손 배수 관계로 추정. 방향은 확실하나 크기는 작게 잡히는 경향이 있습니다.
          </p>
        </>
      )}

      <h3 className="mt-7 text-[15px] font-semibold text-ink">같은 시기 과거 급증 빈도</h3>
      <p className="mt-1 text-[12px] text-mute">
        {months.length ? `${months.sort((a, b) => a - b).join('·')}월` : '선택 기간'}에 이슈가 평소(직전 12개월 평균)의 1.5배 이상으로 늘었던 해의 비율
      </p>
      <ul className="mt-3 space-y-2">
        {data.outlook.map((o) => (
          <li key={o.issue} className="rounded-xl bg-page px-4 py-2.5 text-[13px]">
            <div className="flex items-center justify-between gap-3">
              <span>
                <b className="font-semibold text-ink">{o.issue}</b> <span className="text-mute">{agencyName(o.agency)}</span>
              </span>
              <span className="font-semibold text-ink num">
                {Math.round(o.prob * 100)}% <span className="font-normal text-faint">({o.total}년 중 {o.surged}년)</span>
              </span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white">
              <div className="h-full rounded-full bg-brand" style={{ width: `${Math.max(2, o.prob * 100)}%`, opacity: 0.35 + o.prob * 0.65 }} />
            </div>
          </li>
        ))}
      </ul>

      {data.actual_surges.length > 0 && (
        <>
          <h3 className="mt-7 text-[15px] font-semibold text-ink">실제로 급증한 이슈 (기간 지난 경우)</h3>
          <ul className="mt-3 space-y-1.5 text-[13px]">
            {data.actual_surges.map((s) => (
              <li key={s.issue} className="flex justify-between rounded-xl bg-page px-4 py-2">
                <span className="font-semibold text-ink">{s.issue}</span>
                <span className="text-mute num">
                  {fmtMDW(s.date)} {fmtInt(s.count)}건 (평소 {fmtInt(s.normal)}건)
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </Drawer>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-page px-3 py-3">
      <p className="text-[12px] text-mute">{label}</p>
      <p className="mt-1 text-[17px] font-bold text-ink num">{value}</p>
    </div>
  )
}
