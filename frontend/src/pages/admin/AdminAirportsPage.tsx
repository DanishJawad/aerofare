import { useId, useState, type ChangeEvent, type FormEvent } from "react"
import { ApiError, api } from "../../api"
import { Dialog } from "../../components/Dialog"
import { Alert, EmptyState, ErrorState, Skeleton, Spinner } from "../../components/Feedback"
import { TextField } from "../../components/Field"
import { PinIcon, PlusIcon } from "../../components/Icons"
import { invalidateAirports } from "../../lib/data"
import { useAsync } from "../../lib/useAsync"
import type { Airport, AirportInput } from "../../types"

type Field = keyof AirportInput

function AirportDialog({
  airport,
  open,
  onClose,
  onSaved,
}: {
  airport: Airport | null
  open: boolean
  onClose: () => void
  onSaved: (a: Airport) => void
}) {
  const formId = useId()
  const initial: AirportInput = airport
    ? { name: airport.name, city: airport.city, country: airport.country }
    : { name: "", city: "", country: "" }
  const [values, setValues] = useState(initial)
  const [errors, setErrors] = useState<Partial<Record<Field, string>>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const bind = (key: Field) => ({
    value: values[key],
    onChange: (e: ChangeEvent<HTMLInputElement>) =>
      setValues((prev) => ({ ...prev, [key]: e.target.value })),
    error: errors[key],
  })

  async function submit(e: FormEvent) {
    e.preventDefault()
    const found: Partial<Record<Field, string>> = {}
    if (!values.name.trim()) found.name = "Enter the airport name."
    if (!values.city.trim()) found.city = "Enter the city."
    if (!values.country.trim()) found.country = "Enter the country."
    setErrors(found)
    setFormError(null)
    if (Object.keys(found).length > 0) return

    const clean: AirportInput = {
      name: values.name.trim(),
      city: values.city.trim(),
      country: values.country.trim(),
    }
    setSaving(true)
    try {
      let saved: Airport
      if (airport) {
        const patch: Partial<AirportInput> = {}
        for (const k of Object.keys(clean) as Field[]) if (clean[k] !== initial[k]) patch[k] = clean[k]
        saved = Object.keys(patch).length ? await api.updateAirport(airport.id, patch) : airport
      } else {
        saved = await api.createAirport(clean)
      }
      onSaved(saved)
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors(err.fieldErrors)
        setFormError(err.message)
      } else setFormError("Something unexpected went wrong.")
      setSaving(false)
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={airport ? `Edit ${airport.name}` : "Add airport"}
      locked={saving}
      actions={
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button type="submit" form={formId} className="btn btn-primary" disabled={saving}>
            {saving && <Spinner />}
            {saving ? "Saving…" : airport ? "Save changes" : "Add airport"}
          </button>
        </>
      }
    >
      <form id={formId} className="stack" onSubmit={submit} noValidate>
        {formError && <Alert tone="error">{formError}</Alert>}
        <TextField label="Airport name" {...bind("name")} hint="e.g. Allama Iqbal International" />
        <div className="form-grid form-grid-2">
          <TextField label="City" {...bind("city")} />
          <TextField label="Country" {...bind("country")} />
        </div>
      </form>
    </Dialog>
  )
}

export function AdminAirportsPage() {
  const req = useAsync(api.listAirports, [])
  // `editing`: undefined = closed, null = creating, Airport = editing that one.
  const [editing, setEditing] = useState<Airport | null | undefined>(undefined)
  const [notice, setNotice] = useState<string | null>(null)

  function body() {
    if (req.error) return <ErrorState message={req.error.message} onRetry={req.reload} />
    if (!req.data) {
      return (
        <div className="table-wrap card-body stack" role="status" aria-label="Loading airports">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} height={24} />
          ))}
        </div>
      )
    }
    if (req.data.length === 0) {
      return (
        <EmptyState icon={<PinIcon size={24} />} title="No airports yet">
          Flights need a departure and an arrival airport, so add at least two before creating
          flights.
        </EmptyState>
      )
    }
    const rows = [...req.data].sort((a, b) => a.city.localeCompare(b.city))
    return (
      <div className="table-wrap" aria-busy={req.loading}>
        <table className="table table-stack">
          <caption className="visually-hidden">Airports</caption>
          <thead>
            <tr>
              <th scope="col">ID</th>
              <th scope="col">Name</th>
              <th scope="col">City</th>
              <th scope="col">Country</th>
              <th scope="col" className="cell-actions">
                <span className="visually-hidden">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => (
              <tr key={a.id}>
                <td data-label="ID" className="num">
                  {a.id}
                </td>
                <td data-label="Name">{a.name}</td>
                <td data-label="City">{a.city}</td>
                <td data-label="Country">{a.country}</td>
                <td className="cell-actions">
                  <button
                    type="button"
                    className="btn btn-ghost"
                    onClick={() => setEditing(a)}
                    aria-label={`Edit ${a.name}`}
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
          <h1 className="admin-title">Airports</h1>
          {req.data && <p className="muted">{req.data.length} total</p>}
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setEditing(null)}>
          <PlusIcon />
          Add airport
        </button>
      </div>
      {notice && <Alert tone="success">{notice}</Alert>}
      {body()}
      {editing !== undefined && (
        <AirportDialog
          key={editing?.id ?? "new"}
          airport={editing}
          open
          onClose={() => setEditing(undefined)}
          onSaved={(a) => {
            setNotice(editing ? `Saved changes to ${a.name}.` : `Added ${a.name}.`)
            setEditing(undefined)
            invalidateAirports()
            req.reload()
          }}
        />
      )}
    </div>
  )
}
