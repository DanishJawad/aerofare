import { useState } from "react"
import { api } from "../../api"
import { EmptyState, ErrorState, Skeleton } from "../../components/Feedback"
import { TicketIcon } from "../../components/Icons"
import { StatusBadge } from "../../components/StatusBadge"
import { getFlightsAndAirports, indexById } from "../../lib/data"
import { airportLabel, formatDateTime, formatMoney, formatShortDate } from "../../lib/format"
import { useAsync } from "../../lib/useAsync"
import type { BookingStatus } from "../../types"

type Filter = "all" | BookingStatus

export function AdminBookingsPage() {
  const req = useAsync(
    () => Promise.all([api.allBookings(), api.listUsers(), getFlightsAndAirports()]),
    [],
  )
  const [filter, setFilter] = useState<Filter>("all")

  function body() {
    if (req.error) return <ErrorState message={req.error.message} onRetry={req.reload} />
    if (!req.data) {
      return (
        <div className="table-wrap card-body stack" role="status" aria-label="Loading bookings">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} height={24} />
          ))}
        </div>
      )
    }
    const [bookings, userList, { flights, airports }] = req.data
    if (bookings.length === 0) {
      return (
        <EmptyState icon={<TicketIcon size={24} />} title="No bookings yet">
          Bookings appear here as soon as a customer books a flight.
        </EmptyState>
      )
    }
    const users = indexById(userList)
    const rows = bookings
      .filter((b) => filter === "all" || b.status === filter)
      .sort((a, b) => b.id - a.id)

    if (rows.length === 0) {
      return (
        <EmptyState icon={<TicketIcon size={24} />} title={`No ${filter} bookings`}>
          Switch the filter above to see the rest.
        </EmptyState>
      )
    }

    return (
      <div className="table-wrap" aria-busy={req.loading}>
        <table className="table table-stack">
          <caption className="visually-hidden">All bookings, newest first</caption>
          <thead>
            <tr>
              <th scope="col">ID</th>
              <th scope="col">Customer</th>
              <th scope="col">Flight</th>
              <th scope="col" className="align-right">
                Seats
              </th>
              <th scope="col" className="align-right">
                Total
              </th>
              <th scope="col">Status</th>
              <th scope="col">Booked</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((b) => {
              const user = users.get(b.user_id)
              const flight = flights.get(b.flight_id)
              return (
                <tr key={b.id}>
                  <td data-label="ID" className="num">
                    {b.id}
                  </td>
                  <td data-label="Customer">
                    <div>
                      {user?.name ?? `User #${b.user_id}`}
                      {user && <span className="cell-sub">{user.email}</span>}
                    </div>
                  </td>
                  <td data-label="Flight">
                    <div>
                      {flight
                        ? `${airportLabel(airports.get(flight.departure_airport))} to ${airportLabel(
                            airports.get(flight.arrival_airport),
                          )}`
                        : `Flight #${b.flight_id}`}
                      {flight && <span className="cell-sub">{formatDateTime(flight.start_time)}</span>}
                    </div>
                  </td>
                  <td data-label="Seats" className="align-right num">
                    {b.seats_booked}
                  </td>
                  <td data-label="Total" className="align-right num">
                    {formatMoney(b.total_amount)}
                  </td>
                  <td data-label="Status">
                    <StatusBadge status={b.status} />
                  </td>
                  <td data-label="Booked">{formatShortDate(b.created_at)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    )
  }

  const counts = req.data
    ? {
        all: req.data[0].length,
        confirmed: req.data[0].filter((b) => b.status === "confirmed").length,
        cancelled: req.data[0].filter((b) => b.status === "cancelled").length,
      }
    : null

  return (
    <div className="stack">
      <div className="toolbar">
        <div>
          <h1 className="admin-title">Bookings</h1>
          <p className="muted">Read-only. Refunds are handled from Payments.</p>
        </div>
      </div>
      <div className="segmented" role="group" aria-label="Filter by status">
        {(["all", "confirmed", "cancelled"] as Filter[]).map((f) => (
          <button key={f} type="button" aria-pressed={filter === f} onClick={() => setFilter(f)}>
            {f === "all" ? "All" : f === "confirmed" ? "Confirmed" : "Cancelled"}
            {counts && ` (${counts[f]})`}
          </button>
        ))}
      </div>
      {body()}
    </div>
  )
}
