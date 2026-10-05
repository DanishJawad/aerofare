import { useCallback, useEffect, useState, type DependencyList } from "react"
import { ApiError } from "../api"

interface Settled<T> {
  key: string
  data?: T
  error?: ApiError
}

export interface AsyncResult<T> {
  /** Latest successful data. Kept while a refetch is in flight so the page doesn't jump. */
  data: T | undefined
  error: ApiError | undefined
  /** True while the request for the current deps hasn't settled yet. */
  loading: boolean
  reload: () => void
}

function toApiError(err: unknown): ApiError {
  return err instanceof ApiError ? err : new ApiError(0, "Something unexpected went wrong.")
}

/**
 * Run `fn` whenever `deps` change (or `reload()` is called) and track the
 * loading / error / data states every data screen needs.
 *
 * Loading is derived by comparing the key of the last settled request with the
 * current one, instead of calling setState({loading: true}) inside the effect.
 */
export function useAsync<T>(fn: () => Promise<T>, deps: DependencyList): AsyncResult<T> {
  const [version, setVersion] = useState(0)
  const [settled, setSettled] = useState<Settled<T> | null>(null)
  const key = `${JSON.stringify(deps)}#${version}`

  useEffect(() => {
    let active = true
    fn().then(
      (data) => {
        if (active) setSettled({ key, data })
      },
      (err: unknown) => {
        if (active) setSettled((prev) => ({ key, data: prev?.data, error: toApiError(err) }))
      },
    )
    return () => {
      active = false
    }
    // `key` already encodes `deps`; `fn` is a fresh closure every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  const reload = useCallback(() => setVersion((v) => v + 1), [])
  const current = settled?.key === key

  return {
    data: settled?.data,
    error: current ? settled?.error : undefined,
    loading: !current,
    reload,
  }
}
