import type { MatrixItem, MatrixOut } from '../api/client'
import { fmtInt, fmtMult, fmtPct } from '../lib/format'
import { C, QUADRANT_COLOR } from '../lib/theme'
import { FONT, tooltipBase, type EOption } from './useEChart'

type CustomApi = { value: (i: number) => number; coord: (v: number[]) => number[] }

/** 축 범위: 기준선과 모든 점·범위가 들어가되, 특보 부서처럼 범위가 아주 넓으면 끝에서 자르고 화살표로 표시 */
export function matrixBounds(items: MatrixItem[], th: { x: number; y: number; support_x: number }) {
  const lo = Math.min(th.support_x - 0.15, ...items.map((i) => Math.min(i.x_lo, i.x)))
  const hi = Math.max(th.x + 0.15, ...items.map((i) => Math.max(i.x_hi, i.x, i.x_actual ?? -Infinity)))
  const xmin = Math.max(-0.8, Math.floor((lo - 0.04) * 10) / 10)
  const xmax = Math.min(1.0, Math.ceil((hi + 0.04) * 10) / 10)
  const ys = items.map((i) => i.y)
  const lowY = Math.min(0.6, ...ys) - 0.1
  const highY = Math.max(th.y + 0.5, ...ys) + 0.2
  const yInterval = highY - lowY > 2.2 ? 0.5 : 0.25
  const ymin = Math.max(0, Math.floor(lowY / yInterval) * yInterval)
  const ymax = Math.ceil(highY / yInterval) * yInterval
  return { xmin, xmax, ymin, ymax, yInterval }
}

const GRID = { left: 64, right: 46, top: 18, bottom: 52 }
export const MATRIX_HEIGHT = 430

type Box = { x0: number; y0: number; x1: number; y1: number }
export type LabelPlace = { position: 'right' | 'left' | 'top' | 'bottom'; offset: [number, number] }

const area = (a: Box, b: Box) =>
  Math.max(0, Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0)) * Math.max(0, Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0))

/** 이름표 폭 추정 (12px 글꼴: 한글 약 12.5px, 그 밖 7px) */
export const labelWidth = (text: string, extra = 0) =>
  [...text].reduce((w, ch) => w + (/[\u3131-\uD79D]/.test(ch) ? 12.5 : 7), 0) + extra

/** 원과 이미 놓은 이름표에 덜 겹치는 쪽을 골라 이름표 위치를 정합니다 (큰 원부터). */
export function placeLabels(
  pts: { cx: number; cy: number; r: number; w: number }[],
  plot: Box,
  obstacles: Box[] = [],
): LabelPlace[] {
  const H = 16
  const GAP = 5
  const placed: Box[] = []
  const out: LabelPlace[] = pts.map(() => ({ position: 'right', offset: [0, 0] }))
  const circles = pts.map((p) => ({ x0: p.cx - p.r, y0: p.cy - p.r, x1: p.cx + p.r, y1: p.cy + p.r }))
  const order = pts.map((_, i) => i).sort((a, b) => pts[b].r - pts[a].r)
  for (const i of order) {
    const { cx, cy, r, w } = pts[i]
    const right = (dy: number): Box => ({ x0: cx + r + GAP, y0: cy - H / 2 + dy, x1: cx + r + GAP + w, y1: cy + H / 2 + dy })
    const left = (dy: number): Box => ({ x0: cx - r - GAP - w, y0: cy - H / 2 + dy, x1: cx - r - GAP, y1: cy + H / 2 + dy })
    const cands: { place: LabelPlace; box: Box; pref: number }[] = [
      { place: { position: 'right', offset: [0, 0] }, box: right(0), pref: 0 },
      { place: { position: 'left', offset: [0, 0] }, box: left(0), pref: 1 },
      { place: { position: 'top', offset: [0, 0] }, box: { x0: cx - w / 2, y0: cy - r - GAP - H, x1: cx + w / 2, y1: cy - r - GAP }, pref: 2 },
      { place: { position: 'bottom', offset: [0, 0] }, box: { x0: cx - w / 2, y0: cy + r + GAP, x1: cx + w / 2, y1: cy + r + GAP + H }, pref: 2 },
      { place: { position: 'right', offset: [0, -H] }, box: right(-H), pref: 3 },
      { place: { position: 'right', offset: [0, H] }, box: right(H), pref: 3 },
      { place: { position: 'left', offset: [0, -H] }, box: left(-H), pref: 4 },
      { place: { position: 'left', offset: [0, H] }, box: left(H), pref: 4 },
    ]
    let best = cands[0]
    let bestScore = Infinity
    for (const c of cands) {
      let score = c.pref * 6
      circles.forEach((b, j) => {
        if (j !== i) score += area(c.box, b)
      })
      for (const b of placed) score += area(c.box, b) * 3
      for (const b of obstacles) score += area(c.box, b) * 2
      const outside =
        Math.max(0, plot.x0 - c.box.x0) + Math.max(0, c.box.x1 - plot.x1) + Math.max(0, plot.y0 - c.box.y0) + Math.max(0, c.box.y1 - plot.y1)
      score += outside * H * 3
      if (score < bestScore) {
        bestScore = score
        best = c
      }
    }
    placed.push(best.box)
    out[i] = best.place
  }
  return out
}

/** 이름표 옆 작은 표시: 기상 특보 → '특보', 봄철 도로 파손 → '도로 파손' (둘 다면 특보 우선) */
export const flagBadge = (flag: string) =>
  flag.includes('기상 특보') ? '특보' : flag.includes('도로 파손') ? '도로 파손' : flag

export function matrixOption(m: MatrixOut, selected: string | null, width = 640): EOption {
  const th = m.thresholds
  const items = m.items
  const { xmin, xmax, ymin, ymax, yInterval } = matrixBounds(items, th)
  const clampX = (v: number) => Math.min(Math.max(v, xmin), xmax)
  const maxOpen = Math.max(1, ...items.map((i) => i.backlog_open))
  const size = (v: number) => 14 + 26 * Math.sqrt(Math.max(v, 0) / maxOpen)
  const hasActual = items.some((i) => i.x_actual != null)
  const xInterval = xmax - xmin > 1.2 ? 0.2 : 0.1

  // 화면 좌표로 바꿔 이름표 자리를 미리 계산
  const plot = { x0: GRID.left, y0: GRID.top, x1: width - GRID.right, y1: MATRIX_HEIGHT - GRID.bottom }
  const toPx = (x: number, y: number) => [
    plot.x0 + ((clampX(x) - xmin) / (xmax - xmin)) * (plot.x1 - plot.x0),
    plot.y0 + (1 - (y - ymin) / (ymax - ymin)) * (plot.y1 - plot.y0),
  ]
  const places = placeLabels(
    items.map((i) => {
      const [cx, cy] = toPx(i.x, i.y)
      return { cx, cy, r: size(i.backlog_open) / 2, w: labelWidth(i.short, i.flag ? labelWidth(flagBadge(i.flag), 14) : 0) }
    }),
    plot,
    // 실제 결과 × 표시도 이름표가 피해 갈 자리
    items.flatMap((i) => {
      if (i.x_actual == null) return []
      const [cx, cy] = toPx(i.x_actual, i.y)
      return [{ x0: cx - 7, y0: cy - 7, x1: cx + 7, y1: cy + 7 }]
    }),
  )

  const tip = (i: MatrixItem) => {
    const rows = [
      `<b style="font-size:13px">${i.name}</b> <span style="color:${QUADRANT_COLOR[i.quadrant]};font-weight:700">${i.quadrant}</span>`,
      `접수 증가율 <b>${fmtPct(i.x)}</b> <span style="color:${C.mute}">(80% 범위 ${fmtPct(i.x_lo, 0)} ~ ${fmtPct(i.x_hi, 0)})</span>`,
      `예상 접수 <b>${fmtInt(i.pred)}</b>건 <span style="color:${C.mute}">(최근 4주 기준 ${fmtInt(i.base)}건)</span>`,
      `적체 배수 <b>${fmtMult(i.y)}</b> <span style="color:${C.mute}">(처리 중 ${fmtInt(i.backlog_open)} ÷ 평소 ${fmtInt(i.backlog_normal)})</span>`,
    ]
    if (i.flag) rows.push(`<span style="color:#c2362d;font-weight:600">${i.flag}: ${i.flag_reason} → 범위 확대·지원 제외</span>`)
    if (i.actual != null)
      rows.push(
        `실제 <b>${fmtInt(i.actual)}</b>건 → ${fmtPct(i.x_actual)} · 실제 판정 <b>${i.quadrant_actual}</b> · ${i.in_range ? '80% 범위 안' : '<span style="color:#c2362d">범위 밖</span>'}`,
      )
    rows.push(`<span style="color:${C.faint}">원을 누르면 이 부서로 화면을 바꿉니다</span>`)
    return rows.join('<br/>')
  }

  const qLabel = (text: string, color: string, position: string) => ({
    show: true,
    position,
    formatter: text,
    color,
    fontSize: 12,
    fontWeight: 700,
    distance: 8,
  })

  return {
    animationDuration: 450,
    textStyle: { fontFamily: FONT },
    grid: GRID,
    tooltip: { ...tooltipBase, trigger: 'item', confine: true },
    xAxis: {
      type: 'value',
      min: xmin,
      max: xmax,
      interval: xInterval,
      name: '접수 증가율 (기간 예상 일평균 ÷ 최근 4주 일평균 − 1)',
      nameLocation: 'middle',
      nameGap: 32,
      nameTextStyle: { color: C.mute, fontSize: 12 },
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#8a8a9a', fontSize: 11, formatter: (v: number) => fmtPct(v, 0) },
      splitLine: { lineStyle: { color: C.grid } },
    },
    yAxis: {
      type: 'value',
      min: ymin,
      max: ymax,
      interval: yInterval,
      name: '적체 배수 (처리 중 ÷ 평소)',
      nameLocation: 'middle',
      nameGap: 46,
      nameTextStyle: { color: C.mute, fontSize: 12 },
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#8a8a9a', fontSize: 11, formatter: (v: number) => `${Number(v.toFixed(2))}배` },
      splitLine: { lineStyle: { color: C.grid } },
    },
    series: [
      {
        // 접수 증가율 80% 범위 (가로 막대)
        name: '범위',
        type: 'custom',
        silent: true,
        z: 2,
        data: items.map((i) => [clampX(i.x_lo), clampX(i.x_hi), i.y, i.x_hi > xmax ? 1 : 0, i.x_lo < xmin ? 1 : 0]),
        renderItem: (params: { dataIndex: number }, api: CustomApi) => {
          const it = items[params.dataIndex]
          const color = QUADRANT_COLOR[it.quadrant]
          const a = api.coord([api.value(0), api.value(2)])
          const b = api.coord([api.value(1), api.value(2)])
          const dim = selected !== null && selected !== it.agency
          const style = { stroke: color, lineWidth: 2.5, opacity: dim ? 0.18 : 0.45, lineCap: 'round' }
          const children: object[] = [{ type: 'line', shape: { x1: a[0], y1: a[1], x2: b[0], y2: b[1] }, style }]
          if (!api.value(4)) children.push({ type: 'line', shape: { x1: a[0], y1: a[1] - 5, x2: a[0], y2: a[1] + 5 }, style })
          if (api.value(3))
            children.push({
              type: 'polygon',
              shape: { points: [[b[0], b[1]], [b[0] - 8, b[1] - 5], [b[0] - 8, b[1] + 5]] },
              style: { fill: color, opacity: dim ? 0.2 : 0.6 },
            })
          else children.push({ type: 'line', shape: { x1: b[0], y1: b[1] - 5, x2: b[0], y2: b[1] + 5 }, style })
          return { type: 'group', children }
        },
      },
      {
        name: '부서',
        type: 'scatter',
        z: 4,
        cursor: 'pointer',
        data: items.map((i, k) => {
          const dim = selected !== null && selected !== i.agency
          const sel = selected === i.agency
          return {
            value: [clampX(i.x), i.y],
            symbolSize: size(i.backlog_open),
            itemStyle: {
              color: QUADRANT_COLOR[i.quadrant],
              opacity: dim ? 0.35 : 0.93,
              borderColor: i.flag ? C.ink : '#ffffff',
              borderWidth: sel ? 3.5 : i.flag ? 2 : 2,
              borderType: i.flag ? [4, 3] : 'solid',
              shadowBlur: sel ? 14 : 0,
              shadowColor: 'rgba(91,79,224,0.45)',
            },
            label: {
              show: true,
              position: places[k].position,
              offset: places[k].offset,
              distance: 5,
              formatter: i.flag ? `{n|${i.short}} {f|${flagBadge(i.flag)}}` : `{n|${i.short}}`,
              rich: {
                n: {
                  color: dim ? C.faint : C.ink,
                  fontSize: 12,
                  fontWeight: sel ? 800 : 600,
                  textBorderColor: '#ffffff',
                  textBorderWidth: 3,
                },
                f: { color: '#fff', backgroundColor: C.ink, borderRadius: 4, padding: [2, 4], fontSize: 10, fontWeight: 700 },
              },
            },
          }
        }),
        tooltip: { formatter: (p: { dataIndex: number }) => tip(items[p.dataIndex]) },
        emphasis: { scale: 1.08, focus: 'none' },
        markArea: {
          silent: true,
          data: [
            [
              { xAxis: th.x, yAxis: th.y, itemStyle: { color: 'rgba(229,72,77,0.07)' }, label: qLabel('▲ 집중관리', '#c9363b', 'insideTopRight') },
              { xAxis: xmax, yAxis: ymax },
            ],
            [
              { xAxis: xmin, yAxis: th.y, itemStyle: { color: 'rgba(227,155,45,0.05)' }, label: qLabel('처리지연 주의', '#b77412', 'insideTopLeft') },
              { xAxis: th.x, yAxis: ymax },
            ],
            [
              { xAxis: th.x, yAxis: ymin, itemStyle: { color: 'rgba(239,131,84,0.05)' }, label: qLabel('접수증가 주의', '#c95f2f', 'insideBottomRight') },
              { xAxis: xmax, yAxis: th.y },
            ],
            [
              { xAxis: xmin, yAxis: ymin, itemStyle: { color: 'rgba(34,160,107,0.07)' }, label: qLabel('지원 가능', '#17834f', 'insideBottomLeft') },
              { xAxis: th.support_x, yAxis: th.y },
            ],
            [
              { xAxis: th.support_x, yAxis: ymin, itemStyle: { color: 'rgba(0,0,0,0)' }, label: qLabel('안정', '#8a8a9e', 'insideBottom') },
              { xAxis: th.x, yAxis: th.y },
            ],
          ],
        },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: '#9a9aae', type: [5, 4], width: 1 },
          label: { color: '#8a8a9a', fontSize: 11 },
          data: [
            { xAxis: th.x, label: { formatter: fmtPct(th.x, 0), position: 'end' } },
            { yAxis: th.y, label: { formatter: `${th.y}배`, position: 'end' } },
            [
              { coord: [th.support_x, ymin], lineStyle: { color: '#22a06b', type: [2, 4], width: 1.2 }, label: { show: false } },
              { coord: [th.support_x, th.y] },
            ],
          ],
        },
      },
      ...(hasActual
        ? [
            {
              name: '실제',
              type: 'scatter',
              z: 5,
              symbol:
                'path://M3.5,2 L6,4.5 L8.5,2 L10,3.5 L7.5,6 L10,8.5 L8.5,10 L6,7.5 L3.5,10 L2,8.5 L4.5,6 L2,3.5 Z',
              symbolSize: 11,
              itemStyle: { color: C.navy, opacity: 0.85 },
              data: items
                .filter((i) => i.x_actual != null)
                .map((i) => ({
                  value: [clampX(i.x_actual as number), i.y],
                  name: i.agency,
                  label:
                    (i.x_actual as number) > xmax
                      ? { show: true, position: 'top', formatter: `실제 ${fmtPct(i.x_actual, 0)} →`, color: C.navy, fontSize: 10, fontWeight: 700 }
                      : undefined,
                })),
              tooltip: {
                formatter: (p: { name: string }) => {
                  const it = items.find((x) => x.agency === p.name)
                  return it ? `<b>${it.name}</b> 실제 접수 증가율 <b>${fmtPct(it.x_actual)}</b><br/>실제 판정 ${it.quadrant_actual}` : ''
                },
              },
            },
          ]
        : []),
    ],
  }
}
