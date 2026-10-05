import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react"
import { useNavigate } from "react-router-dom"
import { api, clearToken, getToken, setToken, setUnauthorizedHandler } from "../api"
import type { User } from "../types"
import { AuthContext, type AuthState } from "./context"

export function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const [user, setUser] = useState<User | null>(null)
  const [status, setStatus] = useState<AuthState["status"]>(() =>
    getToken() ? "loading" : "ready",
  )

  // Restore the session from a stored token. /users/me is the source of truth
  // for is_admin; the JWT only carries the user id.
  useEffect(() => {
    if (!getToken()) return
    api
      .restoreSession()
      .then(setUser)
      .catch(() => {
        clearToken()
        setUser(null)
      })
      .finally(() => setStatus("ready"))
  }, [])

  // Any 401 on an authenticated call lands here after the token is cleared.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null)
      const from = window.location.pathname + window.location.search
      navigate("/login", { replace: true, state: { from, reason: "expired" } })
    })
    return () => setUnauthorizedHandler(null)
  }, [navigate])

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await api.login(email, password)
    setToken(access_token)
    const me = await api.me()
    setUser(me)
    return me
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.logout() // revokes the token server-side
    } catch {
      // Already expired or server unreachable: clearing locally is still correct.
    }
    // Navigate first: if user went null while still on a protected page,
    // RequireAuth would bounce to /login instead.
    navigate("/", { replace: true })
    clearToken()
    setUser(null)
  }, [navigate])

  const value = useMemo<AuthState>(
    () => ({ status, user, login, logout, setUser }),
    [status, user, login, logout],
  )

  return <AuthContext value={value}>{children}</AuthContext>
}
