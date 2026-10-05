import type { Airport, Flight, FlightClass } from "../types"

// The backend has no currency field. Every price is shown in USD.
const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" })

export function formatMoney(value: string | number): string {
  const n = typeof value === "number" ? value : Number.parseFloat(value)
  return Number.isFinite(n) ? money.format(n) : "–"
}

/**
 * The API returns datetimes without an offset ("2030-01-01T08:00:00") but
 * they are UTC. `new Date()` would read an offset-less string as local time,
 * so append "Z" when no offset is present.
 */
export function parseApiDate(iso: string): Date {
  const hasOffset = /(Z|[+-]\d{2}:?\d{2})$/i.test(iso)
  return new Date(hasOffset ? iso : `${iso}Z`)
}

const timeFmt = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" })
const dateFmt = new Intl.DateTimeFormat(undefined, {
  weekday: "short",
  day: "numeric",
  month: "short",
  year: "numeric",
})
const shortDateFmt = new Intl.DateTimeFormat(undefined, {
  day: "numeric",
  month: "short",
  year: "numeric",
})
const dateTimeFmt = new Intl.DateTimeFormat(undefined, {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "numeric",
  minute: "2-digit",
})
const tzFmt = new Intl.DateTimeFormat(undefined, { timeZoneName: "short" })

export const formatTime = (iso: string) => timeFmt.format(parseApiDate(iso))
export const formatDate = (iso: string) => dateFmt.format(parseApiDate(iso))
export const formatShortDate = (iso: string) => shortDateFmt.format(parseApiDate(iso))
export const formatDateTime = (iso: string) => dateTimeFmt.format(parseApiDate(iso))

/** e.g. "PKT" or "GMT+5": shown once per page so local times are unambiguous. */
export function localTimeZoneLabel(): string {
  const part = tzFmt.formatToParts(new Date()).find((p) => p.type === "timeZoneName")
  return part?.value ?? "local time"
}

export function formatDuration(startIso: string, endIso: string): string {
  const minutes = Math.round(
    (parseApiDate(endIso).getTime() - parseApiDate(startIso).getTime()) / 60000,
  )
  if (minutes <= 0) return "–"
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return h === 0 ? `${m}m` : `${h}h ${String(m).padStart(2, "0")}m`
}

/** Days between departure and arrival in the viewer's time zone, for "+1" markers. */
export function dayOffset(startIso: string, endIso: string): number {
  const a = parseApiDate(startIso)
  const b = parseApiDate(endIso)
  const dayA = new Date(a.getFullYear(), a.getMonth(), a.getDate()).getTime()
  const dayB = new Date(b.getFullYear(), b.getMonth(), b.getDate()).getTime()
  return Math.round((dayB - dayA) / 86400000)
}

export function hasDeparted(flight: Flight): boolean {
  return parseApiDate(flight.start_time).getTime() <= Date.now()
}

export const CLASS_LABELS: Record<FlightClass, string> = {
  economy: "Economy",
  business: "Business",
  first: "First",
}

export function airportLabel(airport: Airport | undefined): string {
  return airport ? airport.city : "Unknown airport"
}

export function pluralize(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`
}

// ---------------------------------------------------------------- form <-> API

/** "2030-01-01T08:00:00" (UTC) -> "2030-01-01T13:00" for a datetime-local input in the viewer's zone. */
export function apiToLocalInput(iso: string): string {
  const d = parseApiDate(iso)
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/**
 * datetime-local value (viewer's zone) -> UTC ISO with explicit +00:00.
 * Always convert to UTC before sending: the backend drops non-UTC offsets
 * instead of converting them, so "+05:00" would be stored 5 hours off.
 */
export function localInputToApi(value: string): string {
  return new Date(value).toISOString().replace(/\.\d{3}Z$/, "+00:00")
}

/** yyyy-mm-dd from a date input -> UTC ISO for the start (or end) of that local day. */
export function localDateToApi(value: string, endOfDay = false): string {
  const [y, m, d] = value.split("-").map(Number)
  const date = endOfDay ? new Date(y, m - 1, d, 23, 59, 59) : new Date(y, m - 1, d, 0, 0, 0)
  return date.toISOString().replace(/\.\d{3}Z$/, "Z")
}
