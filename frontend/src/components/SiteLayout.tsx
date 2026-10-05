import { useState } from "react"
import { Link, NavLink, Outlet, useLocation } from "react-router-dom"
import { useAuth } from "../auth/context"
import { CloseIcon, MenuIcon, PlaneIcon } from "./Icons"

export function Brand({ to = "/" }: { to?: string }) {
  return (
    <Link to={to} className="brand">
      <span className="brand-mark">
        <PlaneIcon size={18} />
      </span>
      aerofare
    </Link>
  )
}

function NavItems() {
  const { user } = useAuth()
  return (
    <>
      <NavLink to="/" end className="nav-link">
        Flights
      </NavLink>
      {user && (
        <>
          <NavLink to="/bookings" className="nav-link">
            My trips
          </NavLink>
          <NavLink to="/payments" className="nav-link">
            Payments
          </NavLink>
        </>
      )}
    </>
  )
}

function AccountItems() {
  const { user, status } = useAuth()
  if (status === "loading") return null
  if (!user) {
    return (
      <>
        <Link to="/login" className="btn btn-ghost">
          Log in
        </Link>
        <Link to="/signup" className="btn btn-secondary">
          Sign up
        </Link>
      </>
    )
  }
  return (
    <>
      {user.is_admin && (
        <Link to="/admin" className="admin-pill">
          Admin
        </Link>
      )}
      <NavLink to="/profile" className="nav-link">
        Profile
      </NavLink>
    </>
  )
}

export function SiteLayout() {
  const location = useLocation()
  // Keyed on the path so the mobile menu closes itself after navigating.
  const [openFor, setOpenFor] = useState<string | null>(null)
  const open = openFor === location.pathname

  return (
    <>
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <header className="site-header" data-open={open}>
        <div className="container">
          <div className="site-header-inner">
            <Brand />
            <nav className="site-nav" aria-label="Main">
              <NavItems />
            </nav>
            <div className="header-actions">
              <AccountItems />
            </div>
            <button
              type="button"
              className="btn btn-ghost menu-button"
              aria-expanded={open}
              aria-controls="mobile-menu"
              onClick={() => setOpenFor(open ? null : location.pathname)}
            >
              {open ? <CloseIcon size={20} /> : <MenuIcon size={20} />}
              Menu
            </button>
          </div>
          <nav id="mobile-menu" className="mobile-panel" aria-label="Main">
            <NavItems />
            <AccountItems />
          </nav>
        </div>
      </header>
      <main id="main">
        <Outlet />
      </main>
      <footer className="site-footer">
        <div className="container">
          Aerofare. Times are shown in your local time zone. Prices in USD.
        </div>
      </footer>
    </>
  )
}
