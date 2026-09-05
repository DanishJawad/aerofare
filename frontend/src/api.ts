const BASE_URL = import.meta.env.VITE_API_URL

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`)

  if (!res.ok) {
    throw new Error(`Request failed (${res.status})`)
  }

  return res.json() as Promise<T>
}