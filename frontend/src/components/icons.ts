import {
  Cloud,
  CloudLightning,
  CloudRain,
  CloudRainWind,
  CloudSnow,
  CloudSun,
  Sun,
  Construction,
  Droplets,
  Flame,
  Heater,
  Lamp,
  Rat,
  Snowflake,
  Sparkles,
  Wind,
  type LucideIcon,
} from 'lucide-react'

/** 기상 특보 종류 → 아이콘 */
export const ALERT_ICON: Record<string, LucideIcon> = { heat: Flame, snow: Snowflake, wind: Wind, rain: CloudRain }

/** API의 이슈 카드 icon 이름 → 아이콘 */
export const ISSUE_ICON: Record<string, LucideIcon> = {
  flame: Flame,
  snowflake: Snowflake,
  wind: Wind,
  'cloud-rain': CloudRain,
  droplets: Droplets,
  construction: Construction,
  lamp: Lamp,
  rat: Rat,
  heater: Heater,
  sparkles: Sparkles,
}

/** 예보 띠 날씨 아이콘 (API icon 값 → 아이콘·색). 검증 문서 2-2의 6종 */
export const SKY_ICON: Record<string, { icon: LucideIcon; color: string }> = {
  clear: { icon: Sun, color: '#f59e0b' },
  partly: { icon: CloudSun, color: '#8b8fa3' },
  cloudy: { icon: Cloud, color: '#6b6b7b' },
  rain: { icon: CloudRain, color: '#3b82f6' },
  snow: { icon: CloudSnow, color: '#60a5fa' },
  thunder: { icon: CloudLightning, color: '#7c3aed' },
}

/** 예보 띠·모달의 특보 종류 아이콘 (호우는 일반 비 아이콘과 구분) */
export const WX_ALERT_ICON: Record<string, LucideIcon> = { heat: Flame, snow: Snowflake, wind: Wind, rain: CloudRainWind }

/** 특보 단계 색: 2 경보 · 1 주의보 · 0 예비특보 */
export const LEVEL_TONE: Record<number, { fg: string; bg: string; icon: string; word: string }> = {
  2: { fg: '#c2362d', bg: '#fdf0ef', icon: '#e0483f', word: '경보' },
  1: { fg: '#a35a07', bg: '#fdf5e8', icon: '#d97706', word: '주의보' },
  0: { fg: '#4a3fc7', bg: '#f0eefd', icon: '#5b4fe0', word: '예비특보' },
}
