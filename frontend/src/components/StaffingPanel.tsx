import { ArrowLeft, ChevronLeft, ChevronRight, CircleCheck, TriangleAlert, Users } from 'lucide-react'
import { useState } from 'react'
import type { StaffingOut } from '../api/client'
import { useMatrix, useStaffing } from '../api/hooks'
import { fmtInt, fmtPct, peopleText } from '../lib/format'
import { QUADRANT_COLOR, QUADRANT_TINT } from '../lib/theme'
import { useDash } from '../state/dashboard'
import { PpdStepper } from './Controls'
import { AgencyTile, Chip, DashedProgress, ErrorState, FlagChip, IconButton, Panel, QuadrantChip, Skeleton } from './ui'

export function StaffingPanel({ className }: { className?: string }) {
  const { period, state } = useDash()
  const { data, error, refetch, isFetching } = useStaffing(period, state.ppd)
  const { data: mx } = useMatrix(period)
  // 접수는 줄지만 기상 특보 영향이라 지원 후보에서 뺀 부서 (매트릭스에서는 '안정'으로 표시)
  const excluded =
    mx?.items.filter((m) => m.flag && m.x <= mx.thresholds.support_x && m.y < mx.thresholds.y) ?? []
  const [idx, setIdx] = useState(0)
  const needs = data?.needs ?? []
  const i = Math.min(idx, Math.max(0, needs.length - 1))

  return (
    <Panel
      title="인력 지원 권고"
      subtitle="적체가 늘 것으로 보이는 부서와, 접수가 줄어 여유가 생기는 '지원 가능' 부서를 짝지어 보여 줍니다"
      evidenceKey="staffing"
      className={className}
      actions={
        <>
          <IconButton label="이전 부서" disabled={i === 0} onClick={() => setIdx(i - 1)}>
            <ChevronLeft size={18} />
          </IconButton>
          <IconButton label="다음 부서" disabled={i >= needs.length - 1} onClick={() => setIdx(i + 1)}>
            <ChevronRight size={18} />
          </IconButton>
        </>
      }
    >
      {error && !data ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : !data ? (
        <>
          <Skeleton className="h-[76px]" />
          <Skeleton className="mt-4 h-[230px]" />
        </>
      ) : (
        <div className={isFetching ? 'opacity-60 transition-opacity' : 'transition-opacity'}>
          <Summary data={data} />
          {needs.length > 0 ? <NeedCard data={data} index={i} /> : <NoNeed data={data} />}
          {excluded.length > 0 && (
            <p className="mt-3 flex items-start gap-2 rounded-xl bg-[#fdf5e8] px-3.5 py-2.5 text-[13px] text-[#8a4b06]">
              <TriangleAlert size={16} className="mt-0.5 shrink-0" />
              <span>
                급증이 예상되는 부서는 접수가 줄어 보여도 지원 후보에서 뺍니다:{' '}
                <b className="font-semibold">
                  {excluded.map((m) => `${m.name} (${m.flag}, 예상 접수 ${fmtPct(m.x)})`).join(', ')}
                </b>
              </span>
            </p>
          )}
          <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-2 text-[12px] text-mute">
            <span className="inline-flex items-center gap-1.5 rounded-md bg-[#fdf3e2] px-1.5 py-0.5 font-semibold text-[#a35a07]">가정값</span>
            1인당 하루
            <PpdStepper compact />
            건 × 근무일 {data.workdays}일로 명 단위를 환산합니다. 국내 적용 시 실제 정원으로 바꿉니다.
          </div>
        </div>
      )}
    </Panel>
  )
}

function Summary({ data }: { data: StaffingOut }) {
  const slack = data.supports.reduce((s, x) => s + x.slack, 0)
  const cells = [
    { label: '지원 필요 인원', value: peopleText(data.total_people), sub: `적체 증가 예상 ${fmtInt(data.total_need)}건` },
    { label: '지원 가능 부서', value: `${data.supports.length}곳`, sub: data.supports.length ? `여유 ${fmtInt(slack)}건` : '해당 부서 없음' },
    {
      label: '지원 처리율',
      value: data.coverage != null ? `${Math.round(data.coverage * 100)}%` : '–',
      sub: data.coverage != null ? `${fmtInt(data.covered)}건 처리` : '지원 필요 없음',
    },
  ]
  return (
    <div className="grid grid-cols-3 gap-2">
      {cells.map((c) => (
        <div key={c.label} className="rounded-2xl bg-page px-4 py-3">
          <p className="text-[12px] text-mute">{c.label}</p>
          <p className="mt-0.5 text-[20px] font-bold text-ink num">{c.value}</p>
          <p className="text-[12px] text-faint num">{c.sub}</p>
        </div>
      ))}
    </div>
  )
}

function NeedCard({ data, index }: { data: StaffingOut; index: number }) {
  const { agencyName } = useDash()
  const n = data.needs[index]
  const pairs = data.pairs.filter((p) => p.to_agency === n.agency)
  const ratio = n.need > 0 ? n.covered / n.need : 0
  const color = QUADRANT_COLOR[n.quadrant] ?? '#5b4fe0'
  return (
    <article className="mt-4 rounded-2xl border border-line p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <AgencyTile code={n.agency} color={color} bg={QUADRANT_TINT[n.quadrant]} />
          <div className="min-w-0">
            <p className="flex flex-wrap items-center gap-2 text-[17px] font-semibold text-ink">
              {agencyName(n.agency)}
              <QuadrantChip q={n.quadrant} />
              {n.flag && <FlagChip label={n.flag} />}
            </p>
            <p className="text-[12px] text-mute num">
              {index + 1} / {data.needs.length} 부서 · 필요 인원 많은 순
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Chip className="border border-line bg-white px-3 py-1.5 text-[13px] font-medium text-ink">
            적체 증가 예상 <b className="text-up num">+{fmtInt(n.need)}건</b>
          </Chip>
          <Chip className="border border-line bg-white px-3 py-1.5 text-[13px] font-medium text-ink">
            <Users size={14} className="text-mute" /> 지원 필요 <b className="text-brand num">{peopleText(n.people)}</b>
          </Chip>
        </div>
      </div>
      <div className="mt-5">
        <div className="mb-2 flex items-center justify-between text-[13px]">
          <span className="font-medium text-ink">지원 가능 부서로 메우는 비율</span>
          <span className="font-bold text-ink num">{Math.round(ratio * 100)}%</span>
        </div>
        <DashedProgress value={ratio} color={ratio >= 0.999 ? '#22a06b' : ratio > 0 ? '#5b4fe0' : '#e5484d'} />
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-[13px]">
        {pairs.length === 0 ? (
          <span className="rounded-lg bg-[#fdf0ef] px-2.5 py-1.5 text-[#a1281f]">
            이번 기간에는 지원 가능 부서가 없습니다 (접수 −10% 이하·적체 정상 부서 없음)
          </span>
        ) : (
          pairs.map((p) => (
            <span key={p.from_agency} className="inline-flex items-center gap-1.5 rounded-lg bg-[#e5f5ed] px-2.5 py-1.5 text-[#17834f]">
              <ArrowLeft size={14} />
              <b className="font-semibold">{agencyName(p.from_agency)}</b> {peopleText(p.people)}
              <span className="text-[#17834f]/70 num">({fmtInt(p.amount)}건)</span>
            </span>
          ))
        )}
      </div>
      <p className="mt-3 text-[12px] leading-relaxed text-faint num">
        계산: 평소보다 많은 접수 {fmtInt(n.excess)}건 × 바로 끝나지 않는 비율 {Math.round((1 - n.instant_share) * 100)}% × 적체
        전환율 {Math.round(n.conv * 100)}% = {fmtInt(n.need)}건 → {fmtInt(n.need)}건 ÷ (1인 하루 {data.per_person_day}건 ×{' '}
        {data.workdays}일) = {peopleText(n.people)}
      </p>
    </article>
  )
}

function NoNeed({ data }: { data: StaffingOut }) {
  const { agencyName } = useDash()
  return (
    <article className="mt-4 rounded-2xl border border-line p-5">
      <div className="flex items-center gap-3">
        <span className="flex size-11 items-center justify-center rounded-xl bg-[#e5f5ed] text-[#17955a]">
          <CircleCheck size={22} />
        </span>
        <div>
          <p className="text-[16px] font-semibold text-ink">지원이 필요한 부서가 없습니다</p>
          <p className="text-[13px] text-mute">모든 부서의 예상 접수가 최근 4주 수준 +10% 미만입니다.</p>
        </div>
      </div>
      {data.supports.length > 0 && (
        <>
          <p className="mt-5 text-[13px] font-medium text-ink">다른 업무에 돌릴 수 있는 여유 (지원 가능 부서)</p>
          <ul className="mt-2 grid gap-2 sm:grid-cols-2">
            {data.supports.map((s) => (
              <li key={s.agency} className="flex items-center justify-between rounded-xl bg-page px-3.5 py-2.5 text-[13px]">
                <span className="flex items-center gap-2">
                  <span className="h-4 w-1 rounded-full bg-[#22a06b]" />
                  <b className="font-semibold text-ink">{agencyName(s.agency)}</b>
                </span>
                <span className="text-mute num">
                  여유 {fmtInt(s.slack)}건 · <b className="text-ink">{peopleText(s.people)}</b>
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </article>
  )
}
