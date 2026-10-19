import { useEffect, useState } from 'react'
import './App.css'

type Health = { status: string; data: Record<string, boolean> }

function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/health')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setHealth)
      .catch((e: Error) => setError(e.message))
  }, [])

  return (
    <main className="shell">
      <h1>민원 조기경보 대시보드</h1>
      <p className="sub">부서·기간을 선택하면 민원 집중도를 미리 보여 주는 행정 지원 대시보드 (개발 중)</p>
      <section className="status">
        <h2>서버 상태</h2>
        {error && <p className="bad">백엔드 연결 실패: {error}</p>}
        {!error && !health && <p>확인 중…</p>}
        {health && (
          <ul>
            <li>API: {health.status}</li>
            {Object.entries(health.data).map(([name, ok]) => (
              <li key={name}>
                {name}: {ok ? '있음' : '없음'}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  )
}

export default App
