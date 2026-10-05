import { useState, type FormEvent } from "react"
import { Link, useLocation, useNavigate, useParams } from "react-router-dom"
import { ApiError, api } from "../api"
import { useAuth } from "../auth/context"
import { Alert, EmptyState, ErrorState, Skeleton, Spinner } from "../components/Feedback"
import { SeatsBadge } from "../components/FlightCard"
import { ArrowLeftIcon, MinusIcon, PlaneIcon, PlusIcon } from "../components/Icons"
import { getAirports, indexById } from "../lib/data"
import {
  CLASS_LABELS,
  formatDate,
  formatDuration,
  formatMoney,
  formatTime,
  hasDeparted,
  localTimeZoneLabel,
  pluralize,
} from "../lib/format"
import { useAsync } from "../lib/useAsync"
import type { Airport, Flight } from "../types"

function BackLink() {
  return (
    <Link to="/" className="back-link">
      <ArrowLeftIcon />
      All flights
    </Link>
  )
}

function Timeline({ flight, from, to }: { flight: Flight; from?: Airport; to?: Airport }) {
  return (
    <div className="timeline">
      <span className="timeline-dot" aria-hidden="true" />
      <div className="timeline-leg">
        <div className="timeline-time">{formatTime(flight.start_time)}</div>
        <div className="timeline-place">{from ? `${from.city}, ${from.country}` : "Unknown airport"}</div>
        <div>
          {from?.name} · {formatDate(flight.start_time)}
        </div>
      </div>
      <span className="timeline-rail" aria-hidden="true" />
      <div className="timeline-leg muted">
        {formatDuration(flight.start_time, flight.end_time)} direct · {flight.airline_name}
      </div>
      <span className="timeline-dot timeline-dot-end" aria-hidden="true" />
      <div className="timeline-leg">
        <div className="timeline-time">{formatTime(flight.end_time)}</div>
        <div className="timeline-place">{to ? `${to.city}, ${to.country}` : "Unknown airport"}</div>
        <div>
          {to?.name} · {formatDate(flight.end_time)}
        </div>
      </div>
    </div>
  )
}

function BookingPanel({ flight, onConflict }: { flight: Flight; onConflict: () => void }) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [seats, setSeats] = useState(1)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const departed = hasDeparted(flight)
  const soldOut = flight.available_seats <= 0
  const max = flight.available_seats
  const validSeats = Number.isInteger(seats) && seats >= 1 && seats <= max
  const total = Number.parseFloat(flight.price) * (validSeats ? seats : 0)

  async function book(e: FormEvent) {
    e.preventDefault()
    if (!validSeats) return
    setSubmitting(true)
    setError(null)
    try {
      const booking = await api.createBooking({ flight_id: flight.id, seats_booked: seats })
      navigate("/bookings", { state: { bookedId: booking.id } })
    } catch (err) {
      const apiErr = err instanceof ApiError ? err : null
      setError(apiErr?.fieldErrors.seats_booked ?? apiErr?.message ?? "Booking failed. Try again.")
      // Seats or departure changed under us: refresh the flight so the panel is honest.
      if (apiErr?.status === 409) onConflict()
      setSubmitting(false)
    }
  }

  if (departed || soldOut) {
    return (
      <aside className="card booking-panel" aria-labelledby="book-title">
        <div className="card-body stack">
          <h2 className="section-title flush" id="book-title">
            {departed ? "This flight has departed" : "This flight is sold out"}
          </h2>
          <p className="muted">
            {departed
              ? "Bookings close at departure time. Search again for a later flight on this route."
              : "Every seat has been booked. Seats come back if someone cancels, so check again later or pick another flight."}
          </p>
          <Link
            to={`/?from=${flight.departure_airport}&to=${flight.arrival_airport}`}
            className="btn btn-primary btn-block"
          >
            Find other flights on this route
          </Link>
        </div>
      </aside>
    )
  }

  return (
    <aside className="card booking-panel" aria-labelledby="book-title">
      <form className="card-body stack" onSubmit={book} noValidate>
        <div>
          <h2 className="section-title flush" id="book-title">
            {formatMoney(flight.price)} <span className="price-note">per seat</span>
          </h2>
        </div>

        <div className="field">
          <label className="field-label" htmlFor="seats">
            Seats
          </label>
          <div className="stepper">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setSeats((s) => Math.max(1, s - 1))}
              disabled={seats <= 1 || submitting}
              aria-label="One fewer seat"
            >
              <MinusIcon />
            </button>
            <input
              id="seats"
              className="input"
              type="number"
              inputMode="numeric"
              min={1}
              max={max}
              step={1}
              value={Number.isNaN(seats) ? "" : seats}
              onChange={(e) => setSeats(e.target.valueAsNumber)}
              aria-describedby="seats-hint"
              aria-invalid={!validSeats || undefined}
              disabled={submitting}
            />
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setSeats((s) => Math.min(max, (Number.isNaN(s) ? 0 : s) + 1))}
              disabled={seats >= max || submitting}
              aria-label="One more seat"
            >
              <PlusIcon />
            </button>
          </div>
          <p className={validSeats ? "field-hint" : "field-error"} id="seats-hint">
            {validSeats
              ? `${pluralize(max, "seat")} available`
              : `Choose between 1 and ${max}.`}
          </p>
        </div>

        <dl className="summary-rows">
          <div>
            <dt>
              {formatMoney(flight.price)} × {validSeats ? seats : 0}
            </dt>
            <dd>{formatMoney(total)}</dd>
          </div>
          <div className="summary-total">
            <dt>Total</dt>
            <dd>{formatMoney(total)}</dd>
          </div>
        </dl>

        {error && <Alert tone="error" title="Booking didn't go through">{error}</Alert>}

        {user ? (
          <button
            type="submit"
            className="btn btn-primary btn-lg btn-block"
            disabled={!validSeats || submitting}
          >
            {submitting && <Spinner />}
            {submitting ? "Booking…" : `Book ${pluralize(validSeats ? seats : 0, "seat")}`}
          </button>
        ) : (
          <Link
            to="/login"
            state={{ from: location.pathname }}
            className="btn btn-primary btn-lg btn-block"
          >
            Log in to book
          </Link>
        )}
        <p className="field-hint">
          {user
            ? "You're charged when you book. Cancel any time before departure for a full refund."
            : "Browsing is free. You'll come straight back here after logging in."}
        </p>
      </form>
    </aside>
  )
}

export function FlightDetailPage() {
  const { id } = useParams()
  const flightId = Number(id)
  const req = useAsync(
    () => Promise.all([api.getFlight(flightId), getAirports()]),
    [flightId],
  )

  if (!Number.isInteger(flightId) || req.error?.status === 404 || req.error?.status === 422) {
    return (
      <div className="container page">
        <BackLink />
        <EmptyState icon={<PlaneIcon size={24} />} title="We couldn't find that flight">
          It may have been removed, or the link is wrong. Head back to the list to find another one.
        </EmptyState>
      </div>
    )
  }

  if (req.error) {
    return (
      <div className="container page">
        <BackLink />
        <ErrorState title="We couldn't load this flight" message={req.error.message} onRetry={req.reload} />
      </div>
    )
  }

  if (!req.data) {
    return (
      <div className="container page" role="status" aria-label="Loading flight">
        <BackLink />
        <div className="stack">
          <Skeleton height={40} width="60%" />
          <div className="detail-layout">
            <div className="area-itinerary">
              <Skeleton height={280} />
            </div>
            <div className="booking-panel">
              <Skeleton height={320} />
            </div>
          </div>
        </div>
      </div>
    )
  }

  const [flight, airportList] = req.data
  const airports = indexById(airportList)
  const from = airports.get(flight.departure_airport)
  const to = airports.get(flight.arrival_airport)

  return (
    <div className="container page">
      <BackLink />
      <div className="page-header">
        <div>
          <h1 className="page-title">
            {from?.city ?? "Unknown"} to {to?.city ?? "Unknown"}
          </h1>
          <p className="page-subtitle">
            {formatDate(flight.start_time)} · {flight.airline_name} ·{" "}
            {CLASS_LABELS[flight.flight_class]}
          </p>
        </div>
        <SeatsBadge flight={flight} />
      </div>

      <div className="detail-layout">
        <section className="card area-itinerary" aria-labelledby="itinerary-title">
          <div className="card-header">
            <h2 className="section-title flush" id="itinerary-title">
              Itinerary
            </h2>
          </div>
          <div className="card-body">
            <Timeline flight={flight} from={from} to={to} />
            <p className="field-hint mt-4">
              Times shown in your time zone ({localTimeZoneLabel()}).
            </p>
          </div>
        </section>

        <section className="card area-facts" aria-labelledby="facts-title">
          <div className="card-header">
            <h2 className="section-title flush" id="facts-title">
              Flight details
            </h2>
          </div>
          <div className="card-body">
            <dl className="facts">
              <div>
                <dt>Airline</dt>
                <dd>{flight.airline_name}</dd>
              </div>
              <div>
                <dt>Cabin</dt>
                <dd>{CLASS_LABELS[flight.flight_class]}</dd>
              </div>
              <div>
                <dt>Duration</dt>
                <dd>{formatDuration(flight.start_time, flight.end_time)}</dd>
              </div>
              <div>
                <dt>Seats left</dt>
                <dd className="num">
                  {flight.available_seats} of {flight.total_seats}
                </dd>
              </div>
            </dl>
          </div>
        </section>

        <BookingPanel flight={flight} onConflict={req.reload} />
      </div>
    </div>
  )
}
