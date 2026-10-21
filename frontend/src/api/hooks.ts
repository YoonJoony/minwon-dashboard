import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { api, unwrap } from './client'

/** 화면 전체가 공유하는 조회 조건 */
export type Period = { asof: string; start: string; end: string }

const q = (p: Period) => ({ asof: p.asof, start: p.start, end: p.end })
// 기준일·기간을 바꾸는 동안 이전 화면을 유지해 깜빡임을 줄입니다.
const keep = { placeholderData: keepPreviousData }

export function useMeta() {
  return useQuery({
    queryKey: ['meta'],
    queryFn: async () => unwrap(await api.GET('/api/meta')),
    staleTime: Infinity,
  })
}

export function useSummary(p: Period, agency: string | null, perPersonDay: number) {
  return useQuery({
    queryKey: ['summary', p, agency, perPersonDay],
    queryFn: async () =>
      unwrap(
        await api.GET('/api/summary', {
          params: { query: { ...q(p), agency: agency ?? undefined, per_person_day: perPersonDay } },
        }),
      ),
    ...keep,
  })
}

export function useForecast(p: Period, agency: string | null) {
  return useQuery({
    queryKey: ['forecast', p, agency],
    queryFn: async () =>
      unwrap(await api.GET('/api/forecast', { params: { query: { ...q(p), agency: agency ?? undefined } } })),
    ...keep,
  })
}

export function useIssues(p: Period, agency: string | null) {
  return useQuery({
    queryKey: ['issues', p, agency],
    queryFn: async () =>
      unwrap(await api.GET('/api/issues', { params: { query: { ...q(p), agency: agency ?? undefined } } })),
    ...keep,
  })
}

export function useMatrix(p: Period) {
  return useQuery({
    queryKey: ['matrix', p],
    queryFn: async () => unwrap(await api.GET('/api/matrix', { params: { query: q(p) } })),
    ...keep,
  })
}

export function useStaffing(p: Period, perPersonDay: number) {
  return useQuery({
    queryKey: ['staffing', p, perPersonDay],
    queryFn: async () =>
      unwrap(await api.GET('/api/staffing', { params: { query: { ...q(p), per_person_day: perPersonDay } } })),
    ...keep,
  })
}

export function useEvidence() {
  return useQuery({
    queryKey: ['evidence'],
    queryFn: async () => unwrap(await api.GET('/api/evidence')),
    staleTime: Infinity,
  })
}

/** 7일 기상 예보 띠 (기준일마다) */
export function useWeatherStrip(asof: string) {
  return useQuery({
    queryKey: ['weather-strip', asof],
    queryFn: async () => unwrap(await api.GET('/api/weather/strip', { params: { query: { asof } } })),
    ...keep,
  })
}

/** 예보 띠에서 고른 날의 예보와 과거 7년 (모달을 열 때만) */
export function useWeatherDay(asof: string, date: string | null) {
  return useQuery({
    queryKey: ['weather-day', asof, date],
    queryFn: async () =>
      unwrap(await api.GET('/api/weather/day', { params: { query: { asof, date: date as string } } })),
    enabled: date !== null,
  })
}
