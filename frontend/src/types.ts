// Response and request shapes for the Aerofare FastAPI backend.
// Decimals (price, amounts) arrive as strings; datetimes arrive as ISO strings
// without a timezone offset and are UTC (see parseApiDate in lib/format.ts).

export interface Airport {
  id: number
  name: string
  city: string
  country: string
}

export type AirportInput = Omit<Airport, "id">

export type FlightClass = "economy" | "business" | "first"

export interface Flight {
  id: number
  airline_name: string
  departure_airport: number
  arrival_airport: number
  start_time: string
  end_time: string
  price: string
  total_seats: number
  available_seats: number
  flight_class: FlightClass
}

export type FlightInput = Omit<Flight, "id">

export interface FlightSearchParams {
  departure_airport?: number
  arrival_airport?: number
  start_time?: string
  end_time?: string
  min_price?: string
  max_price?: string
  flight_class?: FlightClass
}

export interface User {
  id: number
  name: string
  email: string
  phone_number: string | null
  city: string
  country: string
  is_admin: boolean
}

export interface SignupInput {
  name: string
  email: string
  password: string
  phone_number: string | null
  city: string
  country: string
}

export type UserUpdate = Partial<Omit<User, "id" | "is_admin">>

export interface PasswordChange {
  current_password: string
  new_password: string
}

export interface MessageResponse {
  message: string
}

export interface TokenResponse {
  access_token: string
  token_type: "bearer"
}

export type BookingStatus = "confirmed" | "cancelled"

export interface Booking {
  id: number
  user_id: number
  flight_id: number
  seats_booked: number
  total_amount: string
  status: BookingStatus
  created_at: string
}

export interface BookingInput {
  flight_id: number
  seats_booked: number
}

export type PaymentStatus = "pending" | "completed" | "failed" | "refunded"

export interface Payment {
  id: number
  booking_id: number
  amount: string
  status: PaymentStatus
  paid_at: string | null
  created_at: string
}

/** One entry of an error's `details` list. `field` is null for whole-body rules. */
export interface ErrorDetail {
  field: string | null
  message: string
}

/** Every error response from the API has this shape. */
export interface ErrorEnvelope {
  error: {
    code: string
    message: string
    details: ErrorDetail[] | null
    request_id: string
  }
}
