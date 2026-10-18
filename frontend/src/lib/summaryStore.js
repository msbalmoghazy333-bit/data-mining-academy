/**
 * Tiny shared store for the dashboard summary.
 *
 * The header progress pill and the dashboard both need the same data, so a
 * module-level cache with subscriber set is enough — no prop drilling and no
 * external state library. Pages call `refreshSummary()` after uploads /
 * publishes / deletes to keep the pill fresh.
 */

import { useEffect, useState } from 'react'

import api from './api.js'

let snapshot = { status: 'idle', loading: false, data: null, error: null }
let inflight = false
const listeners = new Set()

function emit() {
  for (const listener of listeners) listener()
}

async function fetchSummary() {
  if (inflight) return
  inflight = true
  snapshot = { ...snapshot, loading: true, error: null }
  emit()

  try {
    const data = await api.get('/v1/dashboard/summary')
    snapshot = { status: 'ready', loading: false, data, error: null }
  } catch (error) {
    snapshot = { status: 'error', loading: false, data: null, error }
  }

  inflight = false
  emit()
}

/** Force a fresh fetch (e.g. after an upload or publish). */
export function refreshSummary() {
  return fetchSummary()
}

/** Subscribe the component to the shared summary snapshot. */
export function useSummary() {
  const [, tick] = useState(0)

  useEffect(() => {
    const listener = () => tick((value) => value + 1)
    listeners.add(listener)
    if (snapshot.status === 'idle' && !inflight) fetchSummary()
    return () => {
      listeners.delete(listener)
    }
  }, [])

  return snapshot
}
