import clsx from 'clsx'
import { Bell, Check, ChevronDown, Flame, Landmark, MapPin } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useIssues } from '../api/hooks'
import { fmtMDW } from '../lib/format'
import { useDash } from '../state/dashboard'
import { ALERT_ICON } from './icons'
import { AgencyIcon, Popover } from './ui'

export function LogoMark({ size = 30 }: { size?: number }) {
  // 2×2 위험 매트릭스를 본뜬 표식 (오른쪽 위 = 집중관리)
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect x="2" y="2" width="12.5" height="12.5" rx="3.6" fill="#16161d" />
      <rect x="17.5" y="2" width="12.5" height="12.5" rx="6.25" fill="#5b4fe0" />
      <rect x="2" y="17.5" width="12.5" height="12.5" rx="3.6" fill="#16161d" />
      <rect x="17.5" y="17.5" width="12.5" height="12.5" rx="3.6" fill="#16161d" />
    </svg>
  )
}

const Divider = ({ className }: { className?: string }) => (
  <span className={clsx('h-8 w-px shrink-0 bg-line', className)} aria-hidden="true" />
)

export function Header() {
  return (
    <header className="border-b border-line bg-page">
      <div className="mx-auto flex h-[72px] max-w-[1680px] items-center gap-3 px-5 sm:gap-5 lg:px-10">
        <a href="/" className="flex shrink-0 items-center gap-2.5" aria-label="스마트 민원케어 처음 화면">
          <LogoMark />
          {/* 모바일은 로고 글자를 빼서 부서 선택·알림이 화면 밖으로 밀리지 않게 */}
          <span className="hidden text-[21px] font-bold tracking-[-0.02em] text-ink sm:inline">스마트 민원케어</span>
        </a>
        <Divider className="hidden sm:block" />
        <AgencySelect />
        <Divider className="hidden xl:block" />
        <span className="hidden items-center gap-1.5 text-[14px] text-mute xl:inline-flex">
          <MapPin size={16} /> 뉴욕시 브롱크스 · 311 민원 8개 부서
        </span>
        <div className="ml-auto flex items-center gap-3">
          <AlertBell />
          <DemoUser />
        </div>
      </div>
    </header>
  )
}

function AgencySelect() {
  const { meta, state, setAgency, agencyName } = useDash()
  const [open, setOpen] = useState(false)
  const pick = (code: string | null) => {
    setAgency(code)
    setOpen(false)
  }
  return (
    <Popover
      open={open}
      onOpenChange={setOpen}
      width={340}
      trigger={
        <button
          type="button"
          onClick={() => setOpen(!open)}
          aria-haspopup="listbox"
          aria-expanded={open}
          className="flex items-center gap-2.5 rounded-xl px-2 py-2 text-[15px] font-medium text-ink hover:bg-white"
        >
          <Landmark size={19} strokeWidth={1.9} />
          <span className="max-w-[160px] truncate">{agencyName(state.agency)}</span>
          <ChevronDown size={17} className="text-mute" />
        </button>
      }
    >
      <ul role="listbox" aria-label="부서 선택" className="max-h-[420px] overflow-y-auto">
        <Option selected={state.agency === null} onClick={() => pick(null)} title="전체 부서" desc={`${meta.agencies.length}개 부서 합계`} />
        <li className="my-1 h-px bg-line" aria-hidden="true" />
        {meta.agencies.map((a) => (
          <Option
            key={a.code}
            selected={state.agency === a.code}
            onClick={() => pick(a.code)}
            title={a.name}
            desc={a.desc}
            icon={<AgencyIcon code={a.code} size={17} />}
          />
        ))}
      </ul>
    </Popover>
  )
}

function Option({
  selected,
  onClick,
  title,
  desc,
  icon,
}: {
  selected: boolean
  onClick: () => void
  title: string
  desc: string
  icon?: ReactNode
}) {
  return (
    <li role="option" aria-selected={selected}>
      <button
        type="button"
        onClick={onClick}
        className={clsx(
          'flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition',
          selected ? 'bg-brand-tint' : 'hover:bg-page',
        )}
      >
        <span className="flex size-8 items-center justify-center rounded-lg bg-page text-ink/80">
          {icon ?? <Landmark size={17} strokeWidth={1.9} />}
        </span>
        <span className="min-w-0 flex-1">
          <span className={clsx('block text-[14px] font-semibold', selected ? 'text-brand' : 'text-ink')}>{title}</span>
          <span className="block truncate text-[12px] text-mute">{desc}</span>
        </span>
        {selected && <Check size={17} className="text-brand" />}
      </button>
    </li>
  )
}

function AlertBell() {
  const { period, state, agencyName, openEvidence } = useDash()
  const { data } = useIssues(period, state.agency)
  const [open, setOpen] = useState(false)
  const fut = (data?.alerts ?? []).filter((a) => a.source === '예보')
  const count = new Set(fut.map((a) => `${a.type}|${a.date}`)).size
  return (
    <Popover
      open={open}
      onOpenChange={setOpen}
      align="right"
      width={380}
      trigger={
        <button
          type="button"
          onClick={() => setOpen(!open)}
          aria-label={`기상 특보 예보 ${count}건`}
          className="relative inline-flex size-11 items-center justify-center rounded-xl border border-line bg-white text-ink/80 hover:border-line-strong"
        >
          <Bell size={19} strokeWidth={1.9} />
          {count > 0 && (
            <span className="absolute -right-1.5 -top-1.5 flex min-w-5 items-center justify-center rounded-full bg-brand px-1 text-[11px] font-bold leading-5 text-white num">
              {count}
            </span>
          )}
        </button>
      }
    >
      <div className="px-3 pb-2 pt-2">
        <p className="text-[14px] font-semibold text-ink">기상 특보 예보</p>
        <p className="mt-0.5 text-[12px] text-mute">기준일에 발표된 예보 · 미국 기상청 뉴욕 지청 기준</p>
      </div>
      {fut.length === 0 ? (
        <p className="mx-1 mb-1 rounded-xl bg-page px-3 py-4 text-[13px] text-mute">선택 기간에 기상 특보 예보가 없습니다.</p>
      ) : (
        <ul className="max-h-[360px] overflow-y-auto">
          {fut.map((a) => {
            const Icon = ALERT_ICON[a.type] ?? Flame
            const danger = a.level === 2
            return (
              <li key={`${a.type}${a.date}`} className="flex gap-3 rounded-xl px-3 py-2.5 hover:bg-page">
                <span
                  className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg"
                  style={{ background: danger ? '#fdf0ef' : '#fdf5e8', color: danger ? '#e0483f' : '#d97706' }}
                >
                  <Icon size={17} />
                </span>
                <span className="min-w-0 flex-1 text-[13px]">
                  <span className="flex items-center justify-between gap-2">
                    <b className="font-semibold text-ink">{a.level_label}</b>
                    <span className="text-mute num">{fmtMDW(a.date)}</span>
                  </span>
                  <span className="block text-mute">
                    {a.lead_days}일 전 예보 · {a.value}
                  </span>
                  <span className="block text-mute">
                    {a.agencies.map((g) => agencyName(g)).join(', ')} · 과거 민원 급증 {Math.round(a.hit_rate * 100)}%
                  </span>
                </span>
              </li>
            )
          })}
        </ul>
      )}
      <button
        type="button"
        onClick={() => {
          setOpen(false)
          openEvidence('alerts')
        }}
        className="mt-1 w-full rounded-xl px-3 py-2 text-left text-[13px] font-semibold text-brand hover:bg-brand-tint"
      >
        경보 기준과 적중률 보기 →
      </button>
    </Popover>
  )
}

function DemoUser() {
  return (
    <div className="flex items-center gap-3 pl-1" title="사용자 구분 없이 시연용 계정으로 표시합니다">
      <span className="flex size-11 items-center justify-center rounded-xl bg-brand-tint text-[16px] font-bold text-brand">
        데모
      </span>
      <span className="hidden leading-tight md:block">
        <span className="block text-[15px] font-semibold text-ink">데모 사용자</span>
        <span className="block text-[13px] text-mute">시연 계정</span>
      </span>
    </div>
  )
}
