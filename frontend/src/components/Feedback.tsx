import type { ReactNode } from "react"
import { AlertIcon, CheckIcon, InfoIcon } from "./Icons"

export function Spinner({ label }: { label?: string }) {
  return (
    <>
      <span className="spinner" aria-hidden="true" />
      {label && <span className="visually-hidden">{label}</span>}
    </>
  )
}

export function PageSpinner({ label = "Loading" }: { label?: string }) {
  return (
    <div className="page-spinner" role="status">
      <span className="spinner" aria-hidden="true" />
      <span>{label}…</span>
    </div>
  )
}

type AlertTone = "error" | "success" | "info" | "warning"

const ALERT_ICONS: Record<AlertTone, ReactNode> = {
  error: <AlertIcon />,
  warning: <AlertIcon />,
  success: <CheckIcon />,
  info: <InfoIcon />,
}

export function Alert({
  tone,
  title,
  children,
}: {
  tone: AlertTone
  title?: string
  children?: ReactNode
}) {
  // Errors interrupt screen readers; everything else waits its turn.
  const role = tone === "error" ? "alert" : "status"
  return (
    <div className={`alert alert-${tone}`} role={role}>
      {ALERT_ICONS[tone]}
      <div className="alert-body">
        {title && <p className="alert-title">{title}</p>}
        {children && <div>{children}</div>}
      </div>
    </div>
  )
}

export function EmptyState({
  icon,
  title,
  children,
  action,
}: {
  icon: ReactNode
  title: string
  children?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="state">
      <div className="state-icon">{icon}</div>
      <h2 className="state-title">{title}</h2>
      {children && <p className="state-text">{children}</p>}
      {action}
    </div>
  )
}

export function ErrorState({
  title = "We couldn't load this",
  message,
  onRetry,
}: {
  title?: string
  message: string
  onRetry?: () => void
}) {
  return (
    <div className="state state-error" role="alert">
      <div className="state-icon">
        <AlertIcon size={24} />
      </div>
      <h2 className="state-title">{title}</h2>
      <p className="state-text">{message}</p>
      {onRetry && (
        <button type="button" className="btn btn-secondary" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  )
}

export function Skeleton({ height, width = "100%" }: { height: number; width?: string | number }) {
  return <span className="skeleton" style={{ height, width }} aria-hidden="true" />
}

/** A list of card-shaped placeholders sized like the real rows, so nothing jumps on load. */
export function SkeletonList({ rows = 4, height = 112 }: { rows?: number; height?: number }) {
  return (
    <div className="flight-list" role="status" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} height={height} />
      ))}
    </div>
  )
}
