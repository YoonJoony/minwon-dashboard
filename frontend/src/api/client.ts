import createClient from 'openapi-fetch'
import type { components, paths } from './schema'

export const api = createClient<paths>({ baseUrl: '' })

type S = components['schemas']
export type Meta = S['Meta']
export type Agency = S['Agency']
export type Scenario = S['Scenario']
export type SummaryOut = S['SummaryOut']
export type ForecastOut = S['ForecastOut']
export type SeriesPoint = S['SeriesPoint']
export type IssuesOut = S['IssuesOut']
export type IssueCard = S['IssueCard']
export type MatrixOut = S['MatrixOut']
export type MatrixItem = S['MatrixItem']
export type StaffingOut = S['StaffingOut']
export type RiskOut = S['RiskOut']
export type EvidenceOut = S['EvidenceOut']

/** API 오류를 한국어 메시지로 바꿔 던집니다. */
export function unwrap<T>(res: { data?: T; error?: unknown; response: Response }): T {
  if (res.data !== undefined) return res.data
  const err = res.error as { detail?: unknown } | undefined
  const detail = typeof err?.detail === 'string' ? err.detail : `서버 응답 오류 (${res.response.status})`
  throw new Error(detail)
}
