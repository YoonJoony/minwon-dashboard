import { useEffect, useRef, useState } from 'react'

/** 요소 폭을 감시합니다. step 단위로 반올림해 크기를 조금 바꿀 때마다 다시 그리지 않게 합니다. */
export function useWidth<T extends HTMLElement>(initial: number, step = 20) {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(initial)
  useEffect(() => {
    const el = ref.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(([e]) => setWidth(Math.round(e.contentRect.width / step) * step))
    ro.observe(el)
    return () => ro.disconnect()
  }, [step])
  return [ref, width] as const
}
