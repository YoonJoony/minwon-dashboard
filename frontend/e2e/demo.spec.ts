import { expect, test, type APIRequestContext, type Locator, type Page } from '@playwright/test'
import { join } from 'node:path'
import { BASE_URL, SCREENS_DIR, missingPrereqs } from './prereq'

// 시연 화면 점검: 최신 화면과 시연 5단계를 하나씩 열어 화면이 온전히 그려지는지 확인하고,
// 단계마다 전체 화면을 e2e-screens/에 저장합니다. 시연 막대의 "다음 단계"와 부서 선택도 눌러 봅니다.

const missing = missingPrereqs()
test.skip(missing.length > 0, `준비물이 없어 시연 화면 점검을 건너뜁니다 — ${missing.join(' / ')}`)

/** 시연 순서. 화면의 순서(src/state/dashboard.tsx의 DEMO_ORDER)와 같아야 합니다. */
const DEMO_ORDER = ['S4', 'S1', 'S2', 'S3', 'S5']
const PANELS = ['예상 접수 추이', '예상 이슈', '부서 위험 매트릭스', '인력 지원 권고', '부서별 현황', '지연 위험 민원']
/** ECharts를 붙이는 영역의 이름 (role="img") */
const CHARTS = ['예상 접수 추이 막대 차트', '부서 위험 매트릭스 산점도']

type Scenario = { id: string; title: string; asof: string; start: string; end: string; agency?: string | null }

/** /api/meta의 시연 시나리오를 시연 순서대로 */
async function demoSteps(request: APIRequestContext): Promise<Scenario[]> {
  const res = await request.get('/api/meta')
  expect(res.ok(), '/api/meta 응답').toBe(true)
  const { scenarios } = (await res.json()) as { scenarios: Scenario[] }
  return DEMO_ORDER.map((id) => {
    const sc = scenarios.find((s) => s.id === id)
    if (!sc) throw new Error(`/api/meta에 시연 시나리오 ${id}가 없습니다`)
    return sc
  })
}

/** 시연 n단계 주소 (시연 모드에서 화면이 만드는 주소와 같은 형식) */
function demoUrl(sc: Scenario, n: number): string {
  const q = new URLSearchParams({ asof: sc.asof, start: sc.start, end: sc.end })
  if (sc.agency) q.set('agency', sc.agency)
  q.set('demo', String(n))
  return `/?${q}`
}

/** 페이지를 열고, 그때부터 나오는 콘솔 오류·처리되지 않은 예외·외부 주소 요청(시연은 인터넷 없이 함)을 모읍니다. */
async function open(page: Page, url: string): Promise<string[]> {
  const errors: string[] = []
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(m.text())
  })
  page.on('pageerror', (e) => errors.push(e.message))
  page.on('request', (r) => {
    const u = new URL(r.url())
    if (u.protocol.startsWith('http') && u.origin !== BASE_URL) errors.push(`외부 요청: ${r.url()}`)
  })
  const res = await page.goto(url)
  expect(res?.status(), '8000번 서버가 화면을 내보내지 않습니다. npm run build 뒤 서버를 다시 시작하세요').toBe(200)
  return errors
}

/** 핵심 지표 줄 (aria-busy는 이 줄에만 있음) */
const kpiRow = (page: Page): Locator => page.locator('[aria-busy]')

/** 시연 모드의 남색 띠 */
const demoBanner = (page: Page): Locator => page.locator('div.bg-navy').filter({ hasText: '실제로 일어난 일' })

/** 요청이 모두 끝나 화면이 다 그려질 때까지 기다린 뒤 공통 항목을 확인합니다. */
async function expectDashboardOk(page: Page, errors: string[]) {
  await expect(page.getByRole('heading', { name: '민원 운영 대시보드' })).toBeVisible()
  // 회색 자리표시가 모두 사라지면 요청이 다 끝난 것 (성공이든 실패든)
  await expect(page.locator('.skeleton')).toHaveCount(0)

  await expect(kpiRow(page)).toHaveAttribute('aria-busy', 'false')
  const cells = kpiRow(page).locator(':scope > div')
  await expect(cells, '핵심 지표 칸 수').toHaveCount(5)
  for (const cell of await cells.all()) await expect(cell.locator('p').first()).not.toBeEmpty()

  for (const name of PANELS)
    await expect(page.getByRole('region', { name, exact: true }), `${name} 패널`).toBeVisible()
  await expect(page.getByText('불러오기 실패')).toHaveCount(0)

  for (const name of CHARTS) {
    const canvas = page.getByRole('img', { name, exact: true }).locator('canvas').first()
    await expect(canvas, name).toBeVisible()
    const box = await canvas.boundingBox()
    expect(box?.width, `${name} 폭`).toBeGreaterThan(0)
    expect(box?.height, `${name} 높이`).toBeGreaterThan(0)
  }
  expect(errors, '콘솔 오류·외부 요청').toEqual([])
}

async function saveScreen(page: Page, name: string) {
  // 차트 등장 애니메이션(450ms)이 끝난 뒤 찍습니다.
  await page.waitForTimeout(700)
  await page.screenshot({
    path: join(SCREENS_DIR, `${name}.png`),
    fullPage: true,
    animations: 'disabled',
    // 화면 아래에 고정된 시연 막대가 사진 중간에 찍혀 차트를 가리지 않도록, 찍는 동안만 페이지 맨 아래로 옮깁니다.
    style: 'body { position: relative } .fixed.bottom-5 { position: absolute }',
  })
}

test('최신 화면', async ({ page }) => {
  const errors = await open(page, '/')
  await expectDashboardOk(page, errors)
  await expect(demoBanner(page)).toHaveCount(0)
  await saveScreen(page, '0-latest')
})

DEMO_ORDER.forEach((id, i) => {
  const n = i + 1
  test(`시연 ${n}단계 (${id})`, async ({ page, request }) => {
    const steps = await demoSteps(request)
    const sc = steps[i]
    const errors = await open(page, demoUrl(sc, n))
    await expectDashboardOk(page, errors)
    const banner = demoBanner(page)
    await expect(banner).toContainText(`시연 ${n} / ${steps.length}`)
    await expect(banner.getByText(sc.title, { exact: true })).toBeVisible()
    await saveScreen(page, `${n}-${id}`)
  })
})

test('"다음 단계" 버튼으로 시연 단계가 넘어감', async ({ page, request }) => {
  const steps = await demoSteps(request)
  const errors = await open(page, demoUrl(steps[0], 1))
  const next = page.getByRole('button', { name: '다음 단계', exact: true })
  for (let n = 2; n <= steps.length; n++) {
    await next.click()
    await expect(page).toHaveURL(new RegExp(`[?&]demo=${n}(&|$)`))
    await expect(demoBanner(page).getByText(steps[n - 1].title, { exact: true })).toBeVisible()
  }
  await expect(next).toBeDisabled()
  await expect(kpiRow(page)).toHaveAttribute('aria-busy', 'false')
  await expect(page.getByText('불러오기 실패')).toHaveCount(0)
  expect(errors, '콘솔 오류·외부 요청').toEqual([])
})

test('부서 선택: 환경보호국으로 바꾸면 주소에 agency=DEP', async ({ page }) => {
  const errors = await open(page, '/')
  await expectDashboardOk(page, errors)
  const select = page.locator('button[aria-haspopup="listbox"]')
  await select.click()
  const summary = page.waitForResponse((r) => r.url().includes('/api/summary?') && r.url().includes('agency=DEP'))
  await page.getByRole('listbox', { name: '부서 선택' }).getByRole('option', { name: /환경보호국/ }).click()
  await expect(page).toHaveURL(/[?&]agency=DEP(&|$)/)
  await expect(select).toContainText('환경보호국')
  expect((await summary).ok(), '환경보호국 핵심 지표 응답').toBe(true)
  await expect(kpiRow(page)).toHaveAttribute('aria-busy', 'false')
  await expect(page.getByText('불러오기 실패')).toHaveCount(0)
  expect(errors, '콘솔 오류·외부 요청').toEqual([])
})
