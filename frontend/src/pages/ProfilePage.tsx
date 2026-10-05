import { useState, type ChangeEvent, type FormEvent } from "react"
import { ApiError, api } from "../api"
import { useAuth } from "../auth/context"
import { Alert, Spinner } from "../components/Feedback"
import { TextField } from "../components/Field"
import { validateNewPassword, validateProfile, type ProfileField } from "../lib/validation"
import type { User, UserUpdate } from "../types"

type ProfileValues = Record<ProfileField, string>

function toValues(user: User): ProfileValues {
  return {
    name: user.name,
    email: user.email,
    phone_number: user.phone_number ?? "",
    city: user.city,
    country: user.country,
  }
}

function DetailsForm({ user, onSaved }: { user: User; onSaved: (u: User) => void }) {
  const saved = toValues(user)
  const [values, setValues] = useState<ProfileValues>(saved)
  const [errors, setErrors] = useState<Partial<Record<ProfileField, string>>>({})
  const [status, setStatus] = useState<"idle" | "saving" | "saved">("idle")
  const [formError, setFormError] = useState<string | null>(null)

  const changed = (Object.keys(values) as ProfileField[]).filter(
    (k) => values[k].trim() !== saved[k],
  )

  const bind = (key: ProfileField) => ({
    value: values[key],
    onChange: (e: ChangeEvent<HTMLInputElement>) => {
      setValues((prev) => ({ ...prev, [key]: e.target.value }))
      setStatus("idle")
    },
    error: errors[key],
  })

  async function submit(e: FormEvent) {
    e.preventDefault()
    const found = validateProfile(values)
    setErrors(found)
    setFormError(null)
    if (Object.keys(found).length > 0 || changed.length === 0) return

    // PATCH only what changed.
    const patch: UserUpdate = {}
    for (const k of changed) {
      const v = values[k].trim()
      if (k === "phone_number") patch.phone_number = v || null
      else patch[k] = v
    }

    setStatus("saving")
    try {
      const updated = await api.updateMe(patch)
      onSaved(updated)
      setValues(toValues(updated))
      setStatus("saved")
    } catch (err) {
      setStatus("idle")
      if (err instanceof ApiError && err.status === 409) {
        setErrors({ email: "Another account already uses this email." })
      } else if (err instanceof ApiError) {
        setErrors(err.fieldErrors)
        setFormError(err.message)
      } else {
        setFormError("Something unexpected went wrong.")
      }
    }
  }

  return (
    <section className="card" aria-labelledby="details-title">
      <div className="card-header">
        <h2 className="section-title flush" id="details-title">
          Personal details
        </h2>
      </div>
      <form className="card-body" onSubmit={submit} noValidate>
        <div className="stack">
          {formError && <Alert tone="error">{formError}</Alert>}
          {status === "saved" && <Alert tone="success">Your details are saved.</Alert>}
          <div className="form-grid form-grid-2">
            <TextField label="Full name" autoComplete="name" className="span-2" {...bind("name")} />
            <TextField
              label="Email"
              type="email"
              autoComplete="email"
              className="span-2"
              hint="You log in with this."
              {...bind("email")}
            />
            <TextField
              label="Phone number"
              type="tel"
              autoComplete="tel"
              optional
              className="span-2"
              {...bind("phone_number")}
            />
            <TextField label="City" autoComplete="address-level2" {...bind("city")} />
            <TextField label="Country" autoComplete="country-name" {...bind("country")} />
          </div>
        </div>
        <div className="form-actions">
          <button
            type="submit"
            className="btn btn-primary"
            disabled={status === "saving" || changed.length === 0}
          >
            {status === "saving" && <Spinner />}
            {status === "saving" ? "Saving…" : "Save changes"}
          </button>
          {changed.length > 0 && status !== "saving" && (
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => {
                setValues(saved)
                setErrors({})
              }}
            >
              Discard
            </button>
          )}
        </div>
      </form>
    </section>
  )
}

type PwField = "current_password" | "new_password" | "confirm"

function PasswordForm() {
  const empty = { current_password: "", new_password: "", confirm: "" }
  const [values, setValues] = useState<Record<PwField, string>>(empty)
  const [errors, setErrors] = useState<Partial<Record<PwField, string>>>({})
  const [status, setStatus] = useState<"idle" | "saving" | "saved">("idle")
  const [formError, setFormError] = useState<string | null>(null)

  const bind = (key: PwField) => ({
    value: values[key],
    onChange: (e: ChangeEvent<HTMLInputElement>) => {
      setValues((prev) => ({ ...prev, [key]: e.target.value }))
      setStatus("idle")
    },
    error: errors[key],
  })

  async function submit(e: FormEvent) {
    e.preventDefault()
    const found: Partial<Record<PwField, string>> = {}
    if (!values.current_password) found.current_password = "Enter your current password."
    const pwError = validateNewPassword(values.new_password)
    if (pwError) found.new_password = pwError
    else if (values.new_password === values.current_password)
      found.new_password = "Choose a password you haven't used here before."
    if (values.confirm !== values.new_password) found.confirm = "Doesn't match the new password."
    setErrors(found)
    setFormError(null)
    if (Object.keys(found).length > 0) return

    setStatus("saving")
    try {
      await api.changePassword({
        current_password: values.current_password,
        new_password: values.new_password,
      })
      setValues(empty)
      setStatus("saved")
    } catch (err) {
      setStatus("idle")
      if (err instanceof ApiError && err.status === 400) {
        setErrors({ current_password: "That isn't your current password." })
      } else if (err instanceof ApiError) {
        setErrors(err.fieldErrors)
        setFormError(err.message)
      } else {
        setFormError("Something unexpected went wrong.")
      }
    }
  }

  return (
    <section className="card" aria-labelledby="password-title">
      <div className="card-header">
        <h2 className="section-title flush" id="password-title">
          Password
        </h2>
      </div>
      <form className="card-body" onSubmit={submit} noValidate>
        <div className="stack">
          {formError && <Alert tone="error">{formError}</Alert>}
          {status === "saved" && <Alert tone="success">Password updated. Use it next time you log in.</Alert>}
          <div className="form-grid">
            <TextField
              label="Current password"
              type="password"
              autoComplete="current-password"
              {...bind("current_password")}
            />
            <TextField
              label="New password"
              type="password"
              autoComplete="new-password"
              hint="At least 8 characters."
              {...bind("new_password")}
            />
            <TextField
              label="Confirm new password"
              type="password"
              autoComplete="new-password"
              {...bind("confirm")}
            />
          </div>
        </div>
        <div className="form-actions">
          <button type="submit" className="btn btn-secondary" disabled={status === "saving"}>
            {status === "saving" && <Spinner />}
            {status === "saving" ? "Updating…" : "Update password"}
          </button>
        </div>
      </form>
    </section>
  )
}

export function ProfilePage() {
  const { user, setUser, logout } = useAuth()
  const [loggingOut, setLoggingOut] = useState(false)
  if (!user) return null // RequireAuth guarantees a user; this satisfies the type

  return (
    <div className="container container-reading page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Profile</h1>
          <p className="page-subtitle">{user.email}</p>
        </div>
        {user.is_admin && <span className="badge badge-accent">Admin account</span>}
      </div>

      <div className="stack-lg">
        {/* key: remount with fresh values if the user object is replaced */}
        <DetailsForm key={user.id} user={user} onSaved={setUser} />
        <PasswordForm />

        <section className="card" aria-labelledby="session-title">
          <div className="card-body stack">
            <h2 className="section-title flush" id="session-title">
              Log out
            </h2>
            <p className="muted">
              Ends your session on the server as well as in this browser, so this login can't be
              reused.
            </p>
            <div>
              <button
                type="button"
                className="btn btn-danger-outline"
                disabled={loggingOut}
                onClick={() => {
                  setLoggingOut(true)
                  void logout()
                }}
              >
                {loggingOut && <Spinner />}
                {loggingOut ? "Logging out…" : "Log out"}
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
