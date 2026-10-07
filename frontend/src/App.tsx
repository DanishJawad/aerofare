import { useEffect } from "react"
import { Navigate, Route, Routes, useLocation } from "react-router-dom"
import { RequireAdmin, RequireAuth } from "./auth/guards"
import { AdminLayout } from "./components/AdminLayout"
import { SiteLayout } from "./components/SiteLayout"
import { BookingsPage } from "./pages/BookingsPage"
import { FlightDetailPage } from "./pages/FlightDetailPage"
import { FlightsPage } from "./pages/FlightsPage"
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage"
import { LoginPage } from "./pages/LoginPage"
import { NotFoundPage } from "./pages/NotFoundPage"
import { PaymentsPage } from "./pages/PaymentsPage"
import { ProfilePage } from "./pages/ProfilePage"
import { ResetPasswordPage } from "./pages/ResetPasswordPage"
import { SignupPage } from "./pages/SignupPage"
import { AdminAirportsPage } from "./pages/admin/AdminAirportsPage"
import { AdminBookingsPage } from "./pages/admin/AdminBookingsPage"
import { AdminFlightsPage } from "./pages/admin/AdminFlightsPage"
import { AdminPaymentsPage } from "./pages/admin/AdminPaymentsPage"

const TITLES: [RegExp, string][] = [
  [/^\/$/, "Find a flight"],
  [/^\/flights\/\d+/, "Flight details"],
  [/^\/login/, "Log in"],
  [/^\/signup/, "Create an account"],
  [/^\/forgot-password/, "Forgot password"],
  [/^\/reset-password/, "Reset password"],
  [/^\/bookings/, "My trips"],
  [/^\/payments/, "Payments"],
  [/^\/profile/, "Profile"],
  [/^\/admin\/airports/, "Airports · Admin"],
  [/^\/admin\/flights/, "Flights · Admin"],
  [/^\/admin\/bookings/, "Bookings · Admin"],
  [/^\/admin\/payments/, "Payments · Admin"],
]

/** Page titles per route, and scroll to top on navigation like a normal site. */
function useRouteEffects() {
  const { pathname } = useLocation()
  useEffect(() => {
    const title = TITLES.find(([re]) => re.test(pathname))?.[1]
    document.title = title ? `${title} · Aerofare` : "Aerofare"
    window.scrollTo(0, 0)
  }, [pathname])
}

export default function App() {
  useRouteEffects()

  return (
    <Routes>
      <Route element={<SiteLayout />}>
        <Route index element={<FlightsPage />} />
        <Route path="flights/:id" element={<FlightDetailPage />} />
        <Route path="login" element={<LoginPage />} />
        <Route path="signup" element={<SignupPage />} />
        <Route path="forgot-password" element={<ForgotPasswordPage />} />
        <Route path="reset-password" element={<ResetPasswordPage />} />
        <Route
          path="bookings"
          element={
            <RequireAuth>
              <BookingsPage />
            </RequireAuth>
          }
        />
        <Route
          path="payments"
          element={
            <RequireAuth>
              <PaymentsPage />
            </RequireAuth>
          }
        />
        <Route
          path="profile"
          element={
            <RequireAuth>
              <ProfilePage />
            </RequireAuth>
          }
        />
        <Route path="*" element={<NotFoundPage />} />
      </Route>

      <Route
        path="admin"
        element={
          <RequireAdmin>
            <AdminLayout />
          </RequireAdmin>
        }
      >
        <Route index element={<Navigate to="flights" replace />} />
        <Route path="flights" element={<AdminFlightsPage />} />
        <Route path="airports" element={<AdminAirportsPage />} />
        <Route path="bookings" element={<AdminBookingsPage />} />
        <Route path="payments" element={<AdminPaymentsPage />} />
      </Route>
    </Routes>
  )
}
