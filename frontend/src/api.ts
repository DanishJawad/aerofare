import type {
  Airport,
  AirportInput,
  Booking,
  BookingInput,
  Flight,
  FlightInput,
  FlightSearchParams,
  PasswordChange,
  Payment,
  SignupInput,
  TokenResponse,
  User,
  UserUpdate,
  ValidationIssue,
} from "./types"

const BASE_URL = import.meta.env.VITE_API_URL
const TOKEN_KEY = "aerofare.token"

// ---------------------------------------------------------------- token storage

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

// The auth layer registers this so a 401 anywhere can send the user to /login
// through the router instead of a full page reload.
let onUnauthorized: (() => void) | null = null

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler
}

// ---------------------------------------------------------------- errors

/**
 * Normalised error for every failed request.
 * `message` is always safe to show to a user. `fieldErrors` maps a request
 * field name to its 422 message so forms can show it under the right input.
 */
export class ApiError extends Error {
  readonly status: number
  readonly fieldErrors: Record<string, string>

  constructor(status: number, message: string, fieldErrors: Record<string, string> = {}) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.fieldErrors = fieldErrors
  }
}

function cleanMessage(msg: string): string {
  // Pydantic prefixes model_validator errors with "Value error, ".
  const text = msg.replace(/^Value error,\s*/i, "")
  return text.charAt(0).toUpperCase() + text.slice(1)
}

function fallbackMessage(status: number): string {
  if (status === 403) return "You don't have permission to do that."
  if (status === 404) return "We couldn't find what you were looking for."
  if (status >= 500) return "The server ran into a problem. Try again in a moment."
  return `Something went wrong (error ${status}).`
}

async function toApiError(res: Response): Promise<ApiError> {
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    // Non-JSON error body, fall through to a generic message.
  }

  const detail = (body as { detail?: unknown } | null)?.detail

  if (typeof detail === "string") {
    return new ApiError(res.status, cleanMessage(detail))
  }

  if (Array.isArray(detail)) {
    const fieldErrors: Record<string, string> = {}
    const general: string[] = []
    for (const issue of detail as ValidationIssue[]) {
      // loc looks like ["body", "price"] for a field, or ["body"] for a
      // cross-field model_validator error.
      const field = issue.loc.length > 1 ? String(issue.loc[issue.loc.length - 1]) : null
      const msg = cleanMessage(issue.msg)
      if (field && !fieldErrors[field]) fieldErrors[field] = msg
      else if (!field) general.push(msg)
    }
    const message =
      general[0] ??
      (Object.keys(fieldErrors).length > 0
        ? "Some fields need attention."
        : fallbackMessage(res.status))
    return new ApiError(res.status, message, fieldErrors)
  }

  return new ApiError(res.status, fallbackMessage(res.status))
}

// ---------------------------------------------------------------- core request

type Method = "GET" | "POST" | "PATCH"

interface RequestOptions {
  method?: Method
  json?: unknown
  form?: Record<string, string>
  query?: Record<string, string | number | undefined>
  /** Set false for calls where 401 means "bad credentials", not "session over". */
  redirectOn401?: boolean
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", json, form, query, redirectOn401 = true } = options

  const url = new URL(path, BASE_URL)
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== "") url.searchParams.set(key, String(value))
    }
  }

  const headers: Record<string, string> = { Accept: "application/json" }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  let body: BodyInit | undefined
  if (json !== undefined) {
    headers["Content-Type"] = "application/json"
    body = JSON.stringify(json)
  } else if (form) {
    // URLSearchParams makes fetch send application/x-www-form-urlencoded.
    body = new URLSearchParams(form)
  }

  let res: Response
  try {
    res = await fetch(url, { method, headers, body })
  } catch {
    throw new ApiError(0, "Can't reach the Aerofare server. Check your connection and try again.")
  }

  if (res.status === 401 && redirectOn401 && token) {
    // Token expired or was revoked by logout on another tab.
    clearToken()
    onUnauthorized?.()
    throw new ApiError(401, "Your session has ended. Log in again to continue.")
  }

  if (!res.ok) throw await toApiError(res)

  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export function apiGet<T>(path: string, query?: RequestOptions["query"]): Promise<T> {
  return request<T>(path, { query })
}

export function apiPost<T>(path: string, json?: unknown): Promise<T> {
  return request<T>(path, { method: "POST", json })
}

export function apiPatch<T>(path: string, json: unknown): Promise<T> {
  return request<T>(path, { method: "PATCH", json })
}

// ---------------------------------------------------------------- endpoints

export const api = {
  // auth
  login: (email: string, password: string) =>
    request<TokenResponse>("/users/login", {
      method: "POST",
      form: { username: email, password },
      redirectOn401: false,
    }),
  signup: (input: SignupInput) => apiPost<User>("/users/signup", input),
  logout: () => apiPost<void>("/users/logout"),
  me: () => apiGet<User>("/users/me"),
  /** Session restore on page load: a stale token should log out quietly, not redirect. */
  restoreSession: () => request<User>("/users/me", { redirectOn401: false }),
  updateMe: (input: UserUpdate) => apiPatch<User>("/users/me", input),
  changePassword: (input: PasswordChange) => apiPost<void>("/users/me/password", input),
  listUsers: () => apiGet<User[]>("/users"),

  // airports
  listAirports: () => apiGet<Airport[]>("/airports"),
  createAirport: (input: AirportInput) => apiPost<Airport>("/airports", input),
  updateAirport: (id: number, input: Partial<AirportInput>) =>
    apiPatch<Airport>(`/airports/${id}`, input),

  // flights
  listFlights: () => apiGet<Flight[]>("/flights"),
  searchFlights: (params: FlightSearchParams) =>
    apiGet<Flight[]>("/flights/search", { ...params }),
  getFlight: (id: number) => apiGet<Flight>(`/flights/${id}`),
  createFlight: (input: FlightInput) => apiPost<Flight>("/flights", input),
  updateFlight: (id: number, input: Partial<FlightInput>) =>
    apiPatch<Flight>(`/flights/${id}`, input),

  // bookings
  myBookings: () => apiGet<Booking[]>("/bookings/me"),
  allBookings: () => apiGet<Booking[]>("/bookings"),
  createBooking: (input: BookingInput) => apiPost<Booking>("/bookings", input),
  cancelBooking: (id: number) => apiPost<Booking>(`/bookings/${id}/cancel`),

  // payments
  myPayments: () => apiGet<Payment[]>("/payments/me"),
  allPayments: () => apiGet<Payment[]>("/payments"),
  refundPayment: (id: number) => apiPost<Payment>(`/payments/${id}/refund`),
}
