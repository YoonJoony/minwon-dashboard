import clsx from 'clsx'
import { useEffect } from 'react'
import { useEvidence } from '../api/hooks'
import { useDash } from '../state/dashboard'
import { Drawer, ErrorState, Skeleton } from './ui'

/** 화면 수치의 검증 근거 (docs/검증결과_10년.md, docs/리허설_검증.md 요약) */
export function EvidenceDrawer() {
  const { evidence, closeEvidence } = useDash()
  const { data, error, refetch } = useEvidence()

  // 특정 구역에서 열면 그 절로 이동
  useEffect(() => {
    if (!evidence.open || !evidence.section || !data) return
    const t = window.setTimeout(() => {
      document.getElementById(`ev-${evidence.section}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 320)
    return () => window.clearTimeout(t)
  }, [evidence, data])

  return (
    <Drawer
      open={evidence.open}
      onClose={closeEvidence}
      title="검증 근거"
      subtitle="뉴욕시 브롱크스 10년치(2016~2026) 데이터로, 각 기준일에 알 수 있던 정보만 써서 검증한 결과입니다."
      width={600}
    >
      {error && !data ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : !data ? (
        <div className="space-y-3">
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-16" />
          ))}
        </div>
      ) : (
        <div className="space-y-8">
          {data.sections.map((s) => (
            <section key={s.key} id={`ev-${s.key}`} className="scroll-mt-4">
              <h3
                className={clsx(
                  'text-[16px] font-semibold',
                  evidence.section === s.key ? 'text-brand' : 'text-ink',
                )}
              >
                {s.title}
              </h3>
              <dl className="mt-3 divide-y divide-line rounded-2xl border border-line">
                {s.items.map((it) => (
                  <div key={it.label} className="px-4 py-3">
                    <div className="flex items-start justify-between gap-4">
                      <dt className="text-[14px] text-ink">{it.label}</dt>
                      <dd className="shrink-0 text-right text-[15px] font-bold text-brand num">{it.value}</dd>
                    </div>
                    {it.note && <p className="mt-1 text-[12px] leading-relaxed text-mute">{it.note}</p>}
                  </div>
                ))}
              </dl>
            </section>
          ))}
          <section>
            <h3 className="text-[16px] font-semibold text-ink">자료 출처</h3>
            <ul className="mt-3 space-y-1.5 text-[13px] text-mute">
              {data.sources.map((s) => (
                <li key={s} className="rounded-xl bg-page px-3.5 py-2">
                  {s}
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </Drawer>
  )
}
