import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 개발 중에는 /api 요청을 FastAPI(8000번 포트)로 넘깁니다.
// 빌드 결과(dist)는 FastAPI가 같은 서버에서 그대로 내보냅니다.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
