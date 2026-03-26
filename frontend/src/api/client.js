// Use relative path — in dev, Vite proxy forwards /api → backend.
// In production, the reverse proxy (nginx/railway) does the same.
const API_ROOT = import.meta.env.VITE_API_URL || ''

const BASE = `${API_ROOT}/api`

async function req(method, path, body) {
  const opts = {
    method,
    credentials: 'include',   // envia cookie HttpOnly automaticamente
    headers: body ? { 'Content-Type': 'application/json' } : {},
  }
  if (body) opts.body = JSON.stringify(body)

  const res = await fetch(BASE + path, opts)

  if (res.status === 401) {
    // Sessão expirada — redireciona para login sem loop
    if (!window.location.pathname.startsWith('/login')) {
      window.location.href = '/login'
    }
    throw new Error('Não autenticado')
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Erro ${res.status}`)
  }

  // 204 No Content
  if (res.status === 204) return null
  return res.json()
}

// ── Auth ─────────────────────────────────────────────────────────────────────
export const auth = {
  login:  (email, password) => req('POST', '/auth/login', { email, password }),
  logout: ()                => req('POST', '/auth/logout'),
  me:     ()                => req('GET',  '/auth/me'),
}

// ── Tournaments ───────────────────────────────────────────────────────────────
export const tournaments = {
  list: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ''))
    ).toString()
    return req('GET', `/tournaments${qs ? '?' + qs : ''}`)
  },
  summary: () => req('GET', '/tournaments/summary'),
  hands: (id, params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ''))
    ).toString()
    return req('GET', `/tournaments/${id}/hands${qs ? '?' + qs : ''}`)
  },
}

// ── Hands ────────────────────────────────────────────────────────────────────
export const hands = {
  list:   (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ''))
    ).toString()
    return req('GET', `/hands${qs ? '?' + qs : ''}`)
  },
  get:    (id)          => req('GET',    `/hands/${id}`),
  create: (body)        => req('POST',   '/hands', body),
  update: (id, body)    => req('PATCH',  `/hands/${id}`, body),
  delete: (id)          => req('DELETE', `/hands/${id}`),
  stats:  ()            => req('GET',    '/hands/stats'),
  tagGroups: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ''))
    ).toString()
    return req('GET', `/hands/tag-groups${qs ? '?' + qs : ''}`)
  },
}
// ── Villains ────────────────────────────────────────────────────────────────────
export const villains = {
  list:   (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ''))
    ).toString()
    return req('GET', `/villains${qs ? '?' + qs : ''}`)
  },
  get:    (id)          => req('GET',    `/villains/${id}`),
  create: (body)        => req('POST',   '/villains', body),
  update: (id, body)    => req('PATCH',  `/villains/${id}`, body),
  delete: (id)          => req('DELETE', `/villains/${id}`),
  searchHands: (nick, params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries({ nick, ...params }).filter(([, v]) => v != null && v !== ''))
    ).toString()
    return req('GET', `/villains/search/hands?${qs}`)
  },
}
// ── Entries ──────────────────────────────────────────────────────────────────
export const entries = {
  list: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ''))
    ).toString()
    return req('GET', `/entries${qs ? '?' + qs : ''}`)
  },
  get:       (id)          => req('GET',   `/entries/${id}`),
  update:    (id, body)    => req('PATCH', `/entries/${id}`, body),
  reprocess: (id)          => req('POST',  `/entries/${id}/reprocess`),
}

// ── Discord ──────────────────────────────────────────────────────────────────
export const discord = {
  status:    ()  => req('GET',  '/discord/status'),
  syncState: ()  => req('GET',  '/discord/sync-state'),
  stats:     (params = {})  => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ''))
    ).toString()
    return req('GET', `/discord/stats${qs ? '?' + qs : ''}`)
  },
  sync:      ()  => req('POST', '/discord/sync'),
}

// ── Import ────────────────────────────────────────────────────────────────────
export const imports = {
  upload: (file, site) => {
    const form = new FormData()
    form.append('file', file)
    const url = site ? `${BASE}/import?site=${site}` : `${BASE}/import`
    return fetch(url, { method: 'POST', credentials: 'include', body: form })
      .then(r => r.json())
  },
  logs: () => req('GET', '/import/logs'),
}

// ── MTT ──────────────────────────────────────────────────────────────────────
export const mtt = {
  import: (file) => {
    const form = new FormData()
    form.append('file', file)
    return fetch(`${BASE}/mtt/import`, { method: 'POST', credentials: 'include', body: form })
      .then(r => r.json())
  },
  hands: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ''))
    ).toString()
    return req('GET', `/mtt/hands${qs ? '?' + qs : ''}`)
  },
  hand: (id) => req('GET', `/mtt/hands/${id}`),
  stats: () => req('GET', '/mtt/stats'),
  orphans: () => req('GET', '/mtt/orphan-screenshots'),
  rematch: () => req('POST', '/mtt/rematch'),
}

// ── Screenshots ───────────────────────────────────────────────────────────────
export const screenshots = {
  upload: (file) => {
    const form = new FormData()
    form.append('file', file)
    return fetch(`${BASE}/screenshots`, { method: 'POST', credentials: 'include', body: form })
      .then(r => r.json())
  },
  getForHand: (handId) => req('GET', `/screenshots/hand/${handId}`),
  orphans: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries({ entry_type: 'screenshot', status: 'new', page_size: 100, ...params }).filter(([, v]) => v != null && v !== ''))
    ).toString()
    return req('GET', `/entries?${qs}`)
  },
  rematch: (entryId) => req('POST', `/screenshots/orphans/${entryId}/rematch`),
  dismiss: (entryId) => req('PATCH', `/entries/${entryId}`, { status: 'resolved' }),
}
