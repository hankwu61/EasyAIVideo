import { useCallback, useEffect, useRef, useState } from 'react'
import type { Project } from '../../types'

export interface Keyed {
  /** Stable local key (React key). Survives server round-trips even when ids are assigned later. */
  key: string
  /** Server id, when the entity has one. */
  id?: string
}

interface Options<T extends Keyed> {
  project: Project
  /** Derive the list from a project. Keys should default to the server id (or the index). */
  fromProject: (p: Project) => T[]
  /** Send the full list; resolves with the refreshed project. */
  save: (items: T[]) => Promise<Project>
  onProject: (p: Project) => void
  onError: (e: unknown) => void
  onSaved?: () => void
  debounceMs?: number
}

/**
 * Local editable copy of a list that is saved as a whole (debounced) and only re-synced from the
 * server while no local edit is pending, so polling never clobbers what the user is typing.
 */
export function useSyncedList<T extends Keyed>(opts: Options<T>) {
  const optsRef = useRef(opts)
  optsRef.current = opts
  const debounce = opts.debounceMs ?? 600

  // server id -> local key, so a card keeps its key once the server assigns an id.
  const keyMap = useRef(new Map<string, string>())
  const withStableKeys = useCallback((list: T[]): T[] => {
    return list.map((it) => {
      const k = it.id ? keyMap.current.get(it.id) : undefined
      return k && k !== it.key ? { ...it, key: k } : it
    })
  }, [])

  const [items, setItems] = useState<T[]>(() => withStableKeys(opts.fromProject(opts.project)))
  const latest = useRef(items)
  latest.current = items
  const dirty = useRef(false)
  const inflight = useRef(false)
  const timer = useRef<number | null>(null)

  // Sync from server only when nothing is pending locally.
  useEffect(() => {
    if (!dirty.current && !inflight.current) setItems(withStableKeys(optsRef.current.fromProject(opts.project)))
  }, [opts.project, withStableKeys])

  const flush = useCallback(async () => {
    if (timer.current !== null) {
      window.clearTimeout(timer.current)
      timer.current = null
    }
    if (!dirty.current || inflight.current) return
    dirty.current = false
    inflight.current = true
    const snapshot = latest.current
    try {
      const updated = await optsRef.current.save(snapshot)
      const serverList = optsRef.current.fromProject(updated)
      if (serverList.length === snapshot.length) {
        serverList.forEach((it, i) => {
          if (it.id) keyMap.current.set(it.id, snapshot[i].key)
        })
      }
      inflight.current = false
      if (!dirty.current) setItems(withStableKeys(serverList))
      optsRef.current.onProject(updated)
      optsRef.current.onSaved?.()
    } catch (e) {
      inflight.current = false
      dirty.current = true // keep local edits; the next change retries
      optsRef.current.onError(e)
    }
  }, [withStableKeys])

  const update = useCallback(
    (fn: (prev: T[]) => T[]) => {
      setItems((prev) => {
        const next = fn(prev)
        latest.current = next
        return next
      })
      dirty.current = true
      if (timer.current !== null) window.clearTimeout(timer.current)
      timer.current = window.setTimeout(() => void flush(), debounce)
    },
    [flush, debounce],
  )

  // Flush pending edits when leaving the page.
  useEffect(
    () => () => {
      if (timer.current !== null) window.clearTimeout(timer.current)
      if (dirty.current && !inflight.current) {
        dirty.current = false
        void optsRef.current.save(latest.current).catch(() => undefined)
      }
    },
    [],
  )

  return { items, update, flush }
}
