import { useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react"
import { AlertIcon } from "./Icons"

interface FieldShellProps {
  id: string
  label: string
  optional?: boolean
  hint?: string
  error?: string
  className?: string
  children: ReactNode
}

function FieldShell({ id, label, optional, hint, error, className, children }: FieldShellProps) {
  return (
    <div className={`field ${className ?? ""}`}>
      <label className="field-label" htmlFor={id}>
        {label}
        {optional && <span className="field-optional"> (optional)</span>}
      </label>
      {children}
      {hint && !error && (
        <p className="field-hint" id={`${id}-hint`}>
          {hint}
        </p>
      )}
      {error && (
        <p className="field-error" id={`${id}-error`}>
          <AlertIcon />
          {error}
        </p>
      )}
    </div>
  )
}

function describedBy(id: string, hint?: string, error?: string): string | undefined {
  if (error) return `${id}-error`
  if (hint) return `${id}-hint`
  return undefined
}

type TextFieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, "className"> & {
  label: string
  optional?: boolean
  hint?: string
  error?: string
  className?: string
}

export function TextField({ label, optional, hint, error, className, id, ...input }: TextFieldProps) {
  const autoId = useId()
  const inputId = id ?? autoId
  return (
    <FieldShell
      id={inputId}
      label={label}
      optional={optional}
      hint={hint}
      error={error}
      className={className}
    >
      <input
        id={inputId}
        className="input"
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(inputId, hint, error)}
        {...input}
      />
    </FieldShell>
  )
}

type SelectFieldProps = Omit<SelectHTMLAttributes<HTMLSelectElement>, "className"> & {
  label: string
  optional?: boolean
  hint?: string
  error?: string
  className?: string
  children: ReactNode
}

export function SelectField({
  label,
  optional,
  hint,
  error,
  className,
  id,
  children,
  ...select
}: SelectFieldProps) {
  const autoId = useId()
  const selectId = id ?? autoId
  return (
    <FieldShell
      id={selectId}
      label={label}
      optional={optional}
      hint={hint}
      error={error}
      className={className}
    >
      <select
        id={selectId}
        className="input"
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(selectId, hint, error)}
        {...select}
      >
        {children}
      </select>
    </FieldShell>
  )
}
