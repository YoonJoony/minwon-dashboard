import { BarChart, CustomChart, ScatterChart } from 'echarts/charts'
import { GridComponent, MarkAreaComponent, MarkLineComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { useEffect, useRef } from 'react'

// 필요한 차트 종류만 묶어 번들 크기를 줄입니다.
echarts.use([BarChart, ScatterChart, CustomChart, GridComponent, TooltipComponent, MarkAreaComponent, MarkLineComponent, CanvasRenderer])

export type EOption = echarts.EChartsCoreOption
export type EClick = (p: { seriesName?: string; dataIndex: number; data: unknown }) => void

/** div에 ECharts를 붙이고, 크기 변화·옵션 변경·클릭을 처리합니다. */
export function useEChart(option: EOption | null, onClick?: EClick) {
  const ref = useRef<HTMLDivElement>(null)
  const chart = useRef<echarts.ECharts | null>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const c = echarts.init(el, undefined, { renderer: 'canvas' })
    chart.current = c
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(() => c.resize()) : null
    ro?.observe(el)
    return () => {
      ro?.disconnect()
      c.dispose()
      chart.current = null
    }
  }, [])

  useEffect(() => {
    if (option && chart.current) chart.current.setOption(option, { notMerge: true })
  }, [option])

  useEffect(() => {
    const c = chart.current
    if (!c || !onClick) return
    const h = (p: unknown) => onClick(p as Parameters<EClick>[0])
    c.on('click', h)
    return () => {
      c.off('click', h)
    }
  }, [onClick])

  return ref
}

/** 툴팁 공통 모양 */
export const tooltipBase = {
  backgroundColor: '#ffffff',
  borderColor: '#e6e6ee',
  borderWidth: 1,
  padding: [10, 12],
  textStyle: { color: '#16161d', fontSize: 12, fontFamily: 'Pretendard Variable, Pretendard, sans-serif' },
  extraCssText: 'border-radius:12px;box-shadow:0 10px 30px -12px rgba(22,22,29,.25);',
}

export const FONT = 'Pretendard Variable, Pretendard, -apple-system, sans-serif'
