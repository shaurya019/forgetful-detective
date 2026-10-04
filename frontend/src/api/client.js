const BASE = import.meta.env.VITE_API_URL ?? '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  })
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const data = await res.json()
      detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    } catch {
      /* body wasn't JSON */
    }
    throw new Error(detail)
  }
  return res.json()
}

export const api = {
  health: () => request('/health'),
  sessions: () => request('/sessions'),
  createSession: () => request('/sessions', { method: 'POST' }),
  seedDemo: () => request('/demo/seed', { method: 'POST' }),
  session: (id) => request(`/sessions/${id}`),
  answer: (id, content) => request(`/sessions/${id}/messages`, { method: 'POST', body: { content } }),
  pin: (id, msgId, pinned) => request(`/sessions/${id}/messages/${msgId}`, { method: 'PATCH', body: { pinned } }),
  setMemory: (id, memory) => request(`/sessions/${id}/memory`, { method: 'PUT', body: memory }),
  context: (id, memory) => {
    const q = new URLSearchParams({
      strategy: memory.strategy,
      budget_tokens: String(memory.budget_tokens),
      last_n: String(memory.last_n),
    })
    return request(`/sessions/${id}/context?${q}`)
  },
}
