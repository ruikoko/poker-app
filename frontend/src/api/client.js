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
  screenshot: (id)      => req('GET',    `/hands/${id}/screenshot`),
  stats:  ()            => req('GET',    '/hands/stats'),
  ssMatchPending: ()    => req('GET',    '/hands/ss-match-pending'),
  ssWithoutMatch: ()    => req('GET',    '/hands/ss-without-match'),
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
  listCategorized: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ''))
    ).toString()
    return req('GET', `/villains/categorized${qs ? '?' + qs : ''}`)
  },
  get:    (id)          => req('GET',    `/villains/${id}`),
  create: (body)        => req('POST',   '/villains', body),
  update: (id, body)    => req('PATCH',  `/villains/${id}`, body),
  delete: (id)          => req('DELETE', `/villains/${id}`),
  recalculate: ()       => req('POST',  '/villains/recalculate-hands'),
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

// ── Images (galeria manual — Tech Debt #B9) ──────────────────────────────────
export const images = {
  gallery:  (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ''))
    ).toString()
    return req('GET', `/images/gallery${qs ? '?' + qs : ''}`)
  },
  channels: () => req('GET', '/images/channels'),
  attach:   (handDbId, entryId) => req('POST', `/hands/${handDbId}/images`, { entry_id: entryId }),
  detach:   (handDbId, haId)    => req('DELETE', `/hands/${handDbId}/images/${haId}`),
  // URL absoluto para <img src> — endpoint público (Tech Debt #B9 thumbnails fix).
  // Em dev usa path relativo (Vite proxy); em prod usa VITE_API_URL.
  rawUrl:   (entryId) => `${BASE}/images/${entryId}/raw`,
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
  sync:           ()  => req('POST', '/discord/sync'),
  syncAndProcess: (body)  => req('POST', '/discord/sync-and-process', body),
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
  dates: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ''))
    ).toString()
    return req('GET', `/mtt/dates${qs ? '?' + qs : ''}`)
  },
  hand: (id) => req('GET', `/mtt/hands/${id}`),
  stats: () => req('GET', '/mtt/stats'),
  orphans: () => req('GET', '/mtt/orphan-screenshots'),
  rematch: () => req('POST', '/mtt/rematch'),
  reEnrich: () => req('POST', '/mtt/re-enrich'),
  resetMatches: () => req('POST', '/mtt/reset-matches'),
  cleanup: () => req('POST', '/mtt/cleanup'),
  deleteHand: (id) => req('DELETE', `/mtt/hands/${id}`),
  deleteScreenshot: (entryId) => req('DELETE', `/mtt/screenshot/${entryId}`),
  migrate: () => req('POST', '/mtt/migrate-to-hands'),
}

// ── HM3 Import ───────────────────────────────────────────────────────────────
export const hm3 = {
  import: (file, { daysBack, notaOnly } = {}) => {
    const form = new FormData()
    form.append('file', file)
    let qs = ''
    const params = []
    if (daysBack) params.push(`days_back=${daysBack}`)
    if (notaOnly) params.push('nota_only=true')
    if (params.length) qs = '?' + params.join('&')
    return fetch(`${BASE}/hm3/import${qs}`, { method: 'POST', credentials: 'include', body: form })
      .then(r => r.json())
  },
  stats: () => req('GET', '/hm3/stats'),
  reParse: () => req('POST', '/hm3/re-parse'),
  notaHands: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ''))
    ).toString()
    return req('GET', `/hm3/nota-hands${qs ? '?' + qs : ''}`)
  },
  notaStats: () => req('GET', '/hm3/nota-stats'),
}

// ── Stats ────────────────────────────────────────────────────────────────────
export const stats = {
  dashboard: (month) => req('GET', `/stats/dashboard${month ? '?month=' + month : ''}`),
  monthly:   (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ''))
    ).toString()
    return req('GET', `/stats/monthly${qs ? '?' + qs : ''}`)
  },
  save:      (entries) => req('POST', '/stats/save', { entries }),
  ideals:    (format) => req('GET', `/stats/ideals${format ? '?format=' + format : ''}`),
  saveIdeal: (body) => req('POST', '/stats/ideals', body),
  initDefaults: () => req('POST', '/stats/ideals/init-defaults'),
  initSchema:   () => req('POST', '/stats/init-schema'),
}

// ── Equity Calculator ────────────────────────────────────────────────────────
export const equity = {
  calculate: (heroCards, board, villainRange = 'random', numSims = 10000) =>
    req('POST', '/equity/calculate', { hero_cards: heroCards, board, villain_range: villainRange, num_simulations: numSims }),
  potAnalysis: (potSize, betSize, heroCards = [], board = [], villainRange = 'random') =>
    req('POST', '/equity/pot-analysis', { pot_size: potSize, bet_size: betSize, hero_cards: heroCards, board, villain_range: villainRange }),
  handAnalysis: (handId) => req('POST', `/equity/hand-analysis/${handId}`),
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
  bulkRematch: () => req('POST', `/mtt/rematch`),
  imageUrl: (entryId) => `${BASE}/screenshots/image/${entryId}`,
  dismiss: (entryId) => req('PATCH', `/entries/${entryId}`, { status: 'resolved' }),
  deleteEntry: (entryId) => req('DELETE', `/entries/${entryId}`),
  bulkDelete: (entryIds) => req('POST', '/entries/bulk-delete', { entry_ids: entryIds }),
}

// ── Study Sessions ──────────────────────────────────────────────────────────
export const study = {
  start: (handId = null) => req('POST', '/study/start', { hand_id: handId }),
  stop:  (sessionId)     => req('POST', '/study/stop',  { session_id: sessionId }),
  week:  ()              => req('GET',  '/study/week'),
}

// ── GTO Brain ──────────────────────────────────────────────────────────────
export const gto = {
  match: (params) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ''))
    ).toString()
    return req('GET', `/gto/match?${qs}`)
  },
  getNode: (treeId, nodeIndex) => req('GET', `/gto/trees/${treeId}/node/${nodeIndex}`),
  getNodes: (treeId, indices) => req('GET', `/gto/trees/${treeId}/nodes?indices=${indices.join(',')}`),
  navigate: (data) => req('POST', '/gto/navigate', data),
  trees: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ''))
    ).toString()
    return req('GET', `/gto/trees?${qs}`)
  },
}
