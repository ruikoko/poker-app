// Use relative path — in dev, Vite proxy forwards /api → backend.
// In production, the reverse proxy (nginx/railway) does the same.
export const API_ROOT = import.meta.env.VITE_API_URL || ''

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
  meta: (tms) => req('GET', `/tournaments/meta${tms && tms.length ? '?tms=' + tms.join(',') : ''}`),
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
  // Recompute N/M/K do último sync contra o estado actual da BD (números
  // assentes após Vision/match em background). `since` = last_sync.started_at.
  syncCounters:   (since)  => req('GET', `/discord/sync-counters?since=${encodeURIComponent(since)}`),
  // Botão "Sincronizar histórico" (orquestração no frontend): processa
  // replayer-links GG em VAGAS curtas (max_iters=1) e lê o progresso via
  // preview; backfill cria os placeholders GGDiscord no fim.
  processReplayerLinks:        (limit = 30)  => req('POST', `/discord/process-replayer-links?confirm=true&limit=${limit}&max_iters=1`),
  processReplayerLinksPreview: ()  => req('GET',  '/discord/process-replayer-links/preview'),
  backfillGgdiscord:           ()  => req('POST', '/discord/backfill-ggdiscord?confirm=true'),
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

// ── Lobbys (sync-recent + upload manual) ──────────────────────────────────
export const lobbys = {
  syncRecent: (body = {}) => req('POST', '/lobbys/sync-recent', body),
  // Upload de 1 SS de lobby → gate "é lobby?" no backend (não-lobby ignorado).
  // captured_at = hora local (Lisboa naive) do File.lastModified — ver Lobbys.jsx.
  upload: (file, opts = {}) => {
    const form = new FormData()
    form.append('file', file)
    if (opts.captured_at) form.append('captured_at', opts.captured_at)
    return fetch(`${BASE}/lobbys/upload`, {
      method: 'POST',
      credentials: 'include',
      body: form,
    }).then(async (r) => {
      const data = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(data.detail || `Erro ${r.status}`)
      return data
    })
  },
  // Re-resolve lobbys pendentes (tm_not_found/tm_ambiguous) contra o estado
  // actual da BD. dry_run=true → preview por torneio sem escrever.
  reconcile: (dryRun = false) =>
    req('POST', `/lobbys/reconcile?dry_run=${dryRun ? 'true' : 'false'}`),
}

// ── Tournament Results (backoffice GG SS) ────────────────────────────────
export const tournamentResults = {
  upload: (file, opts = {}) => {
    const form = new FormData()
    form.append('file', file)
    if (opts.dry_run) form.append('dry_run', 'true')
    if (opts.skip_existing) form.append('skip_existing', 'true')
    if (opts.vision_throttle_seconds != null) {
      form.append('vision_throttle_seconds', opts.vision_throttle_seconds)
    }
    return fetch(`${BASE}/tournament-results/import`, {
      method: 'POST',
      credentials: 'include',
      body: form,
    }).then(r => r.json())
  },
}

// ── Tournament Summaries (GG TS files) ────────────────────────────────────
export const tournamentSummaries = {
  upload: (file) => {
    const form = new FormData()
    form.append('file', file)
    return fetch(`${BASE}/tournament-summaries/import`, {
      method: 'POST',
      credentials: 'include',
      body: form,
    }).then(r => r.json())
  },
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

// ── Marcadas por captura (triagem de SS de mesa desanonimizadas) ────────────
export const captureTriage = {
  list:  ()              => req('GET',  '/capture-triage'),
  count: ()              => req('GET',  '/capture-triage/count'),
  tag:   (handId, tag)   => req('POST', `/capture-triage/${handId}/tag`, { tag }),
  imageUrl: (id)         => `${BASE}/table-ss/image/${id}`,
}

// ── Mãos suspeitas (guardião de validação, read-only) ───────────────────────
export const suspicious = {
  list:  () => req('GET', '/suspicious-hands'),
  count: () => req('GET', '/suspicious-hands/count'),
}

// ── HRC Sessions (Complete Export import) ───────────────────────────────────
export const hrc = {
  upload: (file, opts = {}) => {
    const form = new FormData()
    form.append('file', file)
    if (opts.name) form.append('name', opts.name)
    if (opts.source) form.append('source', opts.source)
    if (opts.related_hand_id != null) form.append('related_hand_id', opts.related_hand_id)
    return fetch(`${BASE}/hrc/import`, {
      method: 'POST',
      credentials: 'include',
      body: form,
    }).then(async (r) => {
      const data = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(data.detail || `Erro ${r.status}`)
      return data
    })
  },
  sessions: () => req('GET', '/hrc/sessions'),
  session:  (id) => req('GET', `/hrc/sessions/${id}`),
  node:     (id, idx) => req('GET', `/hrc/sessions/${id}/nodes/${idx}`),
  delete:   (id) => req('DELETE', `/hrc/sessions/${id}`),
  eligible: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ''))
    ).toString()
    return req('GET', `/hrc/eligible${qs ? `?${qs}` : ''}`)
  },
  // pt41 — mãos bounty-format escondidas do /hrc por falta de TS (banner D1).
  pendingTs: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ''))
    ).toString()
    return req('GET', `/hrc/pending-ts${qs ? `?${qs}` : ''}`)
  },
}

// ── HRC Queue (export p/ watcher + download per-mão) ────────────────────────
export const queue = {
  // Download do pack HRC de UMA mão (zip: hh.txt + payouts.json + meta/manifest).
  // Raw fetch (blob) + trigger de download no browser. Lança Error com o detail
  // do backend em 404 (mão inexistente) / 409 (sem payout) / 422 (não exportável).
  hrcHandDownload: async (handId) => {
    const res = await fetch(`${BASE}/queue/hrc/hand/${encodeURIComponent(handId)}`, {
      method: 'GET',
      credentials: 'include',
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || `Erro ${res.status}`)
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `hrc_${handId}.zip`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  },
  // Contadores da fila HRC (pt92 — fila 100% manual, sem disparo em lote)
  gate: () => req('GET', '/queue/hrc/gate'),
  // pt92 — limpa/pausa a fila (des-liberta tudo; o adapter para de puxar)
  clearReleased: () => req('POST', '/queue/hrc/clear-released'),
}

// ── SS de mesa (contexto players_left p/ HRC) ───────────────────────────────
export const tableSs = {
  upload: (file, opts = {}) => {
    const form = new FormData()
    form.append('file', file)
    if (opts.filename) form.append('filename', opts.filename)
    if (opts.captured_at) form.append('captured_at', opts.captured_at)
    if (opts.source) form.append('source', opts.source)
    return fetch(`${BASE}/table-ss/upload`, {
      method: 'POST',
      credentials: 'include',
      body: form,
    }).then(async (r) => {
      const data = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(data.detail || `Erro ${r.status}`)
      return data
    })
  },
  recent: (limit = 50) => req('GET', `/table-ss/recent?limit=${limit}`),
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

// ── Saúde do Import (pt68) ──────────────────────────────────────────────────
export const importHealth = {
  get: (day) => req('GET', `/import-health${day ? `?day=${day}` : ''}`),
}

// ── Multi-select "Enviar ao HRC" (pt68) — reusa o gate ──────────────────────
Object.assign(queue, {
  release: (handIds) => req('POST', '/queue/hrc/release', { hand_ids: handIds }),
  states:  (handIds) => req('POST', '/queue/hrc/states',  { hand_ids: handIds }),
  // pt83 — lista das Enviadas + re-pôr na fila as falhadas
  sent:    () => req('GET', '/queue/hrc/sent'),
  requeue: (handIds) => req('POST', '/queue/hrc/requeue', { hand_ids: handIds }),
  // pt85 (#HRC-VERIFY) — verificação C1-C5 HH-vs-HRC das resolvidas.
  // batch alimenta o badge por linha; single (por hand_id) alimenta o expand.
  verify:     () => req('GET', '/queue/hrc/verify'),
  verifyHand: (handId) => req('GET', `/queue/hrc/verify/${encodeURIComponent(handId)}`),
})
