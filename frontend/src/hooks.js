import { useCallback, useEffect, useRef, useState } from 'react'

// Ignore out-of-order responses and updates after navigation/unmount.
export function useRemote(loader) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const sequence = useRef(0)
  const reload = useCallback(async () => {
    const current = ++sequence.current
    setLoading(true); setError(null)
    try { const value = await loader(); if (sequence.current === current) setData(value); return value }
    catch (issue) { if (sequence.current === current) setError(issue); return null }
    finally { if (sequence.current === current) setLoading(false) }
  }, [loader])
  useEffect(() => { reload(); return () => { sequence.current++ } }, [reload])
  return { data, loading, error, reload }
}
