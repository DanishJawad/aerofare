import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react"
import { Link, useLocation, useNavigate } from "react-router-dom"
import { ApiError, api } from "../api"
import { useAuth } from "../auth/context"
import { Alert, Spinner } from "../components/Feedback"
import { TextField } from "../components/Field"
import { validateNewPassword } from "../lib/validation"

type PwField = "new_password" | "confirm"

/**
 * The email links to /reset-password#token=... The fragment never reaches a server
 * (no access logs, no Referer), but it would stay in browser history, so the page
 * strips it as soon as it has read it.
 */
function readTokenFromHash(): string | null {
  return new URLSearchParams(window.location.hash.slice(1)).get("token") || null
}

export function ResetPasswordPage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const { pathname, search, hash } = useLocation()
  // Lazy initializer: read once on mount and keep it in state. The initializer has no
  // side effects, so StrictMode calling it twice reads the same hash both times.
  const [token] = useState(readTokenFromHash)
  const [values, setValues] = useState<Record<PwField, string>>({ new_password: "", confirm: "" })
  const [errors, setErrors] = useState<Partial<Record<PwField, string>>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [linkDead, setLinkDead] = useState(false)
  const newLink = useRef<HTMLAnchorElement>(null)

  // Drop the token from the address bar. Safe to run twice: the second run finds no hash.
  // Going through the router (a replace, i.e. history.replaceState) keeps useLocation in sync.
  useEffect(() => {
    if (hash) navigate({ pathname, search }, { replace: true })
  }, [hash, pathname, search, navigate])

  // The form is replaced when the link turns out to be dead; move focus to the way out.
  useEffect(() => {
    if (linkDead) newLink.current?.focus()
  }, [linkDead])

  const bind = (key: PwField) => ({
    value: values[key],
    onChange: (e: ChangeEvent<HTMLInputElement>) =>
      setValues((prev) => ({ ...prev, [key]: e.target.value })),
    error: errors[key],
  })

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!token) return
    const found: Partial<Record<PwField, string>> = {}
    const pwError = validateNewPassword(values.new_password)
    if (pwError) found.new_password = pwError
    if (values.confirm !== values.new_password) found.confirm = "Doesn't match the new password."
    setErrors(found)
    setFormError(null)
    if (Object.keys(found).length > 0) return

    setSubmitting(true)
    try {
      await api.resetPassword(token, values.new_password)
    } catch (err) {
      if (err instanceof ApiError && err.code === "invalid_reset_token") {
        setLinkDead(true)
      } else if (err instanceof ApiError && err.fieldErrors.new_password) {
        setErrors({ new_password: err.fieldErrors.new_password })
      } else {
        setFormError(err instanceof ApiError ? err.message : "Something unexpected went wrong.")
      }
      setSubmitting(false)
      return
    }

    // The reset ended every session, this browser's included. If someone was logged in
    // here, clear them out of the app too, or LoginPage would bounce them as if still in.
    if (user) await logout()
    navigate("/login", { replace: true, state: { passwordReset: true } })
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1 className="auth-title">Choose a new password</h1>
        <p className="page-subtitle mb-6">
          You'll use it to log in from now on. Anywhere you're still logged in will be logged out.
        </p>

        <div className="card">
          {!token || linkDead ? (
            <div className="card-body stack">
              {linkDead ? (
                <Alert tone="error" title="This reset link is invalid or has expired">
                  Links work once and expire 15 minutes after we send them. Request a new one to
                  continue.
                </Alert>
              ) : (
                <Alert tone="warning" title="This reset link is incomplete">
                  Open the link from your email again. If that doesn't work, request a new one.
                </Alert>
              )}
              <Link ref={newLink} to="/forgot-password" className="btn btn-primary btn-lg btn-block">
                Request a new link
              </Link>
            </div>
          ) : (
            <form className="card-body stack" onSubmit={submit} noValidate>
              {formError && <Alert tone="error">{formError}</Alert>}
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
              <button
                type="submit"
                className="btn btn-primary btn-lg btn-block"
                disabled={submitting}
              >
                {submitting && <Spinner />}
                {submitting ? "Updating password…" : "Update password"}
              </button>
            </form>
          )}
        </div>

        <p className="auth-footer">
          Remembered it? <Link to="/login">Log in</Link>
        </p>
      </div>
    </div>
  )
}
