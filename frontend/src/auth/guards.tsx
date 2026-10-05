import type { ReactNode } from "react"
import { Navigate, useLocation } from "react-router-dom"
import { PageSpinner } from "../components/Feedback"
import { useAuth } from "./context"
import { NotFoundPage } from "../pages/NotFoundPage"

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status, user } = useAuth()
  const location = useLocation()

  if (status === "loading") return <PageSpinner label="Checking your session" />
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  }
  return children
}

/** Non-admins get a plain 404 so the admin area isn't advertised. */
export function RequireAdmin({ children }: { children: ReactNode }) {
  const { status, user } = useAuth()
  const location = useLocation()

  if (status === "loading") return <PageSpinner label="Checking your session" />
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  }
  if (!user.is_admin) return <NotFoundPage />
  return children
}
