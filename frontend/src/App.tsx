import type { ReactNode } from 'react'
import { useMeta } from './api/hooks'
import { DeptPanel } from './components/DeptPanel'
import { EvidenceDrawer } from './components/EvidenceDrawer'
import { ForecastPanel } from './components/ForecastPanel'
import { Header, LogoMark } from './components/Header'
import { IssuePanel } from './components/IssuePanel'
import { KpiRow } from './components/KpiRow'
import { MatrixPanel } from './components/MatrixPanel'
import { StaffingPanel } from './components/StaffingPanel'
import { ContextBanner, DemoDock, PageHeader, TabBar } from './components/Top'
import { DashboardProvider, useDash } from './state/dashboard'

export default function App() {
  const { data: meta, error, refetch, isLoading } = useMeta()
  if (isLoading) return <Splash text="데이터를 불러오는 중입니다" />
  if (error || !meta)
    return (
      <Splash
        text="서버에 연결하지 못했습니다"
        detail={
          <>
            {error instanceof Error ? `${error.message} · ` : ''}백엔드를 실행했는지 확인하세요:{' '}
            <code className="rounded bg-white px-1.5 py-0.5 text-[12px]">uv run uvicorn app.main:app --app-dir backend</code>
          </>
        }
        onRetry={() => refetch()}
      />
    )
  return (
    <DashboardProvider meta={meta}>
      <Dashboard />
    </DashboardProvider>
  )
}

/** 시안의 2단 구역: 왼쪽·오른쪽 패널 사이와 줄 사이에 가는 선. full이면 패널 하나가 한 줄 전체 */
function Row({ children, full = false }: { children: ReactNode; full?: boolean }) {
  return (
    <div className="border-b border-line">
      <div
        className={
          full
            ? 'mx-auto max-w-[1680px]'
            : 'mx-auto grid max-w-[1680px] lg:grid-cols-2 lg:divide-x lg:divide-line max-lg:divide-y max-lg:divide-line'
        }
      >
        {children}
      </div>
    </div>
  )
}

function Dashboard() {
  const { state } = useDash()
  return (
    <div className="min-h-screen bg-page">
      <Header />
      <TabBar />
      <PageHeader />
      <ContextBanner />
      <KpiRow />
      <main className="border-t border-line bg-white">
        <Row>
          <StaffingPanel />
          <MatrixPanel />
        </Row>
        <Row>
          <ForecastPanel />
          <IssuePanel />
        </Row>
        <Row full>
          <DeptPanel />
        </Row>
      </main>
      <Footer />
      {state.demo !== null && <div className="h-24" aria-hidden="true" />}
      <EvidenceDrawer />
      <DemoDock />
    </div>
  )
}

function Footer() {
  const { meta, openEvidence } = useDash()
  return (
    <footer className="mx-auto max-w-[1680px] px-5 py-8 text-[12px] leading-relaxed text-faint lg:px-10">
      <p>{meta.data_note}</p>
      <p className="mt-1">
        사전 계산 {meta.built_at.replace('T', ' ')} · 기준일 {meta.asofs.length}개 ·{' '}
        <button type="button" onClick={() => openEvidence()} className="font-semibold text-brand hover:underline">
          검증 근거 보기
        </button>
      </p>
    </footer>
  )
}

function Splash({ text, detail, onRetry }: { text: string; detail?: ReactNode; onRetry?: () => void }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-page px-6 text-center">
      <div className={onRetry ? '' : 'animate-pulse'}>
        <LogoMark size={44} />
      </div>
      <p className="text-[20px] font-bold text-ink">스마트 민원케어</p>
      <p className="text-[15px] text-mute">{text}</p>
      {detail && <p className="max-w-[560px] text-[13px] text-mute">{detail}</p>}
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 rounded-xl bg-navy px-4 py-2.5 text-[14px] font-semibold text-white"
        >
          다시 시도
        </button>
      )}
    </div>
  )
}
