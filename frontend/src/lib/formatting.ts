import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import relativeTime from 'dayjs/plugin/relativeTime'

dayjs.extend(relativeTime)
dayjs.locale('zh-cn')

const numberFormatter = new Intl.NumberFormat('zh-CN')

export function formatNumber(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) {
    return '-'
  }
  return numberFormatter.format(value)
}

export function formatDate(value: string | Date | null | undefined): string {
  if (!value) {
    return '-'
  }
  const parsed = dayjs(value)
  if (!parsed.isValid()) {
    return '-'
  }
  return parsed.format('MM-DD HH:mm')
}

export function formatRelative(value: string | Date | null | undefined): string {
  if (!value) {
    return '-'
  }
  const parsed = dayjs(value)
  if (!parsed.isValid()) {
    return '-'
  }
  return parsed.fromNow()
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms)) {
    return '-'
  }
  if (ms < 1000) {
    return `${Math.max(0, Math.round(ms))} ms`
  }
  const seconds = ms / 1000
  if (seconds < 60) {
    return `${seconds.toFixed(1)} s`
  }
  const minutes = Math.floor(seconds / 60)
  const remaining = Math.round(seconds - minutes * 60)
  return `${minutes} m ${remaining} s`
}

export function truncate(text: string, max: number): string {
  if (text.length <= max) {
    return text
  }
  return `${text.slice(0, max)}…`
}

export function approxCharCount(text: string): string {
  return formatNumber(text.length)
}
