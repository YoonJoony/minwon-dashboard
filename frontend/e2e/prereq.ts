import { existsSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

/** 프로젝트 루트 (minwon-dashboard/) */
export const ROOT = fileURLToPath(new URL('../../', import.meta.url))

/** 시연 때와 같은 구성: FastAPI 하나가 API와 빌드된 화면(frontend/dist)을 함께 내보냄 */
export const BASE_URL = 'http://127.0.0.1:8000'

/** 단계별 전체 화면을 저장하는 곳 (git 제외) */
export const SCREENS_DIR = join(ROOT, 'frontend', 'e2e-screens')

/** 점검에 필요한데 없는 것. 하나라도 있으면 서버를 띄우지 않고 점검을 모두 건너뜁니다. */
export function missingPrereqs(): string[] {
  const missing: string[] = []
  if (!existsSync(join(ROOT, 'data', 'artifacts', 'manifest.json')))
    missing.push('사전 계산 결과(data/artifacts/manifest.json)가 없습니다 → 프로젝트 루트에서 uv run python -m engine.build (약 3분)')
  if (!existsSync(join(ROOT, 'frontend', 'dist', 'index.html')))
    missing.push('화면 빌드(frontend/dist)가 없습니다 → frontend/에서 npm run build')
  return missing
}

/** 점검 시작 전(globalSetup)에 한 번: 준비물이 없으면 건너뛰는 이유와 할 일을 알려 줍니다. */
export default function announceMissing() {
  const missing = missingPrereqs()
  if (missing.length === 0) return
  console.log(['', '시연 화면 점검을 모두 건너뜁니다. 먼저 준비하세요:', ...missing.map((m) => `  - ${m}`), ''].join('\n'))
}
