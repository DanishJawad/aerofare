import { useState } from "react"
import { Link, useLocation } from "react-router-dom"
import { api } from "../api"
import { ConfirmDialog } from "../components/Dialog"
import { Alert, EmptyState, ErrorState, SkeletonList } from "../components/Feedback"
import { TicketIcon } from "../components/Icons"
import { Badge, StatusBadge } from "../components/StatusBadge"
import { getFlightsAndAirports } from "../lib/data"
import {
  CLASS_LABELS,
  airportLabel,
  formatDate,
  formatMoney,
  formatShortDate,
  formatTime,
  hasDeparted,
  parseApiDate,
  pluralize,
} from "../lib/format"
import { useAsync } from "../lib/useAsync"
import type { Airport, Booking, Flight } from "../types"

interface Row {
  booking: Booking
  flight?: Flight
  from?: Airport
  to?: Airport
}

function BookingCard({
  row,
  highlight,
  onCancel,
}: {
  row: Row
  highlight: boolean
  onCancel?: () => void
}) {
  const { booking, flight, from, to } = row
  return (
    <article className="booking-card" data-highlight={highlight} aria-labelledby={`b-${booking.id}`}>
      <div>
        <div className="booking-head">
          <span className="booking-ref" id={`b-${booking.id}`}>
            Booking #{booking.id}
          </span>
          {flight && booking.status === "confirmed" && hasDeparted(flight) ? (
            <Badge tone="neutral">Flown</Badge>
          ) : (
            <StatusBadge status={booking.status} />
          )}
        </div>
        <div className="booking-route">
          {flight ? `${airportLabel(from)} to ${airportLabel(to)}` : `Flight #${booking.flight_id}`}
        </div>
        <div className="booking-details">
          {flight && (
            <>
              <span>
                {formatDate(flight.start_time)}, {formatTime(flight.start_time)}
              </span>
              <span>
                {flight.airline_name} · {CLASS_LABELS[flight.flight_class]}
              </span>
            </>
          )}
          <span>{pluralize(booking.seats_booked, "seat")}</span>
          <span>Booked {formatShortDate(booking.created_at)}</span>
        </div>
      </div>
      <div className="booking-side">
        <div className="price">{formatMoney(booking.total_amount)}</div>
        <div className="btn-row">
          {flight && (
            <Link to={`/flights/${flight.id}`} className="btn btn-ghost">
              View flight
            </Link>
          )}
          {onCancel && (
            <button type="button" className="btn btn-danger-outline" onClick={onCancel}>
              Cancel booking
            </button>
          )}
        </div>
      </div>
    </article>
  )
}

export function BookingsPage() {
  const location = useLocation()
  const bookedId = (location.state as { bookedId?: number } | null)?.bookedId
  const req = useAsync(() => Promise.all([api.myBookings(), getFlightsAndAirports()]), [])
  const [toCancel, setToCancel] = useState<Row | null>(null)
  const [cancelled, setCancelled] = useState<Booking | null>(null)

  function body() {
    if (req.error) {
      return <ErrorState title="We couldn't load your trips" message={req.error.message} onRetry={req.reload} />
    }
    if (!req.data) return <SkeletonList rows={3} height={120} />

    const [bookings, { flights, airports }] = req.data
    if (bookings.length === 0) {
      return (
        <EmptyState
          icon={<TicketIcon size={24} />}
          title="No trips yet"
          action={
            <Link to="/" className="btn btn-primary">
              Find a flight
            </Link>
          }
        >
          When you book a flight it shows up here, with the option to cancel before departure.
        </EmptyState>
      )
    }

    const rows: Row[] = bookings.map((booking) => {
      const flight = flights.get(booking.flight_id)
      return {
        booking,
        flight,
        from: flight && airports.get(flight.departure_airport),
        to: flight && airports.get(flight.arrival_airport),
      }
    })
    const departure = (r: Row) => (r.flight ? parseApiDate(r.flight.start_time).getTime() : 0)

    // Upcoming soonest first; everything else most recent first.
    const upcoming = rows
      .filter((r) => r.booking.status === "confirmed" && r.flight && !hasDeparted(r.flight))
      .sort((a, b) => departure(a) - departure(b))
    const rest = rows
      .filter((r) => !upcoming.includes(r))
      .sort((a, b) => departure(b) - departure(a))

    return (
      <div aria-busy={req.loading}>
        <h2 className="group-title">Upcoming</h2>
        {upcoming.length === 0 ? (
          <p className="muted">
            No upcoming trips. <Link to="/">Find a flight</Link>
          </p>
        ) : (
          <div className="flight-list">
            {upcoming.map((row) => (
              <BookingCard
                key={row.booking.id}
                row={row}
                highlight={row.booking.id === bookedId}
                onCancel={() => setToCancel(row)}
              />
            ))}
          </div>
        )}

        {rest.length > 0 && (
          <>
            <h2 className="group-title">Past and cancelled</h2>
            <div className="flight-list">
              {rest.map((row) => (
                <BookingCard key={row.booking.id} row={row} highlight={false} />
              ))}
            </div>
          </>
        )}
      </div>
    )
  }

  return (
    <div className="container page">
      <div className="page-header">
        <div>
          <h1 className="page-title">My trips</h1>
          <p className="page-subtitle">Upcoming trips first. You can cancel a confirmed booking any time before it departs.</p>
        </div>
      </div>

      <div className="stack">
        {bookedId && !cancelled && (
          <Alert tone="success" title={`You're booked. Booking #${bookedId} is confirmed.`}>
            Payment was taken when you booked. You'll find the receipt under{" "}
            <Link to="/payments">Payments</Link>.
          </Alert>
        )}
        {cancelled && (
          <Alert tone="success" title={`Booking #${cancelled.id} is cancelled.`}>
            {formatMoney(cancelled.total_amount)} has been marked for refund and the seats are back
            on sale.
          </Alert>
        )}
        {body()}
      </div>

      <ConfirmDialog
        open={toCancel !== null}
        onClose={() => setToCancel(null)}
        title={`Cancel booking #${toCancel?.booking.id ?? ""}?`}
        confirmLabel="Cancel booking"
        pendingLabel="Cancelling…"
        cancelLabel="Keep booking"
        onConfirm={async () => {
          if (!toCancel) return
          const updated = await api.cancelBooking(toCancel.booking.id)
          setCancelled(updated)
          req.reload() // the server is the source of truth for status and seats
        }}
      >
        {toCancel && (
          <p>
            {toCancel.flight
              ? `${airportLabel(toCancel.from)} to ${airportLabel(toCancel.to)} on ${formatDate(
                  toCancel.flight.start_time,
                )}, ${pluralize(toCancel.booking.seats_booked, "seat")}. `
              : ""}
            Your payment of {formatMoney(toCancel.booking.total_amount)} will be refunded. This
            can't be undone.
          </p>
        )}
      </ConfirmDialog>
    </div>
  )
}
