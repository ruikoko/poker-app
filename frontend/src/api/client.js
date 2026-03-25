const API_ROOT = import.meta.env.VITE_API_URL

if (!API_ROOT) {
  throw new Error('VITE_API_URL não definida no build do frontend')
}

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
}

// ── Villains ──────────────────────────────────────────────────────────────────
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
