import { defineConfig } from '@playwright/test'
import { BASE_URL, PORT, ROOT, missingPrereqs } from './e2e/prereq'

// 시연 화면 자동 점검 (npm run e2e). 시연 때처럼 서버 하나(8000번)가 API와 빌드된 화면을 함께 내보내는 구성을 확인합니다.
// 8000번에 서버가 이미 떠 있으면 그대로 쓰고, 없으면 여기서 띄웠다가 점검이 끝나면 끕니다.
const ready = missingPrereqs().length === 0

export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/prereq.ts', // 준비물이 없으면 할 일을 한 번 알려 줌
  fullyParallel: true,
  reporter: 'list',
  timeout: 60_000,
  // 새로 띄운 서버는 첫 요청 때 사전 계산 결과를 읽어 들이므로 넉넉히 기다립니다.
  expect: { timeout: 15_000 },
  use: {
    baseURL: BASE_URL,
    viewport: { width: 1440, height: 900 },
    locale: 'ko-KR',
    timezoneId: 'Asia/Seoul',
    trace: 'retain-on-failure',
  },
  // 준비물(사전 계산 결과·화면 빌드)이 없으면 서버를 띄우지 않고, 점검은 e2e/demo.spec.ts에서 건너뜁니다.
  webServer: ready
    ? {
        command: `uv run uvicorn app.main:app --app-dir backend --port ${PORT}`,
        cwd: ROOT,
        url: `${BASE_URL}/api/health`,
        reuseExistingServer: true,
        timeout: 120_000,
      }
    : undefined,
})
