import clsx from 'clsx'
import {
  Building,
  Droplet,
  HouseHeart,
  Info,
  RotateCcw,
  ShoppingBag,
  Stethoscope,
  TrafficCone,
  TreePine,
  TrendingDown,
  TrendingUp,
  Recycle,
  X,
  type LucideIcon,
} from 'lucide-react'
import { useEffect, useRef, type ButtonHTMLAttributes, type CSSProperties, type ReactNode } from 'react'
import { fmtPct } from '../lib/format'
import { QUADRANT_COLOR, QUADRANT_TINT } from '../lib/theme'
import { useDash } from '../state/dashboard'

/* ------------------------------------------------------------------ 패널 */

type PanelProps = {
  title: string
  subtitle?: ReactNode
  actions?: ReactNode
  evidenceKey?: string
  children: ReactNode
  className?: string
}

/** 시안의 흰 바탕 구역. 시연 모드에서 이 화면의 볼 곳이면 테두리로 강조합니다. */
export function Panel({ title, subtitle, actions, evidenceKey, children, className }: PanelProps) {
  const { demoScenario, openEvidence } = useDash()
  const focus = demoScenario?.focus.includes(title) ?? false
  return (
    <section
      aria-label={title}
      className={clsx(
        'relative min-w-0 px-6 py-7 transition-colors duration-300 lg:px-9 lg:py-8',
        focus && 'bg-brand-tint/45',
        className,
      )}
    >
      {focus && <div className="pointer-events-none absolute inset-2 rounded-2xl ring-2 ring-brand/35" />}
      <header className="mb-5 flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-[19px] font-semibold tracking-[-0.01em] text-ink">{title}</h2>
            {focus && (
              <span className="rounded-full bg-brand px-2 py-0.5 text-[11px] font-semibold text-white">시연 포인트</span>
            )}
          </div>
          {subtitle && <p className="mt-1 text-[13px] leading-relaxed text-mute">{subtitle}</p>}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {actions}
          {evidenceKey && (
            <IconButton label={`${title} 검증 근거`} onClick={() => openEvidence(evidenceKey)}>
              <Info size={17} />
            </IconButton>
          )}
        </div>
      </header>
      {children}
    </section>
  )
}

/* ------------------------------------------------------------------ 버튼 */

export function IconButton({
  label,
  className,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={clsx(
        'inline-flex size-10 items-center justify-center rounded-xl border border-line bg-white text-ink/80 transition',
        'hover:border-line-strong hover:text-ink disabled:cursor-not-allowed disabled:opacity-40',
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  )
}

export function OutlineButton({ className, children, ...rest }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      className={clsx(
        'inline-flex h-10 items-center gap-2 rounded-xl border border-line bg-white px-3.5 text-[14px] font-medium text-ink transition',
        'hover:border-line-strong disabled:cursor-not-allowed disabled:opacity-40',
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  )
}

/* ------------------------------------------------------------------ 표시 */

export function Chip({
  children,
  className,
  style,
}: {
  children: ReactNode
  className?: string
  style?: CSSProperties
}) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[12px] font-semibold',
        className,
      )}
      style={style}
    >
      {children}
    </span>
  )
}

export function QuadrantChip({ q, className }: { q: string; className?: string }) {
  return (
    <Chip className={className} style={{ color: QUADRANT_COLOR[q] ?? '#6b6b7b', background: QUADRANT_TINT[q] ?? '#f1f1f5' }}>
      <span className="size-1.5 rounded-full" style={{ background: QUADRANT_COLOR[q] }} />
      {q}
    </Chip>
  )
}

export function FlagChip({ label = '기상 특보' }: { label?: string }) {
  return <Chip className="bg-ink text-white">{label}</Chip>
}

/** 증감 표시. 민원·적체는 늘면 부담이므로 증가를 빨강, 감소를 초록으로 씁니다. */
export function Trend({ value, digits = 1, className }: { value: number | null | undefined; digits?: number; className?: string }) {
  if (value == null || !Number.isFinite(value)) return null
  const up = value > 0
  const Icon = up ? TrendingUp : TrendingDown
  const flat = Math.abs(value) < 0.0005
  return (
    <span
      className={clsx('inline-flex items-center gap-1 text-[13px] font-semibold num', className)}
      style={{ color: flat ? '#6b6b7b' : up ? '#e0483f' : '#17955a' }}
    >
      {!flat && <Icon size={15} strokeWidth={2.2} />}
      {fmtPct(value, digits)}
    </span>
  )
}

export function Skeleton({ className, style }: { className?: string; style?: CSSProperties }) {
  return <div className={clsx('skeleton', className)} style={style} />
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const msg = error instanceof Error ? error.message : '데이터를 불러오지 못했습니다.'
  return (
    <div className="flex flex-col items-start gap-3 rounded-2xl border border-[#f6cfcb] bg-[#fdf0ef] px-5 py-4 text-[13px] text-[#a1281f]">
      <p>
        <b className="font-semibold">불러오기 실패</b> · {msg}
      </p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 rounded-lg bg-white px-2.5 py-1 text-[12px] font-semibold text-ink"
        >
          <RotateCcw size={13} /> 다시 시도
        </button>
      )}
    </div>
  )
}

/** 시안의 점선 진행 막대 (세로 눈금이 채워지는 방식) */
export function DashedProgress({ value, color = '#22a06b', ticks = 56 }: { value: number; color?: string; ticks?: number }) {
  const v = Math.max(0, Math.min(1, value))
  const filled = Math.round(v * ticks)
  return (
    <div>
      <div className="flex h-9 items-stretch gap-[3px]" role="meter" aria-valuenow={Math.round(v * 100)} aria-valuemin={0} aria-valuemax={100}>
        {Array.from({ length: ticks }, (_, i) => (
          <span
            key={i}
            className="flex-1 rounded-full"
            style={{ background: i < filled ? color : '#e9e9ef', opacity: i < filled ? 1 : 0.9 }}
          />
        ))}
      </div>
      <div className="relative mt-2 h-5 text-[12px] text-faint num">
        <span className="absolute left-0">0</span>
        <span className="absolute left-1/2 -translate-x-1/2">50</span>
        <span className="absolute right-0">100</span>
        {v > 0.04 && v < 0.96 && Math.abs(v - 0.5) > 0.06 && (
          <span
            className="absolute -translate-x-1/2 font-semibold text-ink"
            style={{ left: `${v * 100}%` }}
          >
            {Math.round(v * 100)}%
          </span>
        )}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ 부서 아이콘 */

const AGENCY_ICON: Record<string, LucideIcon> = {
  DSNY: Recycle,
  DEP: Droplet,
  DOT: TrafficCone,
  DOB: Building,
  DOHMH: Stethoscope,
  DPR: TreePine,
  DCWP: ShoppingBag,
  DHS: HouseHeart,
}

export function AgencyIcon({ code, size = 20, className }: { code: string; size?: number; className?: string }) {
  const Icon = AGENCY_ICON[code] ?? Building
  return <Icon size={size} className={className} strokeWidth={1.9} />
}

export function AgencyTile({ code, color = '#5b4fe0', bg = '#f0eefd' }: { code: string; color?: string; bg?: string }) {
  return (
    <span className="inline-flex size-11 shrink-0 items-center justify-center rounded-xl" style={{ background: bg, color }}>
      <AgencyIcon code={code} size={21} />
    </span>
  )
}

/* ------------------------------------------------------------------ 떠 있는 창 */

/** 버튼 아래에 붙는 작은 창. 바깥을 누르거나 Esc를 누르면 닫힙니다. */
export function Popover({
  open,
  onOpenChange,
  trigger,
  children,
  align = 'left',
  width = 320,
  className,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
  trigger: ReactNode
  children: ReactNode
  align?: 'left' | 'right'
  width?: number
  className?: string
}) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onOpenChange(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onOpenChange(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open, onOpenChange])
  return (
    <div ref={ref} className={clsx('relative', className)}>
      {trigger}
      {open && (
        <div
          className={clsx(
            'absolute top-full z-40 mt-2 max-w-[calc(100vw-32px)] rounded-2xl border border-line bg-white p-2',
            'shadow-[0_18px_48px_-16px_rgba(22,22,29,0.28)]',
            align === 'right' ? 'right-0' : 'left-0',
          )}
          style={{ width }}
        >
          {children}
        </div>
      )}
    </div>
  )
}

/** 오른쪽에서 열리는 상세 창 */
export function Drawer({
  open,
  onClose,
  title,
  subtitle,
  children,
  width = 560,
}: {
  open: boolean
  onClose: () => void
  title: string
  subtitle?: ReactNode
  children: ReactNode
  width?: number
}) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])
  return (
    <div className={clsx('fixed inset-0 z-50', !open && 'pointer-events-none')} aria-hidden={!open}>
      <div
        className={clsx('absolute inset-0 bg-ink/25 transition-opacity duration-300', open ? 'opacity-100' : 'opacity-0')}
        onClick={onClose}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={clsx(
          'absolute right-0 top-0 flex h-full max-w-full flex-col bg-white shadow-2xl transition-transform duration-300',
          open ? 'translate-x-0' : 'translate-x-full',
        )}
        style={{ width }}
      >
        <header className="flex items-start justify-between gap-4 border-b border-line px-7 py-5">
          <div>
            <h2 className="text-[20px] font-semibold text-ink">{title}</h2>
            {subtitle && <p className="mt-1 text-[13px] text-mute">{subtitle}</p>}
          </div>
          <IconButton label="닫기" onClick={onClose}>
            <X size={18} />
          </IconButton>
        </header>
        <div className="flex-1 overflow-y-auto px-7 py-6">{open && children}</div>
      </aside>
    </div>
  )
}

/** 가운데 뜨는 창 (예보 띠 → 과거 7년). 바깥을 누르거나 Esc를 누르면 닫힙니다. */
export function Modal({
  open,
  onClose,
  title,
  subtitle,
  children,
  width = 1000,
}: {
  open: boolean
  onClose: () => void
  title: string
  subtitle?: ReactNode
  children: ReactNode
  width?: number
}) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    document.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = prev
      document.removeEventListener('keydown', onKey)
    }
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6">
      <div className="absolute inset-0 bg-ink/30" onClick={onClose} aria-hidden="true" />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="relative flex max-h-[90vh] w-full flex-col overflow-hidden rounded-2xl bg-white shadow-[0_24px_64px_-20px_rgba(22,22,29,0.45)]"
        style={{ maxWidth: width }}
      >
        <header className="flex items-start justify-between gap-4 border-b border-line px-6 py-4">
          <div className="min-w-0">
            <h2 className="text-[19px] font-semibold text-ink">{title}</h2>
            {subtitle && <div className="mt-1 text-[13px] text-mute">{subtitle}</div>}
          </div>
          <IconButton label="닫기" onClick={onClose}>
            <X size={18} />
          </IconButton>
        </header>
        <div className="flex-1 overflow-y-auto px-6 py-5">{children}</div>
      </div>
    </div>
  )
}
