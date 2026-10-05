import { useState, type FormEvent } from "react"
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom"
import { ApiError } from "../api"
import { useAuth } from "../auth/context"
import { Alert, Spinner } from "../components/Feedback"
import { TextField } from "../components/Field"

interface LoginState {
  from?: string
  reason?: "expired"
  signedUp?: string
}

/** Only follow same-app paths, never an absolute URL smuggled into state. */
function safeFrom(from: string | undefined): string {
  return from && from.startsWith("/") && !from.startsWith("//") ? from : "/"
}

export function LoginPage() {
  const { login, user } = useAuth()
  const navigate = useNavigate()
  const state = (useLocation().state ?? {}) as LoginState
  const [email, setEmail] = useState(state.signedUp ?? "")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (user && !submitting) return <Navigate to={safeFrom(state.from)} replace />

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!email.trim() || !password) {
      setError("Enter your email and password.")
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await login(email.trim(), password)
      navigate(safeFrom(state.from), { replace: true })
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401
          ? "That email and password don't match an account. Check both and try again."
          : err instanceof ApiError
            ? err.message
            : "Something unexpected went wrong.",
      )
      setSubmitting(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1 className="auth-title">Log in</h1>
        <p className="page-subtitle mb-6">
          Book flights and manage your trips.
        </p>

        <div className="card">
          <form className="card-body stack" onSubmit={submit} noValidate>
            {state.reason === "expired" && !error && (
              <Alert tone="info" title="Your session ended">
                For your security we log you out after a while. Log in again to pick up where you
                left off.
              </Alert>
            )}
            {state.signedUp && !error && (
              <Alert tone="success" title="Account created">
                Log in with your new password to continue.
              </Alert>
            )}
            {error && <Alert tone="error">{error}</Alert>}

            <TextField
              label="Email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <TextField
              label="Password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <button type="submit" className="btn btn-primary btn-lg btn-block" disabled={submitting}>
              {submitting && <Spinner />}
              {submitting ? "Logging in…" : "Log in"}
            </button>
          </form>
        </div>

        <p className="auth-footer">
          New to Aerofare?{" "}
          <Link to="/signup" state={{ from: state.from }}>
            Create an account
          </Link>
        </p>
      </div>
    </div>
  )
}
