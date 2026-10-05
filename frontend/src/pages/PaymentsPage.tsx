import { Link } from "react-router-dom"
import { api } from "../api"
import { EmptyState, ErrorState, Skeleton } from "../components/Feedback"
import { CardIcon } from "../components/Icons"
import { StatusBadge } from "../components/StatusBadge"
import { getFlightsAndAirports, indexById } from "../lib/data"
import { airportLabel, formatDateTime, formatMoney, formatShortDate, parseApiDate } from "../lib/format"
import { useAsync } from "../lib/useAsync"

export function PaymentsPage() {
  const req = useAsync(
    () => Promise.all([api.myPayments(), api.myBookings(), getFlightsAndAirports()]),
    [],
  )

  function body() {
    if (req.error) {
      return (
        <ErrorState title="We couldn't load your payments" message={req.error.message} onRetry={req.reload} />
      )
    }
    if (!req.data) {
      return (
        <div className="table-wrap" role="status" aria-label="Loading payments">
          <div className="card-body stack">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} height={24} />
            ))}
          </div>
        </div>
      )
    }

    const [payments, bookingList, { flights, airports }] = req.data
    if (payments.length === 0) {
      return (
        <EmptyState
          icon={<CardIcon size={24} />}
          title="No payments yet"
          action={
            <Link to="/" className="btn btn-primary">
              Find a flight
            </Link>
          }
        >
          You pay when you book, so your first payment shows up here as soon as you book a flight.
        </EmptyState>
      )
    }

    const bookings = indexById(bookingList)
    const sorted = [...payments].sort(
      (a, b) => parseApiDate(b.created_at).getTime() - parseApiDate(a.created_at).getTime(),
    )

    return (
      <div className="table-wrap">
        <table className="table table-stack">
          <caption className="visually-hidden">Your payments, newest first</caption>
          <thead>
            <tr>
              <th scope="col">Payment</th>
              <th scope="col">For</th>
              <th scope="col">Status</th>
              <th scope="col">Paid on</th>
              <th scope="col" className="align-right">
                Amount
              </th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((p) => {
              const booking = bookings.get(p.booking_id)
              const flight = booking && flights.get(booking.flight_id)
              return (
                <tr key={p.id}>
                  <td data-label="Payment" className="num">
                    #{p.id}
                  </td>
                  <td data-label="For">
                    <div>
                      <Link to="/bookings">Booking #{p.booking_id}</Link>
                      {flight && (
                        <span className="cell-sub">
                          {airportLabel(airports.get(flight.departure_airport))} to{" "}
                          {airportLabel(airports.get(flight.arrival_airport))},{" "}
                          {formatShortDate(flight.start_time)}
                        </span>
                      )}
                    </div>
                  </td>
                  <td data-label="Status">
                    <StatusBadge status={p.status} />
                  </td>
                  <td data-label="Paid on">{p.paid_at ? formatDateTime(p.paid_at) : "Not paid"}</td>
                  <td data-label="Amount" className="align-right num">
                    {formatMoney(p.amount)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    )
  }

  return (
    <div className="container page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Payments</h1>
          <p className="page-subtitle">
            Payment is taken when you book. Cancelled bookings show as refunded.
          </p>
        </div>
      </div>
      {body()}
    </div>
  )
}
