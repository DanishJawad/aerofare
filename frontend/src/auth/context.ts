import { createContext, useContext } from "react"
import type { User } from "../types"

export interface AuthState {
  /** "loading" only while a stored token is being checked against /users/me on page load. */
  status: "loading" | "ready"
  user: User | null
  login: (email: string, password: string) => Promise<User>
  logout: () => Promise<void>
  /** Replace the cached user after a profile edit. */
  setUser: (user: User) => void
}

export const AuthContext = createContext<AuthState | null>(null)

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>")
  return ctx
}
