// README 화면 구성용 기능별 GIF: 기능 영역만 잘라(2배 해상도) 녹화하고, 아래에 자막 띠를 붙여 GIF로 만든다
// 사용 (프로젝트 루트): node docs/readme/make_gifs.cjs <서버 주소> [--dist <화면 빌드 폴더>] [장면 id ...]
//   서버: uv run uvicorn app.main:app --app-dir backend --port 8011 (사전 계산 결과 필요)
//   --dist를 주면 화면 파일은 그 폴더에서, /api만 서버에서 받는다 (frontend/dist를 다시 빌드하지 않고 찍을 때)
//   필요: frontend/node_modules(Playwright), ffmpeg. 결과: docs/readme/NN-id.gif
const fs = require('fs')
const os = require('os')
const path = require('path')
const { execFileSync } = require('child_process')

const ROOT = path.resolve(__dirname, '../..')
const { chromium } = require(path.join(ROOT, 'frontend/node_modules/playwright'))
const args = process.argv.slice(2)
const BASE = args[0].replace(/\/$/, '')
const di = args.indexOf('--dist')
const DIST = di > 0 ? path.resolve(args[di + 1]) : null
const ONLY = args.slice(1).filter((a, i, all) => a !== '--dist' && all[i - 1] !== '--dist')
const OUT = __dirname
const GIF_W = 960
const FPS = 12
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.png': 'image/png' }

// 헤드리스 화면에는 커서가 안 찍혀서 커서와 클릭 효과를 직접 그린다 (발표자료/영상편집/record.cjs와 같은 모양)
const CURSOR = `
addEventListener('DOMContentLoaded', () => {
  const st = document.createElement('style')
  st.textContent = '@keyframes __rip{0%{transform:translate(-50%,-50%) scale(.15);opacity:1}60%{opacity:.9}100%{transform:translate(-50%,-50%) scale(1);opacity:0}}'
  document.head.appendChild(st)
  const c = document.createElement('div')
  c.innerHTML = '<svg width="30" height="30" viewBox="0 0 28 28"><path d="M4 2 L4 22 L9.5 17 L13 25 L16.5 23.5 L13 15.8 L20.5 15.8 Z" fill="#14141f" stroke="#fff" stroke-width="1.7" stroke-linejoin="round"/></svg>'
  Object.assign(c.style, { position: 'fixed', left: 0, top: 0, zIndex: 2147483647, pointerEvents: 'none',
    transform: 'translate(-60px,-60px)', filter: 'drop-shadow(0 1px 2px rgba(0,0,0,.35))' })
  document.documentElement.appendChild(c)
  addEventListener('mousemove', (e) => { c.style.transform = 'translate(' + (e.clientX - 4) + 'px,' + (e.clientY - 2) + 'px)' }, true)
  addEventListener('mousedown', (e) => {
    for (const [size, look, ms] of [[60, 'background:rgba(255,122,26,.55)', 600], [92, 'border:4px solid #ff7a1a', 800]]) {
      const r = document.createElement('div')
      r.style.cssText = 'position:fixed;left:' + e.clientX + 'px;top:' + e.clientY + 'px;width:' + size + 'px;height:' + size + 'px;' +
        'border-radius:50%;box-sizing:border-box;z-index:2147483646;pointer-events:none;' + look + ';animation:__rip ' + ms + 'ms ease-out forwards'
      document.documentElement.appendChild(r)
      setTimeout(() => r.remove(), ms + 50)
    }
  }, true)
})`

const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2)
const box = async (l) => {
  const b = await l.boundingBox()
  if (!b) throw new Error('영역을 찾지 못함: ' + l)
  return b
}
const union = (...bs) => {
  const x = Math.min(...bs.map((b) => b.x)), y = Math.min(...bs.map((b) => b.y))
  return { x, y, width: Math.max(...bs.map((b) => b.x + b.width)) - x, height: Math.max(...bs.map((b) => b.y + b.height)) - y }
}
const pad = (b, l, t = l, r = l, btm = t) => ({ x: b.x - l, y: b.y - t, width: b.width + l + r, height: b.height + t + btm })
const region = (p, name) => p.getByRole('region', { name, exact: true })
const popover = (trigger) => trigger.locator('xpath=..').locator(':scope > *').last()

// 장면: 화면 크기·주소, 녹화 영역(region), 스크롤 기준(scroll), 동작(run). 자막은 제목 한 줄 + 설명 한 줄
const SCENES = [
  {
    id: 'period', title: '기준일과 기간을 고르면 모든 숫자가 그 시점으로 바뀝니다',
    sub: '최신 · 시연 시나리오 · 다음 7일 · 한 달 · 분기 (기간 직접 지정도 가능)',
    vw: 1280, vh: 860, url: '/',
    region: async (p) => {
      const trig = p.locator('button[aria-haspopup="dialog"]')
      await trig.nth(0).click()
      const a = await box(popover(trig.nth(0)))
      await p.keyboard.press('Escape')
      const h = await box(p.getByRole('heading', { name: '민원 운영 대시보드' }))
      return { x: 16, y: h.y - 18, width: 1248, height: a.y + a.height + 14 - (h.y - 18) }
    },
    run: async (p, r) => {
      const trig = p.locator('button[aria-haspopup="dialog"]')
      await r.hold(0.8)
      await r.click(trig.nth(0))
      await r.hold(0.9)
      await r.click(p.locator('button[aria-label^="최신 · 시연 시나리오"]'))
      await r.hold(0.7)
      await r.click(p.getByRole('option', { name: /폭염/ }).first())
      await r.hold(1.6)
      await r.click(trig.nth(1))
      await r.hold(1.0)
      await r.click(popover(trig.nth(1)).getByText('다음 한 달', { exact: true }))
      await r.hold(2.2)
    },
  },
  {
    id: 'weather-strip', title: '앞으로 7일 날씨와 특보 수준을 한 줄로 봅니다',
    sub: '빨강 아이콘은 경보 · 주황은 주의보 수준 · ‹ 를 누르면 지난 7일 실제 관측',
    vw: 1440, vh: 900, url: '/?asof=2025-06-20&start=2025-06-20&end=2025-06-26',
    region: async (p) => {
      const now = union(await box(p.getByRole('group', { name: '7일 기상 예보' })), await box(p.getByRole('button', { name: '지난 7일 관측 보기' })))
      await p.getByRole('button', { name: '지난 7일 관측 보기' }).click()
      await p.waitForTimeout(500)
      const past = union(await box(p.getByRole('group', { name: '지난 7일 관측 날씨' })), await box(p.getByRole('button', { name: '다음 7일 예보 보기' })))
      return pad(union(now, past), 16, 14)
    },
    run: async (p, r) => {
      const cells = p.getByRole('group', { name: '7일 기상 예보' }).getByRole('button')
      await r.hold(0.8)
      await r.ring(union(await box(cells.nth(2)), await box(cells.nth(4))))
      for (const i of [2, 3, 4]) {
        await r.move(cells.nth(i), 0.45)
        await r.hold(0.5)
      }
      await r.ring(null)
      await r.click(p.getByRole('button', { name: '지난 7일 관측 보기' }))
      await r.hold(2.4)
      await r.click(p.getByRole('button', { name: '다음 7일 예보 보기' }))
      await r.hold(1.2)
    },
  },
  {
    id: 'weather-day', title: '특보 날을 누르면 과거 7년 같은 특보 때의 민원을 보여 줍니다',
    sub: '해마다 접수 · 늘어난 건수 · 기간 안 처리 · 미처리 (소화전 · 수돗물 전환)',
    vw: 1440, vh: 900, url: '/?asof=2025-06-20&start=2025-06-20&end=2025-06-26',
    region: async (p) => {
      await p.getByRole('group', { name: '7일 기상 예보' }).getByRole('button').nth(2).click()
      await p.waitForTimeout(900)
      return box(p.getByRole('dialog').first())
    },
    run: async (p, r) => {
      const day = p.getByRole('group', { name: '7일 기상 예보' }).getByRole('button').nth(2)
      await r.hold(0.6)
      await r.ring(pad(await box(day), 2))
      await r.click(day)
      await r.ring(null)
      await r.hold(1.8)
      await r.move(p.getByRole('dialog').getByText('2024', { exact: true }).first(), 0.6)
      await r.hold(0.8)
      await r.click(p.getByRole('group', { name: '대상 민원' }).getByRole('button', { name: '수돗물' }))
      await r.hold(2.2)
    },
  },
  {
    id: 'kpi', title: '고른 기간을 숫자 6개로 요약합니다',
    sub: '예상 접수 · 기상 특보 예보 · 지원 가능 부서 · 집중관리 부서 · 처리 중 민원 · 지원 필요 인원',
    vw: 1024, vh: 900, url: '/?asof=2024-07-01&start=2024-07-01&end=2024-07-07',
    region: async (p) => pad(await box(p.locator('[aria-busy]')), 0, 0, -18, 0), // 오른쪽 끝 그림자 제외
    run: async (p, r) => {
      const tiles = p.locator('[aria-busy] > *')
      await r.hold(0.8)
      for (let i = 0; i < 6; i++) {
        await r.ring(pad(await box(tiles.nth(i)), -4))
        await r.move(tiles.nth(i), 0.4)
        await r.hold(0.9)
      }
      await r.ring(null)
      await r.hold(0.6)
    },
  },
  {
    id: 'staffing', title: '바쁜 부서와 여유 있는 부서를 짝지어 인력 지원을 권합니다',
    sub: '1인당 하루 처리 건수(가정값)를 바꾸면 필요 인원이 다시 계산됩니다',
    vw: 1440, vh: 900, url: '/?asof=2024-07-01&start=2024-07-01&end=2024-07-07', scroll: (p) => region(p, '인력 지원 권고'),
    region: async (p) => { // 패널 아래 빈칸은 빼고 가정값 줄까지
      const s = await box(region(p, '인력 지원 권고'))
      const plus = await box(region(p, '인력 지원 권고').getByRole('button', { name: '1인당 하루 처리 건수 늘리기' }))
      return { ...s, height: plus.y + plus.height + 22 - s.y }
    },
    run: async (p, r) => {
      const s = region(p, '인력 지원 권고')
      await r.hold(0.8)
      await r.move(s.getByText('교통국').first(), 0.6)
      await r.hold(0.8)
      await r.move(s.getByText('건축국').first(), 0.4)
      await r.hold(0.7)
      const plus = s.getByRole('button', { name: '1인당 하루 처리 건수 늘리기' })
      await r.click(plus)
      await r.hold(0.8)
      await r.click(plus, 0.2)
      await r.hold(1.4)
      const minus = s.getByRole('button', { name: '1인당 하루 처리 건수 줄이기' })
      await r.click(minus)
      await r.hold(0.4)
      await r.click(minus, 0.2)
      await r.hold(1.2)
    },
  },
  {
    id: 'matrix', title: '접수 증가와 적체로 8개 부서의 위험을 한눈에 봅니다',
    sub: '오른쪽 위 집중관리 · 왼쪽 아래 지원 가능 · 원 크기는 처리 중 민원 · ×는 실제 결과',
    vw: 1440, vh: 900, url: '/?asof=2024-07-01&start=2024-07-01&end=2024-07-07', scroll: (p) => region(p, '부서 위험 매트릭스'),
    region: async (p) => pad(await box(region(p, '부서 위험 매트릭스')), 0, 0, -24, 0),
    run: async (p, r) => {
      const at = (x, y) => ({ x: r.clip.x + x, y: r.clip.y + y }) // 패널 왼쪽 위 기준 원 위치
      await r.hold(0.8)
      await r.move(at(625, 410), 0.7) // 환경보호국 (집중관리, 기상 특보)
      await r.hold(1.8)
      await r.move(at(191, 445), 0.7) // 교통국 (지원 가능)
      await r.hold(1.5)
      await r.move(at(258, 155), 0.6) // 노숙자서비스국 (처리지연 주의)
      await r.hold(1.5)
      await r.move(at(420, 610), 0.5)
      await r.hold(0.5)
    },
  },
  {
    id: 'forecast', title: '지난 2주 실적에 이어 앞으로의 접수를 예측합니다',
    sub: '진한 막대는 기상 특보 예보일 · 빗금은 80% 범위 상한 · 짧은 선은 실제 건수',
    vw: 1440, vh: 900, url: '/?asof=2025-06-20&start=2025-06-20&end=2025-06-26', scroll: (p) => region(p, '예상 접수 추이'),
    region: async (p) => box(region(p, '예상 접수 추이')),
    run: async (p, r) => {
      const at = (x, y) => ({ x: r.clip.x + x, y: r.clip.y + y }) // 패널 왼쪽 위 기준 막대 위치
      await r.hold(0.8)
      await r.move(at(320, 395), 0.6) // 지난 실적
      await r.hold(1.0)
      await r.move(at(544, 395), 0.6) // 6/22 경보 예보일
      await r.hold(1.6)
      await r.move(at(600, 330), 0.5) // 6/24 실제 3,000건 이상
      await r.hold(1.8)
      await r.move(at(360, 470), 0.5)
      await r.hold(0.4)
    },
  },
  {
    id: 'issues', title: '어떤 민원이 언제 몰릴지 미리 짚어 줍니다',
    sub: '단기는 기상 특보 예보 · 장기는 같은 시기 과거 급증 빈도 · 아래는 실제로 급증한 이슈',
    vw: 1440, vh: 900, url: '/?asof=2025-06-20&start=2025-06-20&end=2025-06-26', scroll: (p) => region(p, '예상 이슈'),
    region: async (p) => pad(await box(region(p, '예상 이슈')), 0, 0, -24, 0),
    run: async (p, r) => {
      const s = region(p, '예상 이슈')
      // 글자를 감싼 카드(테두리 있는 둥근 상자)를 강조
      const card = (l) => l.evaluate((e) => {
        for (let n = e; n && n !== document.body; n = n.parentElement) {
          const c = getComputedStyle(n), b = n.getBoundingClientRect()
          if (parseFloat(c.borderTopWidth) > 0 && parseFloat(c.borderTopLeftRadius) >= 8 && b.height > 40) return { x: b.x, y: b.y, width: b.width, height: b.height }
        }
        return null
      })
      await r.hold(0.8)
      for (const [l, sec] of [[s.getByText('폭염경보', { exact: true }).first(), 1.4], [s.getByText('폭염·소화전 급증', { exact: true }).first(), 1.3],
        [s.getByText('그 밖의 이슈', { exact: true }).first(), 1.1], [s.getByText(/향후 7일 기상 특보 예보/).first(), 1.5]]) {
        await r.ring(await card(l))
        await r.move(l, 0.5)
        await r.hold(sec)
      }
      const actual = s.getByText('실제로 급증한 이슈').first()
      await r.ring(pad(await box(actual.locator('xpath=..')), 6))
      await r.move(actual, 0.5)
      await r.hold(1.6)
      await r.ring(null)
    },
  },
  {
    id: 'demo', title: '시연 모드로 대표 장면 5개를 차례로 보여 줍니다',
    sub: '평상시 한 달 → 폭염 → 블리자드 → 봄철 도로 파손 → 집중관리',
    vw: 1440, vh: 900, url: '/',
    region: async () => ({ x: 0, y: 76, width: 1416, height: 816 }),
    run: async (p, r) => {
      await r.hold(0.8)
      await r.click(p.getByRole('button', { name: '시연 모드' }))
      await r.hold(2.6)
      const next = p.getByRole('button', { name: '다음 단계', exact: true })
      await r.click(next, 0.8)
      await r.hold(2.6)
      await r.click(next, 0.3)
      await r.hold(2.8)
    },
  },
]

function recorder(p, clip, dir) {
  const frames = []
  const t0 = Date.now()
  const pos = { x: clip.x + clip.width * 0.62, y: clip.y + clip.height * 0.8 }
  let n = 0
  const shot = async () => {
    const f = path.join(dir, String(n++).padStart(4, '0') + '.jpg')
    await p.screenshot({ path: f, clip, type: 'jpeg', quality: 92 })
    frames.push([f, (Date.now() - t0) / 1000])
  }
  const hold = async (sec) => {
    const end = Date.now() + sec * 1000
    do await shot()
    while (Date.now() < end)
  }
  const center = async (t) => {
    if (t.x !== undefined) return t
    const b = await box(t)
    return { x: b.x + b.width / 2, y: b.y + b.height / 2 }
  }
  const move = async (t, sec = 0.6) => {
    const to = await center(t), from = { ...pos }, st = Date.now()
    for (;;) {
      const k = Math.min((Date.now() - st) / (sec * 1000), 1)
      await p.mouse.move(from.x + (to.x - from.x) * ease(k), from.y + (to.y - from.y) * ease(k))
      await shot()
      if (k >= 1) break
    }
    Object.assign(pos, to)
  }
  const click = async (t, sec = 0.6) => {
    await move(t, sec)
    await p.mouse.down()
    await p.mouse.up()
    await shot()
  }
  // 강조 테두리 (주황). null이면 지움
  const ring = (b) => p.evaluate((b) => {
    let el = document.getElementById('__ring')
    if (!b) return el && el.remove()
    if (!el) {
      el = document.createElement('div')
      el.id = '__ring'
      el.style.cssText = 'position:fixed;z-index:2147483640;pointer-events:none;border:3px solid #ff7a1a;border-radius:14px;' +
        'box-shadow:0 0 0 4px rgba(255,122,26,.18);transition:all .25s ease'
      document.documentElement.appendChild(el)
    }
    Object.assign(el.style, { left: b.x + 'px', top: b.y + 'px', width: b.width + 'px', height: b.height + 'px' })
  }, b)
  return { frames, clip, shot, hold, move, click, ring, start: () => p.mouse.move(pos.x, pos.y) }
}

// 앱 화면의 글꼴 정의를 그대로 쓰도록 문서는 두고 본문만 자막 띠로 바꾼다
async function band(p, i, sc, file) {
  await p.evaluate((html) => { document.body.innerHTML = html }, `<div id="b" style="width:${GIF_W}px;box-sizing:border-box;background:#1f1b4d;padding:16px 26px 18px;display:flex;gap:14px;align-items:flex-start;font-family:'Pretendard Variable',Pretendard,sans-serif">
    <div style="flex:none;width:32px;height:32px;border-radius:9px;background:#5b4fe0;color:#fff;font-size:17px;font-weight:700;line-height:32px;text-align:center">${i}</div>
    <div style="min-width:0"><div style="color:#fff;font-size:21px;font-weight:700;line-height:32px;letter-spacing:-.3px">${sc.title}</div>
    <div style="color:#cdc8f8;font-size:15.5px;line-height:1.45;margin-top:2px">${sc.sub}</div></div></div>`)
  await p.evaluate(() => document.fonts.ready)
  await p.waitForTimeout(200)
  await p.locator('#b').screenshot({ path: file })
}

function encode(frames, bandFile, dir, out) {
  let list = ''
  frames.forEach(([f, t], k) => {
    const next = k + 1 < frames.length ? frames[k + 1][1] : t + 0.1
    list += `file '${f}'\nduration ${Math.max(next - t, 0.02).toFixed(3)}\n`
  })
  list += `file '${frames[frames.length - 1][0]}'\n`
  fs.writeFileSync(path.join(dir, 'list.txt'), list)
  execFileSync('ffmpeg', ['-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', path.join(dir, 'list.txt'), '-framerate', String(FPS), '-loop', '1', '-i', bandFile,
    '-filter_complex',
    `[0:v]fps=${FPS},scale=${GIF_W}:-2:flags=lanczos,format=rgb24,setsar=1[v];[1:v]format=rgb24,setsar=1[b];` +
    `[v][b]vstack=inputs=2:shortest=1,fps=${FPS},split[a][c];[a]palettegen=max_colors=200:stats_mode=diff[pal];` +
    '[c][pal]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle',
    '-loop', '0', out])
}

;(async () => {
  const browser = await chromium.launch()
  const fontPage = await (await browser.newContext({ viewport: { width: GIF_W, height: 400 } })).newPage()
  const route = async (ctx) => {
    if (!DIST) return
    await ctx.route(BASE + '/**', (rt) => {
      const u = new URL(rt.request().url())
      if (u.pathname.startsWith('/api/')) return rt.continue()
      let f = path.join(DIST, decodeURIComponent(u.pathname))
      if (!fs.existsSync(f) || fs.statSync(f).isDirectory()) f = path.join(DIST, 'index.html')
      rt.fulfill({ status: 200, body: fs.readFileSync(f), contentType: TYPES[path.extname(f)] || 'application/octet-stream' })
    })
  }
  await route(fontPage.context())
  await fontPage.goto(BASE + '/') // 앱 글꼴(Pretendard)을 불러 둔 뒤 자막 띠를 그림
  await fontPage.evaluate(() => document.fonts.ready)

  for (const [k, sc] of SCENES.entries()) {
    if (ONLY.length && !ONLY.includes(sc.id)) continue
    const num = String(k + 1).padStart(2, '0')
    const tmp = fs.mkdtempSync(path.join(os.tmpdir(), `gif-${sc.id}-`))
    const ctx = await browser.newContext({ viewport: { width: sc.vw, height: sc.vh }, deviceScaleFactor: 2, locale: 'ko-KR', timezoneId: 'Asia/Seoul' })
    await route(ctx)
    await ctx.addInitScript(CURSOR)
    const p = await ctx.newPage()
    const setup = async () => {
      await p.goto(BASE + sc.url)
      await p.getByRole('heading', { name: '민원 운영 대시보드' }).waitFor()
      await p.waitForFunction(() => document.querySelectorAll('.skeleton').length === 0)
      await p.evaluate(() => document.fonts.ready)
      if (sc.scroll) {
        const y = await sc.scroll(p).evaluate((e) => e.getBoundingClientRect().top + window.scrollY)
        await p.evaluate((y) => window.scrollTo(0, y - 24), y)
      }
      await p.waitForTimeout(700)
    }
    await setup()
    const b = await sc.region(p)
    const clip = { x: Math.round(b.x), y: Math.round(b.y), width: Math.round(b.width), height: Math.round(b.height) }
    await setup() // 영역을 재느라 연 창을 닫고 처음 상태로
    const r = recorder(p, clip, tmp)
    await r.start()
    await sc.run(p, r)
    await ctx.close()
    const bandFile = path.join(tmp, 'band.png')
    await band(fontPage, k + 1, sc, bandFile)
    const out = path.join(OUT, `${num}-${sc.id}.gif`)
    encode(r.frames, bandFile, tmp, out)
    fs.rmSync(tmp, { recursive: true, force: true })
    const secs = r.frames[r.frames.length - 1][1].toFixed(1)
    console.log(`${num}-${sc.id}.gif  ${clip.width}x${clip.height} → ${GIF_W}px, ${r.frames.length}프레임, ${secs}초, ${(fs.statSync(out).size / 1048576).toFixed(2)}MB`)
  }
  await browser.close()
})()
