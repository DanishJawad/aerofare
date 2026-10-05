import type { BookingStatus, PaymentStatus } from "../types"

type Tone = "success" | "warning" | "danger" | "neutral" | "accent"

const STATUS: Record<BookingStatus | PaymentStatus, { label: string; tone: Tone }> = {
  confirmed: { label: "Confirmed", tone: "success" },
  cancelled: { label: "Cancelled", tone: "neutral" },
  completed: { label: "Paid", tone: "success" },
  pending: { label: "Pending", tone: "warning" },
  failed: { label: "Failed", tone: "danger" },
  refunded: { label: "Refunded", tone: "neutral" },
}

/** Color is backed by the text label, so status never relies on color alone. */
export function StatusBadge({ status }: { status: BookingStatus | PaymentStatus }) {
  const { label, tone } = STATUS[status] ?? { label: status, tone: "neutral" }
  return <span className={`badge badge-${tone}`}>{label}</span>
}

export function Badge({ tone, children }: { tone: Tone; children: string }) {
  return <span className={`badge badge-${tone}`}>{children}</span>
}
