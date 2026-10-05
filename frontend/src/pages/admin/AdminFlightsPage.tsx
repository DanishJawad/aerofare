import { useState } from "react"
import { Link } from "react-router-dom"
import { api } from "../../api"
import { Alert, EmptyState, ErrorState, Skeleton } from "../../components/Feedback"
import { PlaneIcon, PlusIcon } from "../../components/Icons"
import { Badge } from "../../components/StatusBadge"
import { getAirports, indexById } from "../../lib/data"
import {
  CLASS_LABELS,
  airportLabel,
  formatDateTime,
  formatMoney,
  hasDeparted,
  parseApiDate,
} from "../../lib/format"
import { useAsync } from "../../lib/useAsync"
import type { Flight } from "../../types"
import { FlightDialog } from "./FlightDialog"

type View = "upcoming" | "departed" | "all"

export function AdminFlightsPage() {
  const req = useAsync(() => Promise.all([api.listFlights(), getAirports()]), [])
  const [view, setView] = useState<View>("upcoming")
  const [editing, setEditing] = useState<Flight | null | undefined>(undefined)
  const [notice, setNotice] = useState<string | null>(null)

  const airportCount = req.data?.[1].length ?? 0

  function body() {
    if (req.error) return <ErrorState message={req.error.message} onRetry={req.reload} />
    if (!req.data) {
      return (
        <div className="table-wrap card-body stack" role="status" aria-label="Loading flights">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} height={24} />
          ))}
        </div>
      )
    }
    const [flights, airportList] = req.data
    const airports = indexById(airportList)

    if (flights.length === 0) {
      return (
        <EmptyState icon={<PlaneIcon size={24} />} title="No flights yet">
          {airportCount < 2 ? (
            <>
              You need at least two airports first. <Link to="/admin/airports">Add airports</Link>
            </>
          ) : (
            "Add the first flight and it will appear on the public flight list straight away."
          )}
        </EmptyState>
      )
    }

    const rows = flights
      .filter((f) => view === "all" || (view === "departed") === hasDeparted(f))
      .sort((a, b) => {
        const diff = parseApiDate(a.start_time).getTime() - parseApiDate(b.start_time).getTime()
        return view === "departed" ? -diff : diff
      })

    if (rows.length === 0) {
      return (
        <EmptyState icon={<PlaneIcon size={24} />} title={`No ${view} flights`}>
          Switch the filter above to see the rest.
        </EmptyState>
      )
    }

    return (
      <div className="table-wrap" aria-busy={req.loading}>
        <table className="table table-stack">
          <caption className="visually-hidden">Flights</caption>
          <thead>
            <tr>
              <th scope="col">ID</th>
              <th scope="col">Route</th>
              <th scope="col">Departs</th>
              <th scope="col">Airline</th>
              <th scope="col" className="align-right">
                Price
              </th>
              <th scope="col" className="align-right">
                Seats left
              </th>
              <th scope="col" className="cell-actions">
                <span className="visually-hidden">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((f) => (
              <tr key={f.id}>
                <td data-label="ID" className="num">
                  {f.id}
                </td>
                <td data-label="Route">
                  {airportLabel(airports.get(f.departure_airport))} to{" "}
                  {airportLabel(airports.get(f.arrival_airport))}
                </td>
                <td data-label="Departs">
                  <div>
                    <span className="num">{formatDateTime(f.start_time)}</span>
                    {hasDeparted(f) && (
                      <>
                        {" "}
                        <Badge tone="neutral">Departed</Badge>
                      </>
                    )}
                  </div>
                </td>
                <td data-label="Airline">
                  <div>
                    {f.airline_name}
                    <span className="cell-sub">{CLASS_LABELS[f.flight_class]}</span>
                  </div>
                </td>
                <td data-label="Price" className="align-right num">
                  {formatMoney(f.price)}
                </td>
                <td data-label="Seats left" className="align-right num">
                  {f.available_seats} / {f.total_seats}
                </td>
                <td className="cell-actions">
                  <button
                    type="button"
                    className="btn btn-ghost"
                    onClick={() => setEditing(f)}
                    aria-label={`Edit flight ${f.id}`}
                  >
                    Edit
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  return (
    <div className="stack">
      <div className="toolbar">
        <div>
          <h1 className="admin-title">Flights</h1>
          {req.data && <p className="muted">{req.data[0].length} total</p>}
        </div>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => setEditing(null)}
          disabled={!req.data || airportCount < 2}
        >
          <PlusIcon />
          Add flight
        </button>
      </div>

      <div className="segmented" role="group" aria-label="Show flights">
        {(["upcoming", "departed", "all"] as View[]).map((v) => (
          <button key={v} type="button" aria-pressed={view === v} onClick={() => setView(v)}>
            {v === "upcoming" ? "Upcoming" : v === "departed" ? "Departed" : "All"}
          </button>
        ))}
      </div>

      {notice && <Alert tone="success">{notice}</Alert>}
      {body()}

      {editing !== undefined && req.data && (
        <FlightDialog
          key={editing?.id ?? "new"}
          flight={editing}
          airports={req.data[1]}
          onClose={() => setEditing(undefined)}
          onSaved={(f) => {
            setNotice(editing ? `Saved changes to flight #${f.id}.` : `Added flight #${f.id}.`)
            setEditing(undefined)
            req.reload()
          }}
        />
      )}
    </div>
  )
}
