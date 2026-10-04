import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api } from '../api/client'

export const keys = {
  health: ['health'],
  sessions: ['sessions'],
  session: (id) => ['session', id],
  context: (id, memory) => ['context', id, memory],
}

export const useHealth = () => useQuery({ queryKey: keys.health, queryFn: api.health, staleTime: 60_000 })

export const useSessions = () => useQuery({ queryKey: keys.sessions, queryFn: api.sessions })

export const useSession = (id) =>
  useQuery({ queryKey: keys.session(id), queryFn: () => api.session(id), enabled: !!id })

/** What the detective would see under `memory`. Keeps the previous result while a slider moves. */
export const useContextPreview = (id, memory) =>
  useQuery({
    queryKey: keys.context(id, memory),
    queryFn: () => api.context(id, memory),
    enabled: !!id && !!memory,
    placeholderData: keepPreviousData,
  })

export function useOpenCase({ demo = false, onOpened } = {}) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: demo ? api.seedDemo : api.createSession,
    onSuccess: (session) => {
      qc.invalidateQueries({ queryKey: keys.sessions })
      onOpened?.(session.session_id)
    },
  })
}

export function useAnswer(id) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (content) => api.answer(id, content),
    // Put the answer on the transcript immediately; the server's copy replaces it.
    onMutate: async (content) => {
      await qc.cancelQueries({ queryKey: keys.session(id) })
      const previous = qc.getQueryData(keys.session(id))
      qc.setQueryData(keys.session(id), (old) =>
        old && {
          ...old,
          messages: [...old.messages, { id: 'pending', role: 'user', content, pinned: false, pending: true }],
        },
      )
      return { previous }
    },
    onError: (_err, _content, ctx) => ctx?.previous && qc.setQueryData(keys.session(id), ctx.previous),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: keys.session(id) })
      qc.invalidateQueries({ queryKey: ['context', id] })
      qc.invalidateQueries({ queryKey: keys.sessions })
    },
  })
}

export function usePin(id) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ msgId, pinned }) => api.pin(id, msgId, pinned),
    onMutate: async ({ msgId, pinned }) => {
      await qc.cancelQueries({ queryKey: keys.session(id) })
      const previous = qc.getQueryData(keys.session(id))
      qc.setQueryData(keys.session(id), (old) =>
        old && { ...old, messages: old.messages.map((m) => (m.id === msgId ? { ...m, pinned } : m)) },
      )
      return { previous }
    },
    onError: (_e, _v, ctx) => ctx?.previous && qc.setQueryData(keys.session(id), ctx.previous),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: keys.session(id) })
      qc.invalidateQueries({ queryKey: ['context', id] })
    },
  })
}

export function useSaveMemory(id) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (memory) => api.setMemory(id, memory),
    onSuccess: (session) => {
      qc.setQueryData(keys.session(id), (old) => old && { ...old, session })
    },
  })
}

export function useDebounced(value, delay = 200) {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(t)
  }, [value, delay])
  return debounced
}
