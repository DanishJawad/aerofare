import { Link } from "react-router-dom"
import type { Airport, Flight } from "../types"
import {
  CLASS_LABELS,
  airportLabel,
  dayOffset,
  formatDate,
  formatDuration,
  formatMoney,
  formatTime,
  hasDeparted,
  pluralize,
} from "../lib/format"
import { Badge } from "./StatusBadge"
import { ArrowRightIcon } from "./Icons"

const LOW_SEATS = 5

export function FlightRoute({
  flight,
  from,
  to,
}: {
  flight: Flight
  from?: Airport
  to?: Airport
}) {
  const plusDays = dayOffset(flight.start_time, flight.end_time)
  return (
    <div className="route">
      <div className="route-end">
        <div className="route-time">{formatTime(flight.start_time)}</div>
        <div className="route-city">{airportLabel(from)}</div>
      </div>
      <div className="route-line" aria-hidden="true">
        <span>{formatDuration(flight.start_time, flight.end_time)}</span>
        <span className="route-track" />
        <span>Direct</span>
      </div>
      <div className="route-end">
        <div className="route-time">
          {formatTime(flight.end_time)}
          {plusDays > 0 && <span className="route-day">+{plusDays}</span>}
        </div>
        <div className="route-city">{airportLabel(to)}</div>
      </div>
    </div>
  )
}

/** Availability as a badge: text always says what the color means. */
export function SeatsBadge({ flight }: { flight: Flight }) {
  if (hasDeparted(flight)) return <Badge tone="neutral">Departed</Badge>
  if (flight.available_seats <= 0) return <Badge tone="neutral">Sold out</Badge>
  if (flight.available_seats <= LOW_SEATS)
    return <Badge tone="warning">{`Only ${pluralize(flight.available_seats, "seat")} left`}</Badge>
  return null
}

export function FlightCard({
  flight,
  airports,
}: {
  flight: Flight
  airports: Map<number, Airport>
}) {
  const from = airports.get(flight.departure_airport)
  const to = airports.get(flight.arrival_airport)
  const unavailable = hasDeparted(flight) || flight.available_seats <= 0

  // One link per card: screen readers get a single sentence, not every number.
  const availability = hasDeparted(flight)
    ? "departed"
    : flight.available_seats <= 0
      ? "sold out"
      : `${pluralize(flight.available_seats, "seat")} left`
  const summary = `${flight.airline_name}, ${airportLabel(from)} to ${airportLabel(to)}, ${formatDate(
    flight.start_time,
  )} at ${formatTime(flight.start_time)}, ${CLASS_LABELS[flight.flight_class]}, ${formatMoney(
    flight.price,
  )} per seat, ${availability}`

  return (
    <Link
      to={`/flights/${flight.id}`}
      className="flight-card"
      data-muted={unavailable}
      aria-label={summary}
    >
      <div>
        <div className="flight-meta">
          <span className="flight-airline">{flight.airline_name}</span>
          <span aria-hidden="true">·</span>
          <span>{CLASS_LABELS[flight.flight_class]}</span>
          <span aria-hidden="true">·</span>
          <span>{formatDate(flight.start_time)}</span>
          <SeatsBadge flight={flight} />
        </div>
        <FlightRoute flight={flight} from={from} to={to} />
      </div>
      <div className="flight-side">
        <div>
          <div className="price">{formatMoney(flight.price)}</div>
          <div className="price-note">per seat</div>
        </div>
        <span className="flight-cta">
          {unavailable ? "View details" : "Select"}
          <ArrowRightIcon />
        </span>
      </div>
    </Link>
  )
}
