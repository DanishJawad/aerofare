import { useEffect, useRef, useState, type FormEvent } from "react"
import { Link, useLocation } from "react-router-dom"
import { ApiError, api } from "../api"
import { Alert, Spinner } from "../components/Feedback"
import { TextField } from "../components/Field"
import { validateEmail } from "../lib/validation"

export function ForgotPasswordPage() {
  // LoginPage passes along whatever was typed so nobody enters it twice.
  const prefill = (useLocation().state as { email?: string } | null)?.email ?? ""
  const [email, setEmail] = useState(prefill)
  const [emailError, setEmailError] = useState<string | undefined>()
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [sentTo, setSentTo] = useState<string | null>(null)
  const backLink = useRef<HTMLAnchorElement>(null)

  // The submit button disappears on success; put focus on the next thing to do
  // instead of letting it fall back to <body>.
  useEffect(() => {
    if (sentTo) backLink.current?.focus()
  }, [sentTo])

  async function submit(e: FormEvent) {
    e.preventDefault()
    const found = validateEmail(email)
    setEmailError(found)
    setFormError(null)
    if (found) return

    setSubmitting(true)
    try {
      await api.forgotPassword(email.trim())
      setSentTo(email.trim())
    } catch (err) {
      if (err instanceof ApiError && err.fieldErrors.email) {
        setEmailError(err.fieldErrors.email)
      } else {
        // 429 and network failures both arrive with a message written for people.
        setFormError(err instanceof ApiError ? err.message : "Something unexpected went wrong.")
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1 className="auth-title">Reset your password</h1>
        <p className="page-subtitle mb-6">
          {sentTo
            ? "Open the link in the email to choose a new password."
            : "Enter the email you log in with and we'll send you a link to choose a new password."}
        </p>

        <div className="card">
          {sentTo ? (
            <div className="card-body stack">
              {/* Same wording for every address: the API never says whether an account exists. */}
              <Alert tone="info" title="Check your email">
                If an account exists for {sentTo}, a reset link is on its way. It expires in 15
                minutes.
              </Alert>
              <Link ref={backLink} to="/login" className="btn btn-primary btn-lg btn-block">
                Back to log in
              </Link>
            </div>
          ) : (
            <form className="card-body stack" onSubmit={submit} noValidate>
              {formError && <Alert tone="error">{formError}</Alert>}
              <TextField
                label="Email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                error={emailError}
                required
              />
              <button
                type="submit"
                className="btn btn-primary btn-lg btn-block"
                disabled={submitting}
              >
                {submitting && <Spinner />}
                {submitting ? "Sending link…" : "Send reset link"}
              </button>
            </form>
          )}
        </div>

        {!sentTo && (
          <p className="auth-footer">
            Remembered it? <Link to="/login">Log in</Link>
          </p>
        )}
      </div>
    </div>
  )
}
