import { BookOpen, ChevronLeft, ChevronRight, Eye, LayoutGrid, Presentation, RotateCcw, Square, X } from 'lucide-react'
import { fmtDateW, fmtRange } from '../lib/format'
import { useDash } from '../state/dashboard'
import { AsofPicker, PeriodPicker, SettingsButton } from './Controls'
import { OutlineButton } from './ui'
import { WeatherStrip } from './WeatherStrip'

/* ------------------------------------------------------------------ 탭 */

export function TabBar() {
  const { state, startDemo, stopDemo } = useDash()
  const demo = state.demo !== null
  return (
    <nav className="border-b border-line bg-page" aria-label="화면">
      <div className="mx-auto flex min-h-[68px] max-w-[1680px] flex-wrap items-center gap-x-4 gap-y-2 px-5 py-2 lg:px-10">
        <span
          aria-current="page"
          className="inline-flex items-center gap-2 rounded-xl bg-brand-tint px-4 py-2.5 text-[15px] font-semibold text-brand"
        >
          <LayoutGrid size={18} strokeWidth={2} /> 대시보드
        </span>
        {/* 탭 줄 가운데 7일 기상 예보 띠 (좁은 화면에서는 아래 줄로) */}
        <WeatherStrip className="order-last flex w-full justify-center xl:order-none xl:w-auto xl:flex-1" />
        <button
          type="button"
          onClick={demo ? stopDemo : startDemo}
          className="ml-auto inline-flex h-11 shrink-0 items-center gap-2 rounded-xl bg-navy px-4 text-[15px] font-semibold text-white shadow-[0_6px_16px_-8px_rgba(31,27,77,0.8)] transition hover:bg-[#2a2563] xl:ml-0"
        >
          {demo ? <Square size={15} fill="currentColor" /> : <Presentation size={18} />}
          {demo ? '시연 종료' : '시연 모드'}
        </button>
      </div>
    </nav>
  )
}

/* ------------------------------------------------------------------ 페이지 제목 */

export function PageHeader() {
  const { state, agencyName, short, days, openEvidence } = useDash()
  return (
    <div className="mx-auto flex max-w-[1680px] flex-wrap items-end justify-between gap-x-6 gap-y-4 px-5 pb-6 pt-8 lg:px-10">
      <div className="min-w-0">
        <h1 className="text-[30px] font-bold tracking-[-0.025em] text-ink lg:text-[34px]">민원 운영 대시보드</h1>
        <p className="mt-1.5 text-[14px] text-mute">
          <b className="font-semibold text-ink">{agencyName(state.agency)}</b> · {fmtRange(state.start, state.end)} ({days}일) 예측 ·{' '}
          {short ? '단기 예측 모델(1~14일)' : '월별 계절 지수 방식(한 달·분기)'}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2.5">
        <AsofPicker />
        <PeriodPicker />
        <SettingsButton />
        <OutlineButton className="h-11" onClick={() => openEvidence()}>
          <BookOpen size={17} strokeWidth={1.9} /> 검증 근거
        </OutlineButton>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ 배너 */

/** 시연 중이면 설명 문구·실제 결과, 과거 기준일이면 재현 안내 */
export function ContextBanner() {
  const { state, isLatest, demoScenario, steps, goLatest } = useDash()
  if (demoScenario && state.demo !== null) {
    return (
      <div className="mx-auto max-w-[1680px] px-5 pb-6 lg:px-10">
        <div className="grid gap-4 rounded-2xl bg-navy p-5 text-white lg:grid-cols-[1fr_minmax(280px,420px)] lg:p-6">
          <div>
            <div className="flex flex-wrap items-center gap-2 text-[13px]">
              <span className="rounded-full bg-white/15 px-2.5 py-0.5 font-semibold">
                시연 {state.demo + 1} / {steps.length}
              </span>
              <span className="text-white/70">
                기준일 {fmtDateW(demoScenario.asof)} · 기간 {fmtRange(demoScenario.start, demoScenario.end)}
              </span>
            </div>
            <p className="mt-2 text-[22px] font-bold tracking-[-0.02em]">{demoScenario.title}</p>
            <p className="mt-1.5 max-w-[880px] text-[15px] leading-relaxed text-white/85">{demoScenario.narration}</p>
            <p className="mt-3 flex flex-wrap items-center gap-2 text-[13px] text-white/75">
              <Eye size={15} /> 볼 곳
              {demoScenario.focus.map((f) => (
                <span key={f} className="rounded-md bg-white/12 px-2 py-0.5 font-semibold text-white">
                  {f}
                </span>
              ))}
            </p>
          </div>
          <div className="rounded-xl bg-white/10 p-4">
            <p className="text-[12px] font-semibold tracking-wide text-[#c9c1f7]">실제로 일어난 일</p>
            <p className="mt-1.5 text-[14px] leading-relaxed text-white/90">{demoScenario.result}</p>
          </div>
        </div>
      </div>
    )
  }
  if (isLatest) return null
  return (
    <div className="mx-auto max-w-[1680px] px-5 pb-6 lg:px-10">
      <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-[#dcd6fb] bg-[#f4f2fe] px-5 py-3.5 text-[14px]">
        <span className="flex size-8 items-center justify-center rounded-lg bg-white text-brand">
          <RotateCcw size={16} />
        </span>
        <p className="min-w-0 flex-1 text-ink">
          <b className="font-semibold">과거 시점 재현 · {fmtDateW(state.asof)} 기준</b>
          <span className="text-mute"> — 그날까지의 민원 데이터와 그날 발표된 예보만으로 계산했습니다. 기간이 지난 값은 실제 결과를 함께 표시합니다.</span>
        </p>
        <button type="button" onClick={goLatest} className="text-[13px] font-semibold text-brand hover:underline">
          최신 기준일로 →
        </button>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ 시연 조작 막대 */

export function DemoDock() {
  const { state, steps, gotoDemo, stopDemo } = useDash()
  if (state.demo === null) return null
  const i = state.demo
  return (
    <div className="fixed inset-x-0 bottom-5 z-40 flex justify-center px-4">
      <div className="flex max-w-full items-center gap-3 rounded-2xl bg-navy py-2.5 pl-4 pr-2.5 text-white shadow-[0_18px_40px_-14px_rgba(31,27,77,0.9)]">
        <span className="hidden text-[13px] font-semibold text-[#c9c1f7] sm:inline">시연 모드</span>
        <div className="flex items-center gap-1.5" role="tablist" aria-label="시연 단계">
          {steps.map((s, k) => (
            <button
              key={s.id}
              type="button"
              role="tab"
              aria-selected={k === i}
              title={s.title}
              onClick={() => gotoDemo(k)}
              className={
                k === i
                  ? 'rounded-full bg-white px-3 py-1 text-[13px] font-semibold text-navy'
                  : 'rounded-full px-2.5 py-1 text-[13px] text-white/70 hover:bg-white/10 hover:text-white'
              }
            >
              {k === i ? `${k + 1}. ${s.title}` : k + 1}
            </button>
          ))}
        </div>
        <span className="mx-1 h-6 w-px bg-white/15" />
        <button
          type="button"
          aria-label="이전 단계"
          disabled={i === 0}
          onClick={() => gotoDemo(i - 1)}
          className="flex size-9 items-center justify-center rounded-xl hover:bg-white/10 disabled:opacity-30"
        >
          <ChevronLeft size={19} />
        </button>
        <button
          type="button"
          aria-label="다음 단계"
          disabled={i >= steps.length - 1}
          onClick={() => gotoDemo(i + 1)}
          className="flex h-9 items-center gap-1 rounded-xl bg-brand px-3 text-[14px] font-semibold hover:bg-[#4c40d0] disabled:opacity-30"
        >
          다음 <ChevronRight size={17} />
        </button>
        <button
          type="button"
          aria-label="시연 종료"
          onClick={stopDemo}
          className="flex size-9 items-center justify-center rounded-xl text-white/70 hover:bg-white/10 hover:text-white"
        >
          <X size={18} />
        </button>
      </div>
    </div>
  )
}
