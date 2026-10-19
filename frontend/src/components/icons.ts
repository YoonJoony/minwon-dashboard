import {
  CloudRain,
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
