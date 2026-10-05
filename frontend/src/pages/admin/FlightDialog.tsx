import { useId, useState, type ChangeEvent, type FormEvent } from "react"
import { ApiError, api } from "../../api"
import { Dialog } from "../../components/Dialog"
import { Alert, Spinner } from "../../components/Feedback"
import { SelectField, TextField } from "../../components/Field"
import { CLASS_LABELS, apiToLocalInput, localInputToApi, localTimeZoneLabel } from "../../lib/format"
import type { Airport, Flight, FlightClass, FlightInput } from "../../types"

type Field = keyof FlightInput
type Values = Record<Field, string>

function toValues(flight: Flight | null): Values {
  if (!flight) {
    return {
      airline_name: "",
      departure_airport: "",
      arrival_airport: "",
      start_time: "",
      end_time: "",
      price: "",
      total_seats: "",
      available_seats: "",
      flight_class: "economy",
    }
  }
  return {
    airline_name: flight.airline_name,
    departure_airport: String(flight.departure_airport),
    arrival_airport: String(flight.arrival_airport),
    start_time: apiToLocalInput(flight.start_time),
    end_time: apiToLocalInput(flight.end_time),
    price: flight.price,
    total_seats: String(flight.total_seats),
    available_seats: String(flight.available_seats),
    flight_class: flight.flight_class,
  }
}

const isWholeNumber = (v: string) => /^\d+$/.test(v)

/**
 * The server only checks cross-field rules on create, not on PATCH,
 * so the same rules run here for both.
 */
function validate(v: Values): Partial<Record<Field, string>> {
  const e: Partial<Record<Field, string>> = {}
  if (!v.airline_name.trim()) e.airline_name = "Enter the airline."
  else if (v.airline_name.trim().length > 50) e.airline_name = "Use 50 characters or fewer."
  if (!v.departure_airport) e.departure_airport = "Choose where the flight leaves from."
  if (!v.arrival_airport) e.arrival_airport = "Choose where the flight lands."
  else if (v.arrival_airport === v.departure_airport)
    e.arrival_airport = "Must be different from the departure airport."
  if (!v.start_time) e.start_time = "Enter the departure time."
  if (!v.end_time) e.end_time = "Enter the arrival time."
  else if (v.start_time && new Date(v.end_time) <= new Date(v.start_time))
    e.end_time = "Must be after the departure time."
  if (!/^\d+(\.\d{1,2})?$/.test(v.price)) e.price = "Enter a price like 150 or 150.00."
  if (!isWholeNumber(v.total_seats) || Number(v.total_seats) < 1)
    e.total_seats = "Enter a whole number of 1 or more."
  if (!isWholeNumber(v.available_seats)) e.available_seats = "Enter a whole number of 0 or more."
  else if (isWholeNumber(v.total_seats) && Number(v.available_seats) > Number(v.total_seats))
    e.available_seats = "Can't be more than the total seats."
  return e
}

function toInput(v: Values): FlightInput {
  return {
    airline_name: v.airline_name.trim(),
    departure_airport: Number(v.departure_airport),
    arrival_airport: Number(v.arrival_airport),
    start_time: localInputToApi(v.start_time),
    end_time: localInputToApi(v.end_time),
    price: Number(v.price).toFixed(2),
    total_seats: Number(v.total_seats),
    available_seats: Number(v.available_seats),
    flight_class: v.flight_class as FlightClass,
  }
}

/** Route model_validator messages (loc: ["body"]) to the field they are about. */
function fieldForServerMessage(msg: string): Field | null {
  if (/end_time/i.test(msg)) return "end_time"
  if (/available_seats/i.test(msg)) return "available_seats"
  if (/airports must differ/i.test(msg)) return "arrival_airport"
  return null
}

export function FlightDialog({
  flight,
  airports,
  onClose,
  onSaved,
}: {
  flight: Flight | null
  airports: Airport[]
  onClose: () => void
  onSaved: (f: Flight) => void
}) {
  const formId = useId()
  const initial = toValues(flight)
  const [values, setValues] = useState<Values>(initial)
  const [errors, setErrors] = useState<Partial<Record<Field, string>>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const bind = (key: Field) => ({
    value: values[key],
    onChange: (e: ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setValues((prev) => {
        const next = { ...prev, [key]: e.target.value }
        // New flights start fully available unless the admin says otherwise.
        if (!flight && key === "total_seats" && prev.available_seats === prev.total_seats) {
          next.available_seats = e.target.value
        }
        return next
      }),
    error: errors[key],
  })

  async function submit(e: FormEvent) {
    e.preventDefault()
    const found = validate(values)
    setErrors(found)
    setFormError(null)
    if (Object.keys(found).length > 0) return

    const input = toInput(values)
    setSaving(true)
    try {
      let saved: Flight
      if (flight) {
        const before = toInput(initial)
        const patch: Partial<FlightInput> = {}
        for (const k of Object.keys(input) as Field[]) {
          if (input[k] !== before[k]) Object.assign(patch, { [k]: input[k] })
        }
        saved = Object.keys(patch).length ? await api.updateFlight(flight.id, patch) : flight
      } else {
        saved = await api.createFlight(input)
      }
      onSaved(saved)
    } catch (err) {
      if (err instanceof ApiError) {
        const field = fieldForServerMessage(err.message)
        if (field) setErrors({ ...err.fieldErrors, [field]: err.message })
        else {
          setErrors(err.fieldErrors)
          setFormError(err.message)
        }
      } else setFormError("Something unexpected went wrong.")
      setSaving(false)
    }
  }

  const sorted = [...airports].sort((a, b) => a.city.localeCompare(b.city))
  const options = sorted.map((a) => (
    <option key={a.id} value={a.id}>
      {a.city} ({a.name})
    </option>
  ))
  const booked =
    flight && isWholeNumber(values.total_seats) && isWholeNumber(values.available_seats)
      ? Number(values.total_seats) - Number(values.available_seats)
      : null

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title={flight ? `Edit flight #${flight.id}` : "Add flight"}
      locked={saving}
      actions={
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button type="submit" form={formId} className="btn btn-primary" disabled={saving}>
            {saving && <Spinner />}
            {saving ? "Saving…" : flight ? "Save changes" : "Add flight"}
          </button>
        </>
      }
    >
      <form id={formId} className="stack" onSubmit={submit} noValidate>
        {formError && <Alert tone="error">{formError}</Alert>}
        <div className="form-grid form-grid-2">
          <TextField label="Airline" className="span-2" maxLength={50} {...bind("airline_name")} />
          <SelectField label="From" {...bind("departure_airport")}>
            <option value="">Choose airport</option>
            {options}
          </SelectField>
          <SelectField label="To" {...bind("arrival_airport")}>
            <option value="">Choose airport</option>
            {options}
          </SelectField>
          <TextField
            label="Departs"
            type="datetime-local"
            hint={`Your time zone (${localTimeZoneLabel()}). Saved as UTC.`}
            {...bind("start_time")}
          />
          <TextField
            label="Arrives"
            type="datetime-local"
            min={values.start_time || undefined}
            {...bind("end_time")}
          />
          <TextField
            label="Price per seat ($)"
            type="number"
            inputMode="decimal"
            min={0}
            step="0.01"
            {...bind("price")}
          />
          <SelectField label="Cabin class" {...bind("flight_class")}>
            {Object.entries(CLASS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </SelectField>
          <TextField
            label="Total seats"
            type="number"
            inputMode="numeric"
            min={1}
            step={1}
            {...bind("total_seats")}
          />
          <TextField
            label="Available seats"
            type="number"
            inputMode="numeric"
            min={0}
            step={1}
            hint={
              booked !== null && booked > 0
                ? `${booked} currently booked by customers.`
                : "Usually the same as total seats for a new flight."
            }
            {...bind("available_seats")}
          />
        </div>
      </form>
    </Dialog>
  )
}
