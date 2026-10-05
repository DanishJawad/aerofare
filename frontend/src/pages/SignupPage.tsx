import { useState, type ChangeEvent, type FormEvent } from "react"
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom"
import { ApiError, api } from "../api"
import { useAuth } from "../auth/context"
import { Alert, Spinner } from "../components/Feedback"
import { TextField } from "../components/Field"
import { validateNewPassword, validateProfile, type ProfileField } from "../lib/validation"

type Fields = ProfileField | "password"
type Values = Record<Fields, string>

const EMPTY: Values = { name: "", email: "", password: "", phone_number: "", city: "", country: "" }

export function SignupPage() {
  const { login, user } = useAuth()
  const navigate = useNavigate()
  const from = (useLocation().state as { from?: string } | null)?.from
  const [values, setValues] = useState<Values>(EMPTY)
  const [errors, setErrors] = useState<Partial<Record<Fields, string>>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (user && !submitting) return <Navigate to="/" replace />

  const bind = (key: Fields) => ({
    value: values[key],
    onChange: (e: ChangeEvent<HTMLInputElement>) =>
      setValues((prev) => ({ ...prev, [key]: e.target.value })),
    error: errors[key],
  })

  async function submit(e: FormEvent) {
    e.preventDefault()
    const found: Partial<Record<Fields, string>> = validateProfile(values)
    const pwError = validateNewPassword(values.password)
    if (pwError) found.password = pwError
    setErrors(found)
    setFormError(null)
    if (Object.keys(found).length > 0) return

    setSubmitting(true)
    const email = values.email.trim()
    try {
      await api.signup({
        name: values.name.trim(),
        email,
        password: values.password,
        phone_number: values.phone_number.trim() || null,
        city: values.city.trim(),
        country: values.country.trim(),
      })
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setErrors({ email: "An account with this email already exists. Log in instead." })
      } else if (err instanceof ApiError) {
        setErrors(err.fieldErrors)
        setFormError(err.message)
      } else {
        setFormError("Something unexpected went wrong.")
      }
      setSubmitting(false)
      return
    }

    // Account exists now: log straight in rather than making them type it again.
    try {
      await login(email, values.password)
      navigate(from && from.startsWith("/") ? from : "/", { replace: true })
    } catch {
      navigate("/login", { replace: true, state: { signedUp: email, from } })
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card auth-card-wide">
        <h1 className="auth-title">Create an account</h1>
        <p className="page-subtitle mb-6">
          You'll need one to book. It takes under a minute.
        </p>

        <div className="card">
          <form className="card-body" onSubmit={submit} noValidate>
            {formError && (
              <div className="mb-4">
                <Alert tone="error">{formError}</Alert>
              </div>
            )}
            <div className="form-grid form-grid-2">
              <TextField label="Full name" autoComplete="name" className="span-2" {...bind("name")} />
              <TextField
                label="Email"
                type="email"
                autoComplete="email"
                className="span-2"
                {...bind("email")}
              />
              <TextField
                label="Password"
                type="password"
                autoComplete="new-password"
                hint="At least 8 characters."
                className="span-2"
                {...bind("password")}
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
            <div className="form-actions">
              <button type="submit" className="btn btn-primary btn-lg btn-block" disabled={submitting}>
                {submitting && <Spinner />}
                {submitting ? "Creating account…" : "Create account"}
              </button>
            </div>
          </form>
        </div>

        <p className="auth-footer">
          Already have an account?{" "}
          <Link to="/login" state={{ from }}>
            Log in
          </Link>
        </p>
      </div>
    </div>
  )
}
