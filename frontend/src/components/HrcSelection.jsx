// Multi-select "Enviar ao HRC" (pt69) — contexto + componentes da Estudo.
//
// Desenho aprovado (REGISTO_CONCEITO 2026-06-11, journal pt68 §7):
//   - release FORÇADO, independente do cabaz/janela (o gesto é "eu quero ESTAS");
//   - estado por mão (nada / na fila / concluída / falhou);
//   - guardas com motivo (checkbox desabilitado nas não-exportáveis + motivo no hover).
//
// Backend já LIVE: POST /api/queue/hrc/release {hand_ids} + POST /api/queue/hrc/states.
//
// Arquitectura: contexto leve (em vez de prop-drilling pela cadeia
// TagGroup → TournamentGroup → HandRow). HandRow é usado em 4 páginas; o gate
// `useHrcSelection() === null` garante que os checkboxes só aparecem onde o
// HrcSelectionProvider envolve (apenas a Estudo). Os estados são carregados em
// lote (ensureStates) à medida que as linhas montam.
import { createContext, useCallback, useContext, useRef, useState } from 'react'
import { queue } from '../api/client'

const Ctx = createContext(null)

export function useHrcSelection() {
  return useContext(Ctx)
}

const HRC_STATE_STYLE = {
  'na fila':   { label: 'Na fila',   color: '#f59e0b', bg: 'rgba(245,158,11,0.15)', bd: 'rgba(245,158,11,0.35)' },
  'concluída': { label: 'Concluída', color: '#22c55e', bg: 'rgba(34,197,94,0.15)',  bd: 'rgba(34,197,94,0.35)' },
  'falhou':    { label: 'Falhou',    color: '#ef4444', bg: 'rgba(239,68,68,0.15)',  bd: 'rgba(239,68,68,0.35)' },
}

// ── Provider ────────────────────────────────────────────────────────────────

export function HrcSelectionProvider({ children }) {
  const [selected, setSelected] = useState(() => new Set())
  // hand_id (TEXT) -> { state, exportable, reason }
  const [states, setStates] = useState({})

  // Batching de ensureStates: junta ids pedidos num curto intervalo num único POST.
  const pendingRef = useRef(new Set())
  const timerRef = useRef(null)
  const statesRef = useRef(states)
  statesRef.current = states

  const flush = useCallback(async () => {
    timerRef.current = null
    const ids = [...pendingRef.current]
    pendingRef.current = new Set()
    if (!ids.length) return
    try {
      const r = await queue.states(ids)
      setStates(prev => ({ ...prev, ...(r.states || {}) }))
    } catch {
      // Silencioso — sem estado, os badges não aparecem (degradação graciosa).
    }
  }, [])

  // Pede estados para `ids` ainda desconhecidos (dedup vs states já carregados
  // e vs pending). Idempotente — seguro chamar por cada linha/grupo.
  const ensureStates = useCallback((ids) => {
    let added = false
    for (const id of ids || []) {
      if (!id) continue
      if (statesRef.current[id] || pendingRef.current.has(id)) continue
      pendingRef.current.add(id)
      added = true
    }
    if (added && !timerRef.current) timerRef.current = setTimeout(flush, 60)
  }, [flush])

  // Re-fetch forçado (após release) — actualiza badges mesmo já em states.
  const refreshStates = useCallback(async (ids) => {
    const list = (ids && ids.length ? ids : Object.keys(statesRef.current)).filter(Boolean)
    if (!list.length) return
    try {
      const r = await queue.states(list)
      setStates(prev => ({ ...prev, ...(r.states || {}) }))
    } catch {
      // noop
    }
  }, [])

  const toggle = useCallback((handId) => {
    if (!handId) return
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(handId)) next.delete(handId)
      else next.add(handId)
      return next
    })
  }, [])

  const setMany = useCallback((ids, value) => {
    setSelected(prev => {
      const next = new Set(prev)
      for (const id of ids || []) {
        if (!id) continue
        if (value) next.add(id)
        else next.delete(id)
      }
      return next
    })
  }, [])

  const clear = useCallback(() => setSelected(new Set()), [])

  const value = {
    selected, states, ensureStates, refreshStates, toggle, setMany, clear,
  }
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

// ── Checkbox por linha ──────────────────────────────────────────────────────

// Lê o contexto directamente. Desabilita-se quando o estado leve diz
// não-exportável (motivo no hover). Mãos cujo estado ainda não chegou ficam
// selecionáveis — o /release re-valida com o guard profundo e devolve o motivo.
export function RowCheckbox({ handId }) {
  const hrc = useHrcSelection()
  if (!hrc || !handId) return null
  const st = hrc.states[handId]
  const disabled = !!st && !st.exportable
  const checked = hrc.selected.has(handId)
  const title = disabled
    ? (st.reason || 'não exportável')
    : 'Selecionar esta mão para enviar ao HRC'
  return (
    <input
      type="checkbox"
      checked={checked}
      disabled={disabled}
      title={title}
      onClick={e => e.stopPropagation()}
      onChange={() => hrc.toggle(handId)}
      style={{
        cursor: disabled ? 'not-allowed' : 'pointer',
        accentColor: '#6366f1',
        width: 14, height: 14,
        opacity: disabled ? 0.4 : 1,
      }}
    />
  )
}

// ── Badge de estado HRC por mão ─────────────────────────────────────────────

export function HrcStateBadge({ handId }) {
  const hrc = useHrcSelection()
  if (!hrc || !handId) return null
  const st = hrc.states[handId]
  const meta = st && HRC_STATE_STYLE[st.state]
  if (!meta) return null   // 'nada' (ou ainda a carregar) → sem badge
  return (
    <span
      title={`HRC: ${meta.label}`}
      style={{
        fontSize: 9, fontWeight: 700, letterSpacing: 0.3, whiteSpace: 'nowrap',
        padding: '2px 6px', borderRadius: 3,
        color: meta.color, background: meta.bg, border: `1px solid ${meta.bd}`,
      }}
    >{meta.label}</span>
  )
}

// ── "Selecionar todas" do grupo/torneio (tri-estado) ────────────────────────

// `handIds` = todas as mãos do grupo. Opera só sobre as exportáveis-ou-desconhecidas
// (não tenta selecionar as que o guard leve já marcou não-exportáveis).
export function GroupSelectAll({ handIds, title }) {
  const hrc = useHrcSelection()
  if (!hrc) return null
  const ids = (handIds || []).filter(Boolean)
  const selectable = ids.filter(id => {
    const s = hrc.states[id]
    return !s || s.exportable
  })
  if (selectable.length === 0) return null
  const selCount = selectable.filter(id => hrc.selected.has(id)).length
  const allSel = selCount === selectable.length && selCount > 0
  const someSel = selCount > 0 && !allSel
  // Ref callback simples (não-hook) para o estado indeterminate.
  const setRef = (node) => { if (node) node.indeterminate = someSel }
  return (
    <input
      type="checkbox"
      ref={setRef}
      checked={allSel}
      title={title || 'Selecionar/limpar todas as exportáveis deste grupo'}
      onClick={e => e.stopPropagation()}
      onChange={() => hrc.setMany(selectable, !allSel)}
      style={{ cursor: 'pointer', accentColor: '#6366f1', width: 14, height: 14 }}
    />
  )
}

// ── Barra de acção fixa ─────────────────────────────────────────────────────

function summarizeSkipped(skipped) {
  // Agrupa motivos para um resumo conciso.
  const byReason = {}
  for (const s of skipped || []) {
    const r = s.reason || 'não exportável'
    byReason[r] = (byReason[r] || 0) + 1
  }
  return Object.entries(byReason).map(([r, n]) => `${n}× ${r}`)
}

export function HrcActionBar() {
  const hrc = useHrcSelection()
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)
  if (!hrc) return null

  const ids = [...hrc.selected]
  const n = ids.length
  if (n === 0 && !result) return null

  async function send() {
    setBusy(true)
    setResult(null)
    try {
      const r = await queue.release(ids)
      await hrc.refreshStates([
        ...(r.released || []),
        ...((r.skipped || []).map(s => s.hand_id)),
      ])
      hrc.setMany(r.released || [], false)   // tira as enviadas da selecção
      setResult(r)
    } catch (e) {
      setResult({ error: e.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{
      position: 'fixed', left: 0, right: 0, bottom: 0, zIndex: 900,
      display: 'flex', justifyContent: 'center', pointerEvents: 'none',
      padding: '0 16px 18px',
    }}>
      <div style={{
        pointerEvents: 'auto',
        display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap',
        background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: 12,
        padding: '12px 18px', boxShadow: '0 8px 32px rgba(0,0,0,0.45)',
        maxWidth: 900,
      }}>
        <span style={{ fontSize: 13, color: '#e2e8f0', fontWeight: 600 }}>
          {n} {n === 1 ? 'mão selecionada' : 'mãos selecionadas'}
        </span>

        <button
          onClick={send}
          disabled={busy || n === 0}
          style={{
            padding: '8px 18px', borderRadius: 8, fontSize: 13, fontWeight: 700,
            background: (busy || n === 0) ? '#3730a3' : '#6366f1',
            color: '#fff', border: 'none',
            cursor: (busy || n === 0) ? 'not-allowed' : 'pointer',
            opacity: (busy || n === 0) ? 0.7 : 1,
          }}
        >{busy ? 'A enviar…' : `Enviar ${n} ao HRC`}</button>

        {n > 0 && (
          <button
            onClick={() => hrc.clear()}
            style={{
              padding: '7px 12px', borderRadius: 8, fontSize: 12, fontWeight: 500,
              background: 'transparent', color: '#64748b', border: '1px solid #2a2d3a',
              cursor: 'pointer',
            }}
          >Limpar</button>
        )}

        {/* Resumo do último envio */}
        {result && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
            borderLeft: '1px solid #2a2d3a', paddingLeft: 14, fontSize: 12,
          }}>
            {result.error ? (
              <span style={{ color: '#ef4444' }}>Erro: {result.error}</span>
            ) : (
              <>
                <span style={{ color: '#22c55e', fontWeight: 600 }}>
                  ✓ {(result.released || []).length} na fila
                </span>
                {(result.skipped || []).length > 0 && (
                  <span
                    title={summarizeSkipped(result.skipped).join(' · ')}
                    style={{ color: '#f59e0b' }}
                  >
                    {result.skipped.length} ignorada{result.skipped.length === 1 ? '' : 's'}
                    {' '}({summarizeSkipped(result.skipped).join(' · ')})
                  </span>
                )}
              </>
            )}
            <button
              onClick={() => setResult(null)}
              title="Dispensar"
              style={{
                background: 'transparent', border: 'none', color: '#64748b',
                cursor: 'pointer', fontSize: 14, padding: '0 2px',
              }}
            >✕</button>
          </div>
        )}
      </div>
    </div>
  )
}
