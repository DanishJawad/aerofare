import { useEffect, useState } from "react"
import { apiGet } from "./api"
import type { Airport, Flight } from "./types"

function App() {
  const [airports, setAirports] = useState<Airport[]>([])
  const [airportsLoading, setAirportsLoading] = useState(true)
  const [airportsError, setAirportsError] = useState<string | null>(null)

  const [flights, setFlights] = useState<Flight[]>([])
  const [flightsLoading, setFlightsLoading] = useState(true)
  const [flightsError, setFlightsError] = useState<string | null>(null)

  useEffect(() => {
    apiGet<Airport[]>("/airports")
      .then((data) => setAirports(data))
      .catch((err) => setAirportsError((err as Error).message))
      .finally(() => setAirportsLoading(false))
  }, [])

  useEffect(() => {
    apiGet<Flight[]>("/flights")
      .then((data) => setFlights(data))
      .catch((err) => setFlightsError((err as Error).message))
      .finally(() => setFlightsLoading(false))
  }, [])

  function renderAirports() {
    if (airportsLoading) return <p>Loading airports…</p>
    if (airportsError) return <p>Could not load airports: {airportsError}</p>
    if (airports.length === 0) return <p>No airports yet.</p>
    return (
      <ul>
        {airports.map((a) => (
          <li key={a.id}>
            {a.name} — {a.city}, {a.country}
          </li>
        ))}
      </ul>
    )
  }

  function renderFlights() {
    if (flightsLoading) return <p>Loading flights…</p>
    if (flightsError) return <p>Could not load flights: {flightsError}</p>
    if (flights.length === 0) return <p>No flights yet.</p>
    return (
      <ul>
        {flights.map((f) => (
          <li key={f.id}>
            {f.airline_name}: {f.departure_airport} → {f.arrival_airport} ·{" "}
            {f.flight_class} · ${f.price}
          </li>
        ))}
      </ul>
    )
  }

  return (
    <>
      <h2>Airports</h2>
      {renderAirports()}

      <h2>Flights</h2>
      {renderFlights()}
    </>
  )
}

export default App
