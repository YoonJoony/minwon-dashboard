import { expect, test, type APIRequestContext, type Locator, type Page } from '@playwright/test'
import { join } from 'node:path'
import { BASE_URL, SCREENS_DIR, missingPrereqs } from './prereq'

// 시연 화면 점검: 최신 화면과 시연 5단계를 하나씩 열어 화면이 온전히 그려지는지 확인하고,
// 단계마다 전체 화면을 e2e-screens/에 저장합니다. 시연 막대의 "다음 단계"와 부서 선택도 눌러 봅니다.

const missing = missingPrereqs()
test.skip(missing.length > 0, `준비물이 없어 시연 화면 점검을 건너뜁니다 — ${missing.join(' / ')}`)

/** 시연 순서. 화면의 순서(src/state/dashboard.tsx의 DEMO_ORDER)와 같아야 합니다. */
const DEMO_ORDER = ['S4', 'S1', 'S2', 'S3', 'S5']
const PANELS = ['예상 접수 추이', '예상 이슈', '부서 위험 매트릭스', '인력 지원 권고', '부서별 현황']
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
  await expect(cells, '핵심 지표 칸 수').toHaveCount(6)
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

test('기준일 창: 날짜·기간을 고를 땐 열어 두고, 최신·시나리오를 고르면 닫힘', async ({ page, request }) => {
  const steps = await demoSteps(request)
  const s1 = steps[DEMO_ORDER.indexOf('S1')]
  const errors = await open(page, '/')
  const trigger = page.getByRole('button', { name: /^기준일/ })
  const panel = page.getByText('기준일 목록 · 매주 월요일')
  const pick = async (title: string) => {
    await page.getByRole('button', { name: /^최신 · 시연 시나리오:/ }).click()
    await page.getByRole('listbox', { name: '최신 · 시연 시나리오' }).getByRole('option').filter({ hasText: title }).click()
  }
  await trigger.click()
  // 목록에서 기준일을 고르거나 기간 날짜를 바꿔도 창은 열린 채
  await page.getByRole('tab', { name: '2025' }).click()
  await page.locator('button[title="2025.06.16 (월)"]').click()
  await expect(page).toHaveURL(/[?&]asof=2025-06-16(&|$)/)
  await page.getByLabel('끝', { exact: true }).fill('2025-06-20')
  await expect(panel).toBeVisible()
  // 시나리오를 고르면 닫힘
  await pick(s1.title)
  await expect(page).toHaveURL(new RegExp(`[?&]asof=${s1.asof}(&|$)`))
  await expect(panel).toHaveCount(0)
  // 이미 고른 시나리오를 다시 골라도 닫힘
  await trigger.click()
  await pick(s1.title)
  await expect(panel).toHaveCount(0)
  expect(errors, '콘솔 오류·외부 요청').toEqual([])
})

test('7일 기상 예보 띠 → 기상 예보 모달 (폭염 시나리오)', async ({ page, request }) => {
  const steps = await demoSteps(request)
  const s1 = steps[DEMO_ORDER.indexOf('S1')]
  const errors = await open(page, `/?asof=${s1.asof}&start=${s1.start}&end=${s1.end}`)
  const strip = page.getByRole('group', { name: '7일 기상 예보' })
  await expect(strip.getByRole('button')).toHaveCount(8)
  // 특보 있는 날: 그날 예보 + 같은 특보의 과거 7년 표
  await strip.getByRole('button', { name: /^6\/22/ }).click()
  const dialog = page.getByRole('dialog', { name: '2025.06.22(일) 기상 예보' })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByRole('tab', { name: /폭염/ })).toHaveAttribute('aria-selected', 'true')
  await expect(dialog.getByText('NWS 발표', { exact: false }).first()).toBeVisible()
  await expect(dialog.locator('tbody tr')).toHaveCount(7)
  await page.keyboard.press('Escape')
  await expect(dialog).toHaveCount(0)
  // 특보 없는 날: 그날 예보만, 과거 7년 표 없음
  await strip.getByRole('button', { name: /^6\/21/ }).click()
  const quiet = page.getByRole('dialog', { name: '2025.06.21(토) 기상 예보' })
  await expect(quiet.getByText('특보 없음')).toBeVisible()
  await expect(quiet.locator('table')).toHaveCount(0)
  await page.keyboard.press('Escape')
  expect(errors, '콘솔 오류·외부 요청').toEqual([])
})

test('예보 띠를 왼쪽으로 넘기면 지난 7일 실제 관측 + 오늘, 다시 넘기면 예보', async ({ page }) => {
  // 2025-06-30(월) 기준: 지난 7일(6/23~6/29)에 폭염이 있었음
  const errors = await open(page, '/?asof=2025-06-30&start=2025-06-30&end=2025-07-06')
  await page.getByRole('button', { name: '지난 7일 관측 보기' }).click()
  const cells = page.getByRole('group', { name: '지난 7일 관측 날씨' }).getByRole('button')
  await expect(cells).toHaveCount(8)
  await expect(cells.first()).toHaveAccessibleName(/^6\/23\(월\) 관측/)
  await expect(cells.last()).toHaveAccessibleName(/^6\/30\(월\) 예보/) // 오늘은 맨 오른쪽
  // 폭염 관측일: 관측 값 + 관측 판정 특보 + 과거 7년 표 (예보일과 같은 모달)
  await cells.first().click()
  const dialog = page.getByRole('dialog', { name: '2025.06.23(월) 관측 날씨' })
  await expect(dialog.getByText('실제 관측 (Open-Meteo 관측 기록)')).toBeVisible()
  await expect(dialog.getByText('관측 판정').first()).toBeVisible()
  await expect(dialog.getByRole('tab', { name: /폭염/ })).toHaveAttribute('aria-selected', 'true')
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: '다음 7일 예보 보기' }).click()
  await expect(page.getByRole('group', { name: '7일 기상 예보' }).getByRole('button').first()).toHaveAccessibleName(/^6\/30\(월\) 예보/)
  expect(errors, '콘솔 오류·외부 요청').toEqual([])
})

test('모바일 폭(390px)에서 기상 예보 띠 8칸이 화면 안에 다 들어감', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const errors = await open(page, '/')
  const strip = page.getByRole('group', { name: '7일 기상 예보' })
  await expect(strip.getByRole('button')).toHaveCount(8)
  const fit = await page.evaluate(() => {
    const w = document.documentElement.clientWidth
    const cells = [...document.querySelectorAll('[aria-label="7일 기상 예보"] button')]
    return {
      page: document.documentElement.scrollWidth <= w, // 화면 전체가 옆으로 밀리지 않음
      cells: cells.every((c) => {
        const r = c.getBoundingClientRect()
        return r.left >= 0 && r.right <= w && c.scrollWidth <= c.clientWidth + 1 // 칸이 화면 안, 내용이 칸 안
      }),
      pager: (() => {
        const r = document.querySelector('button[aria-label="지난 7일 관측 보기"]')?.getBoundingClientRect()
        return !!r && r.left >= 0 // 넘김 버튼도 화면 안
      })(),
    }
  })
  expect(fit).toEqual({ page: true, cells: true, pager: true })
  expect(errors, '콘솔 오류·외부 요청').toEqual([])
})
