import dayjs, { type Dayjs } from 'dayjs'
import type { SummaryRange } from '../api/types'

type DateInput = string | number | Date | Dayjs

function toDate(value: DateInput): Date {
  return dayjs(value).toDate()
}

export function formatNumber(
  value: number | null | undefined,
  locale: string,
  options: Intl.NumberFormatOptions = {},
): string {
  if (value == null || Number.isNaN(value)) return '—'
  return new Intl.NumberFormat(locale, {
    maximumFractionDigits: 0,
    ...options,
  }).format(value)
}

export function formatDecimal(
  value: number | null | undefined,
  locale: string,
  digits = 1,
): string {
  if (value == null || Number.isNaN(value)) return '—'
  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value)
}

export function formatDuration(
  minutes: number | null | undefined,
  locale: string,
): string {
  if (minutes == null || Number.isNaN(minutes)) return '—'
  const total = Math.max(0, Math.round(minutes))
  const hours = Math.floor(total / 60)
  const rest = total % 60
  if (locale.startsWith('zh')) {
    if (hours > 0 && rest > 0) return `${hours} 小时 ${rest} 分`
    if (hours > 0) return `${hours} 小时`
    return `${rest} 分钟`
  }
  if (hours > 0 && rest > 0) return `${hours}h ${rest}m`
  if (hours > 0) return `${hours}h`
  return `${rest}m`
}

export function workoutDurationSeconds(workout: {
  durationMinutes: number
  startAt: string
  endAt: string
}): number {
  const fallback = Math.max(0, Math.round(workout.durationMinutes * 60))
  const start = Date.parse(workout.startAt)
  const end = Date.parse(workout.endAt)
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
    return fallback
  }
  const seconds = Math.round((end - start) / 1000)
  if (seconds > 86400) return fallback
  // Reject timezone/clock glitches. Real pauses stay well inside this bound.
  const limit = Math.max(fallback * 2, fallback + 3600)
  return seconds <= limit ? seconds : fallback
}

export function formatDurationClock(seconds: number | null | undefined): string {
  if (seconds == null || Number.isNaN(seconds)) return '—'
  const total = Math.max(0, Math.round(seconds))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const rest = total % 60
  const mm = String(minutes).padStart(2, '0')
  const ss = String(rest).padStart(2, '0')
  if (hours > 0) return `${hours}:${mm}:${ss}`
  return `${minutes}:${ss}`
}

export function formatDistance(
  meters: number | null | undefined,
  locale: string,
): string {
  if (meters == null || Number.isNaN(meters)) return '—'
  return `${formatDecimal(meters / 1000, locale, meters >= 10000 ? 1 : 2)} km`
}

export function formatPace(
  secondsPerKm: number | null | undefined,
  locale: string,
): string {
  if (secondsPerKm == null || Number.isNaN(secondsPerKm)) return '—'
  const total = Math.max(0, Math.round(secondsPerKm))
  const minutes = Math.floor(total / 60)
  const seconds = total % 60
  const unit = locale.startsWith('zh') ? '/公里' : '/km'
  return `${minutes}'${String(seconds).padStart(2, '0')}"${unit}`
}

export function formatSpeed(
  metersPerSecond: number | null | undefined,
  locale: string,
): string {
  if (metersPerSecond == null || Number.isNaN(metersPerSecond)) return '—'
  return `${formatDecimal(metersPerSecond * 3.6, locale, 1)} km/h`
}

export function formatDate(
  value: DateInput,
  locale: string,
  options: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric' },
): string {
  return new Intl.DateTimeFormat(locale, options).format(toDate(value))
}

export function formatFullDate(value: DateInput, locale: string): string {
  const date = formatDate(value, locale, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
  return `${date} · ${formatWeekday(value, locale)}`
}

export function formatMonthYear(value: DateInput, locale: string): string {
  return formatDate(value, locale, { year: 'numeric', month: 'long' })
}

export function formatYear(value: DateInput, locale: string): string {
  return formatDate(value, locale, { year: 'numeric' })
}

export function formatTime(value: DateInput, locale: string): string {
  return formatDate(value, locale, {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

export function formatDateTime(value: DateInput, locale: string): string {
  return `${formatDate(value, locale, {
    month: 'short',
    day: 'numeric',
  })} · ${formatTime(value, locale)}`
}

export function formatWeekday(value: DateInput, locale: string): string {
  return formatDate(value, locale, { weekday: 'short' })
}

export function rangeBounds(range: SummaryRange, anchor: DateInput): [Dayjs, Dayjs] {
  const base = dayjs(anchor).startOf('day')
  switch (range) {
    case 'day':
      return [base, base.endOf('day')]
    case 'week': {
      const mondayOffset = (base.day() + 6) % 7
      const start = base.subtract(mondayOffset, 'day').startOf('day')
      return [start, start.add(6, 'day').endOf('day')]
    }
    case 'month':
      return [base.startOf('month'), base.endOf('month')]
    case 'year':
      return [base.startOf('year'), base.endOf('year')]
  }
}

export function formatRangeLabel(
  range: SummaryRange,
  anchor: DateInput,
  locale: string,
): string {
  const [start, end] = rangeBounds(range, anchor)
  switch (range) {
    case 'day':
      return formatDate(start, locale, {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        weekday: 'short',
      })
    case 'week':
      return `${formatDate(start, locale, {
        month: 'short',
        day: 'numeric',
      })} – ${formatDate(end, locale, {
        month: 'short',
        day: 'numeric',
      })}`
    case 'month':
      return formatMonthYear(start, locale)
    case 'year':
      return formatYear(start, locale)
  }
}

export function formatBucketLabel(
  range: SummaryRange,
  key: string,
  locale: string,
): string {
  switch (range) {
    case 'day':
      return formatDate(key, locale, { month: 'short', day: 'numeric' })
    case 'week':
      return formatWeekday(key, locale)
    case 'month':
      return String(dayjs(key).date())
    case 'year':
      return formatDate(key, locale, { month: 'short' })
  }
}

export function greetingKey(hour: number): 'morning' | 'afternoon' | 'evening' {
  if (hour < 12) return 'morning'
  if (hour < 18) return 'afternoon'
  return 'evening'
}
