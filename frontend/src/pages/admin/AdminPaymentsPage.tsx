import { useState } from "react"
import { api } from "../../api"
import { ConfirmDialog } from "../../components/Dialog"
import { Alert, EmptyState, ErrorState, Skeleton } from "../../components/Feedback"
import { CardIcon } from "../../components/Icons"
import { StatusBadge } from "../../components/StatusBadge"
import { indexById } from "../../lib/data"
import { formatDateTime, formatMoney, pluralize } from "../../lib/format"
import { useAsync } from "../../lib/useAsync"
import type { Payment, PaymentStatus, User } from "../../types"

type Filter = "all" | PaymentStatus

interface Target {
  payment: Payment
  user?: User
  seats?: number
}

export function AdminPaymentsPage() {
  const req = useAsync(
    () => Promise.all([api.allPayments(), api.allBookings(), api.listUsers()]),
    [],
  )
  const [filter, setFilter] = useState<Filter>("all")
  const [target, setTarget] = useState<Target | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  function body() {
    if (req.error) return <ErrorState message={req.error.message} onRetry={req.reload} />
    if (!req.data) {
      return (
        <div className="table-wrap card-body stack" role="status" aria-label="Loading payments">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} height={24} />
          ))}
        </div>
      )
    }
    const [payments, bookingList, userList] = req.data
    if (payments.length === 0) {
      return (
        <EmptyState icon={<CardIcon size={24} />} title="No payments yet">
          A payment is recorded automatically each time a customer books.
        </EmptyState>
      )
    }
    const bookings = indexById(bookingList)
    const users = indexById(userList)
    const rows = payments
      .filter((p) => filter === "all" || p.status === filter)
      .sort((a, b) => b.id - a.id)

    if (rows.length === 0) {
      return (
        <EmptyState icon={<CardIcon size={24} />} title={`No ${filter} payments`}>
          Switch the filter above to see the rest.
        </EmptyState>
      )
    }

    return (
      <div className="table-wrap" aria-busy={req.loading}>
        <table className="table table-stack">
          <caption className="visually-hidden">All payments, newest first</caption>
          <thead>
            <tr>
              <th scope="col">ID</th>
              <th scope="col">Customer</th>
              <th scope="col">Booking</th>
              <th scope="col">Paid on</th>
              <th scope="col">Status</th>
              <th scope="col" className="align-right">
                Amount
              </th>
              <th scope="col" className="cell-actions">
                <span className="visually-hidden">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => {
              const booking = bookings.get(p.booking_id)
              const user = booking && users.get(booking.user_id)
              return (
                <tr key={p.id}>
                  <td data-label="ID" className="num">
                    {p.id}
                  </td>
                  <td data-label="Customer">
                    <div>
                      {user?.name ?? "Unknown"}
                      {user && <span className="cell-sub">{user.email}</span>}
                    </div>
                  </td>
                  <td data-label="Booking" className="num">
                    <div>
                      #{p.booking_id}
                      {booking && (
                        <span className="cell-sub">{pluralize(booking.seats_booked, "seat")}</span>
                      )}
                    </div>
                  </td>
                  <td data-label="Paid on">{p.paid_at ? formatDateTime(p.paid_at) : "Not paid"}</td>
                  <td data-label="Status">
                    <StatusBadge status={p.status} />
                  </td>
                  <td data-label="Amount" className="align-right num">
                    {formatMoney(p.amount)}
                  </td>
                  <td className="cell-actions">
                    {p.status === "completed" && (
                      <button
                        type="button"
                        className="btn btn-danger-outline"
                        onClick={() => setTarget({ payment: p, user, seats: booking?.seats_booked })}
                        aria-label={`Refund payment ${p.id}`}
                      >
                        Refund
                      </button>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    )
  }

  const filters: Filter[] = ["all", "completed", "refunded", "pending", "failed"]

  return (
    <div className="stack">
      <div className="toolbar">
        <div>
          <h1 className="admin-title">Payments</h1>
          <p className="muted">Refunding a payment also cancels its booking and frees the seats.</p>
        </div>
      </div>
      <div className="segmented" role="group" aria-label="Filter by status">
        {filters.map((f) => (
          <button key={f} type="button" aria-pressed={filter === f} onClick={() => setFilter(f)}>
            {f === "all" ? "All" : f === "completed" ? "Paid" : f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>
      {notice && <Alert tone="success">{notice}</Alert>}
      {body()}

      <ConfirmDialog
        open={target !== null}
        onClose={() => setTarget(null)}
        title={`Refund ${target ? formatMoney(target.payment.amount) : ""}?`}
        confirmLabel="Refund payment"
        pendingLabel="Refunding…"
        cancelLabel="Don't refund"
        onConfirm={async () => {
          if (!target) return
          const updated = await api.refundPayment(target.payment.id)
          setNotice(
            `Refunded ${formatMoney(updated.amount)} on payment #${updated.id}. Booking #${updated.booking_id} is now cancelled.`,
          )
          req.reload()
        }}
      >
        {target && (
          <p>
            Payment #{target.payment.id}
            {target.user ? ` from ${target.user.name}` : ""} will be marked refunded. Booking #
            {target.payment.booking_id} will be cancelled
            {target.seats ? ` and its ${pluralize(target.seats, "seat")} released` : ""}. This can't be
            undone.
          </p>
        )}
      </ConfirmDialog>
    </div>
  )
}
