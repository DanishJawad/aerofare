import { useState, type FormEvent } from "react"
import { useSearchParams } from "react-router-dom"
import { api, SEARCH_PAGE_SIZE } from "../api"
import { EmptyState, ErrorState, SkeletonList } from "../components/Feedback"
import { SelectField, TextField } from "../components/Field"
import { FlightCard } from "../components/FlightCard"
import { SearchIcon, SwapIcon } from "../components/Icons"
import { getAirports, indexById } from "../lib/data"
import { CLASS_LABELS, hasDeparted, localDateToApi, parseApiDate, pluralize } from "../lib/format"
import { useAsync } from "../lib/useAsync"
import type { Airport, FlightClass, FlightSearchParams } from "../types"

// Filters live in the URL so refresh, back/forward and shared links all work.
const FILTER_KEYS = ["from", "to", "depart", "arrive", "class", "min", "max"] as const
type FilterKey = (typeof FILTER_KEYS)[number]
type Filters = Record<FilterKey, string>

function readFilters(params: URLSearchParams): Filters {
  return Object.fromEntries(FILTER_KEYS.map((k) => [k, params.get(k) ?? ""])) as Filters
}

function toApiParams(f: Filters): FlightSearchParams {
  return {
    departure_airport: f.from ? Number(f.from) : undefined,
    arrival_airport: f.to ? Number(f.to) : undefined,
    start_time: f.depart ? localDateToApi(f.depart) : undefined,
    end_time: f.arrive ? localDateToApi(f.arrive, true) : undefined,
    flight_class: (f.class || undefined) as FlightClass | undefined,
    min_price: f.min || undefined,
    max_price: f.max || undefined,
  }
}

function validate(f: Filters): Partial<Record<FilterKey, string>> {
  const errors: Partial<Record<FilterKey, string>> = {}
  if (f.from && f.from === f.to) errors.to = "Pick a different airport from where you're leaving."
  if (f.depart && f.arrive && f.arrive < f.depart) errors.arrive = "Must be on or after the departure date."
  if (f.min && Number(f.min) < 0) errors.min = "Can't be negative."
  if (f.max && Number(f.max) < 0) errors.max = "Can't be negative."
  if (f.min && f.max && Number(f.min) > Number(f.max)) errors.max = "Must be at least the minimum price."
  return errors
}

function SearchForm({
  initial,
  airports,
  onSearch,
}: {
  initial: Filters
  airports: Airport[] | undefined
  onSearch: (f: Filters) => void
}) {
  const [f, setF] = useState<Filters>(initial)
  const [errors, setErrors] = useState<Partial<Record<FilterKey, string>>>({})
  const set = (key: FilterKey) => (value: string) => setF((prev) => ({ ...prev, [key]: value }))

  function submit(e: FormEvent) {
    e.preventDefault()
    const found = validate(f)
    setErrors(found)
    if (Object.keys(found).length === 0) onSearch(f)
  }

  const sorted = airports ? [...airports].sort((a, b) => a.city.localeCompare(b.city)) : []
  const airportOptions = sorted.map((a) => (
    <option key={a.id} value={a.id}>
      {a.city} ({a.name})
    </option>
  ))

  return (
    <form className="search-form" onSubmit={submit} noValidate aria-label="Search flights">
      <SelectField
        label="From"
        value={f.from}
        onChange={(e) => set("from")(e.target.value)}
        disabled={!airports}
      >
        <option value="">Any airport</option>
        {airportOptions}
      </SelectField>
      <button
        type="button"
        className="btn btn-ghost swap-button"
        onClick={() => setF((prev) => ({ ...prev, from: prev.to, to: prev.from }))}
        aria-label="Swap departure and arrival airports"
        title="Swap airports"
      >
        <SwapIcon size={20} />
      </button>
      <SelectField
        label="To"
        value={f.to}
        onChange={(e) => set("to")(e.target.value)}
        disabled={!airports}
        error={errors.to}
      >
        <option value="">Any airport</option>
        {airportOptions}
      </SelectField>
      <TextField
        label="Departing from"
        type="date"
        value={f.depart}
        onChange={(e) => set("depart")(e.target.value)}
      />
      <TextField
        label="Arriving by"
        type="date"
        value={f.arrive}
        min={f.depart || undefined}
        onChange={(e) => set("arrive")(e.target.value)}
        error={errors.arrive}
      />
      <div className="search-more">
        <SelectField label="Cabin class" value={f.class} onChange={(e) => set("class")(e.target.value)}>
          <option value="">Any class</option>
          {Object.entries(CLASS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </SelectField>
        <fieldset className="price-range fieldset-reset">
          <legend className="visually-hidden">Price per seat, in US dollars</legend>
          <TextField
            label="Min price ($)"
            type="number"
            inputMode="decimal"
            min={0}
            step="0.01"
            value={f.min}
            onChange={(e) => set("min")(e.target.value)}
            error={errors.min}
          />
          <TextField
            label="Max price ($)"
            type="number"
            inputMode="decimal"
            min={0}
            step="0.01"
            value={f.max}
            onChange={(e) => set("max")(e.target.value)}
            error={errors.max}
          />
        </fieldset>
        <button type="submit" className="btn btn-primary btn-lg">
          <SearchIcon />
          Search flights
        </button>
      </div>
    </form>
  )
}

export function FlightsPage() {
  const [params, setParams] = useSearchParams()
  const filters = readFilters(params)
  const hasFilters = FILTER_KEYS.some((k) => filters[k] !== "")
  const showPast = params.get("past") === "1"
  const query = FILTER_KEYS.map((k) => filters[k]).join("|")

  const airportsReq = useAsync(getAirports, [])
  const flightsReq = useAsync(
    () => (hasFilters ? api.searchFlights(toApiParams(filters)) : api.listFlights()),
    [query],
  )

  function search(next: Filters) {
    const p = new URLSearchParams()
    for (const k of FILTER_KEYS) if (next[k]) p.set(k, next[k])
    if (showPast) p.set("past", "1")
    setParams(p)
  }

  function togglePast(show: boolean) {
    const p = new URLSearchParams(params)
    if (show) p.set("past", "1")
    else p.delete("past")
    setParams(p, { replace: true })
  }

  const airports = airportsReq.data ? indexById(airportsReq.data) : new Map<number, Airport>()
  const all = [...(flightsReq.data ?? [])].sort(
    (a, b) => parseApiDate(a.start_time).getTime() - parseApiDate(b.start_time).getTime(),
  )
  const upcoming = all.filter((f) => !hasDeparted(f))
  const pastCount = all.length - upcoming.length
  const visible = showPast ? all : upcoming
  // A full page from search means more matches may exist beyond it.
  const pageFull = hasFilters && (flightsReq.data?.length ?? 0) >= SEARCH_PAGE_SIZE

  function renderResults() {
    const error = flightsReq.error ?? airportsReq.error
    if (error) {
      return (
        <ErrorState
          title="We couldn't load flights"
          message={error.message}
          onRetry={() => {
            flightsReq.reload()
            airportsReq.reload()
          }}
        />
      )
    }

    if (!flightsReq.data || !airportsReq.data) return <SkeletonList />

    if (all.length === 0) {
      return hasFilters ? (
        <EmptyState
          icon={<SearchIcon size={24} />}
          title="No flights match your search"
          action={
            <button type="button" className="btn btn-secondary" onClick={() => setParams({})}>
              Clear all filters
            </button>
          }
        >
          Try different dates, a wider price range, or leave one of the airports as "Any airport".
        </EmptyState>
      ) : (
        <EmptyState icon={<SearchIcon size={24} />} title="No flights scheduled yet">
          Flights appear here as soon as they're added. Check back soon.
        </EmptyState>
      )
    }

    if (visible.length === 0) {
      return (
        <EmptyState
          icon={<SearchIcon size={24} />}
          title="No upcoming flights"
          action={
            <button type="button" className="btn btn-secondary" onClick={() => togglePast(true)}>
              Show {pluralize(pastCount, "past flight")}
            </button>
          }
        >
          Every flight that matches has already departed.
        </EmptyState>
      )
    }

    return (
      <ul className="flight-list" aria-busy={flightsReq.loading}>
        {visible.map((flight) => (
          <li key={flight.id}>
            <FlightCard flight={flight} airports={airports} />
          </li>
        ))}
      </ul>
    )
  }

  const ready = flightsReq.data && airportsReq.data && !flightsReq.error && visible.length > 0

  return (
    <>
      <section className="search-band" aria-labelledby="search-title">
        <div className="container">
          <h1 className="page-title" id="search-title">
            Find a flight
          </h1>
          <p className="page-subtitle">
            Direct flights, one price per seat. Browse freely, log in when you're ready to book.
          </p>
          <SearchForm
            key={query}
            initial={filters}
            airports={airportsReq.data}
            onSearch={search}
          />
        </div>
      </section>

      <section className="container page" aria-labelledby="results-title">
        <div className="results-bar">
          <h2 className="results-count" id="results-title" aria-live="polite">
            {ready
              ? `${pluralize(visible.length, "flight")}${hasFilters ? " found" : ""}`
              : hasFilters
                ? "Search results"
                : "All flights"}
          </h2>
          {ready && (
            <div className="btn-row">
              {hasFilters && (
                <button type="button" className="btn btn-ghost" onClick={() => setParams({})}>
                  Clear filters
                </button>
              )}
              {pastCount > 0 && (
                <button type="button" className="btn btn-ghost" onClick={() => togglePast(!showPast)}>
                  {showPast ? "Hide past flights" : `Show ${pluralize(pastCount, "past flight")}`}
                </button>
              )}
            </div>
          )}
        </div>
        {ready && pageFull && (
          <p className="muted">
            Showing the first {SEARCH_PAGE_SIZE} matches by departure time. Narrow the search to see
            the rest.
          </p>
        )}
        {renderResults()}
      </section>
    </>
  )
}
