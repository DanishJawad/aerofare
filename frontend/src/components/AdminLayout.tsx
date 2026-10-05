import { Link, NavLink, Outlet } from "react-router-dom"
import { ArrowLeftIcon, CardIcon, PinIcon, PlaneIcon, TicketIcon } from "./Icons"
import { Brand } from "./SiteLayout"

const SECTIONS = [
  { to: "/admin/flights", label: "Flights", icon: <PlaneIcon /> },
  { to: "/admin/airports", label: "Airports", icon: <PinIcon /> },
  { to: "/admin/bookings", label: "Bookings", icon: <TicketIcon /> },
  { to: "/admin/payments", label: "Payments", icon: <CardIcon /> },
]

/**
 * Dark top bar + side nav: visibly a different tool from the consumer site,
 * so an admin always knows which side they're acting on.
 */
export function AdminLayout() {
  return (
    <div className="admin-shell">
      <a href="#admin-main" className="skip-link">
        Skip to content
      </a>
      <header className="admin-topbar">
        <div className="container">
          <div className="admin-topbar-inner">
            <Brand to="/admin" />
            <span className="admin-tag">Admin</span>
            <Link to="/" className="topbar-link">
              <ArrowLeftIcon />
              Back to site
            </Link>
          </div>
        </div>
      </header>
      <div className="container admin-body">
        <nav className="admin-nav" aria-label="Admin sections">
          {SECTIONS.map((s) => (
            <NavLink key={s.to} to={s.to} className="nav-link">
              {s.icon}
              {s.label}
            </NavLink>
          ))}
        </nav>
        <main className="admin-main" id="admin-main">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
