import { api } from "../api"
import type { Airport, Flight } from "../types"

// Airports rarely change and almost every screen needs them to turn an airport
// id into a city name, so fetch them once per page load and share the promise.
let airportsPromise: Promise<Airport[]> | null = null

export function getAirports(): Promise<Airport[]> {
  if (!airportsPromise) {
    airportsPromise = api.listAirports().catch((err: unknown) => {
      airportsPromise = null // let the next caller retry
      throw err
    })
  }
  return airportsPromise
}

/** Call after an admin creates or edits an airport. */
export function invalidateAirports(): void {
  airportsPromise = null
}

export function indexById<T extends { id: number }>(items: T[]): Map<number, T> {
  return new Map(items.map((item) => [item.id, item]))
}

/** Bookings and payments only carry ids, so screens join them to flights client-side. */
export async function getFlightsAndAirports(): Promise<{
  flights: Map<number, Flight>
  airports: Map<number, Airport>
}> {
  const [flights, airports] = await Promise.all([api.listFlights(), getAirports()])
  return { flights: indexById(flights), airports: indexById(airports) }
}
