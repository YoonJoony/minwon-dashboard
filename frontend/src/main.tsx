import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import './index.css'

// 사전 계산 결과라 같은 조건이면 값이 바뀌지 않습니다 → 오래 캐시하고, 창을 다시 볼 때 새로 받지 않습니다.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30 * 60 * 1000, gcTime: 60 * 60 * 1000, retry: 1, refetchOnWindowFocus: false },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
