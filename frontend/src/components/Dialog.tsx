import { useEffect, useId, useRef, useState, type ReactNode } from "react"
import { ApiError } from "../api"
import { Alert, Spinner } from "./Feedback"

interface DialogProps {
  open: boolean
  onClose: () => void
  title: string
  wide?: boolean
  children: ReactNode
  /** Rendered in the grey footer strip. */
  actions: ReactNode
  /** Block Escape / backdrop dismissal while a request is in flight. */
  locked?: boolean
}

/**
 * Native <dialog> with showModal(): the browser handles focus trapping,
 * Escape to close, and making the page behind it inert.
 */
export function Dialog({ open, onClose, title, wide, children, actions, locked }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      className={`dialog ${wide ? "dialog-wide" : ""}`}
      aria-labelledby={titleId}
      onCancel={(e) => {
        e.preventDefault() // keep React state as the single source of truth
        if (!locked) onClose()
      }}
    >
      {open && (
        <>
          <div className="dialog-body">
            <h2 className="dialog-title" id={titleId}>
              {title}
            </h2>
            {children}
          </div>
          <div className="dialog-actions">{actions}</div>
        </>
      )}
    </dialog>
  )
}

interface ConfirmDialogProps {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  confirmLabel: string
  pendingLabel: string
  cancelLabel?: string
  onConfirm: () => Promise<void>
}

/** Confirmation for destructive actions. Shows the server's error inline if the action fails. */
export function ConfirmDialog({
  open,
  onClose,
  title,
  children,
  confirmLabel,
  pendingLabel,
  cancelLabel = "Keep it",
  onConfirm,
}: ConfirmDialogProps) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function close() {
    setError(null)
    onClose()
  }

  async function confirm() {
    setPending(true)
    setError(null)
    try {
      await onConfirm()
      onClose()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something unexpected went wrong.")
    } finally {
      setPending(false)
    }
  }

  return (
    <Dialog
      open={open}
      onClose={close}
      title={title}
      locked={pending}
      actions={
        <>
          <button type="button" className="btn btn-secondary" onClick={close} disabled={pending}>
            {cancelLabel}
          </button>
          <button type="button" className="btn btn-danger" onClick={confirm} disabled={pending}>
            {pending && <Spinner />}
            {pending ? pendingLabel : confirmLabel}
          </button>
        </>
      }
    >
      <div className="stack">
        <div className="dialog-text">{children}</div>
        {error && <Alert tone="error" title="That didn't work">{error}</Alert>}
      </div>
    </Dialog>
  )
}
