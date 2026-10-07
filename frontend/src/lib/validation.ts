export type ProfileField = "name" | "email" | "phone_number" | "city" | "country"

// Mirrors the backend's pydantic rules so most mistakes are caught before a round trip.
export function validateEmail(email: string): string | undefined {
  if (!email.trim()) return "Enter your email."
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) return "Enter an email like name@example.com."
  return undefined
}

export function validateProfile(
  v: Record<ProfileField, string>,
): Partial<Record<ProfileField, string>> {
  const errors: Partial<Record<ProfileField, string>> = {}
  if (!v.name.trim()) errors.name = "Enter your name."
  const emailError = validateEmail(v.email)
  if (emailError) errors.email = emailError
  if (!v.city.trim()) errors.city = "Enter your city."
  if (!v.country.trim()) errors.country = "Enter your country."
  return errors
}

export function validateNewPassword(pw: string): string | undefined {
  if (pw.length < 8) return "Use at least 8 characters."
  if (pw.length > 72) return "Use 72 characters or fewer."
  return undefined
}
