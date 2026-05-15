import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { hrc } from '../api/client'

const RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']

// Mapeia (row, col) -> chave de combo no node.hands_strategies. Convençao standard:
// linha == coluna -> par (XX); linha < coluna -> suited (Xs); linha > coluna -> offsuit (Xo).
function comboKey(row, col) {
  const r1 = RANKS[row]
  const r2 = RANKS[col]
  if (row === col) return r1 + r1
  if (row < col) return r1 + r2 + 's'
  return r2 + r1 + 'o'
}

// Devolve {idx, freq, type, amount} da accao com maior frequencia.
// Considera a accao "dominante" para colorir a celula.
function dominantAction(played, actions) {
  if (!played || !actions || !played.length) return null
  let bestIdx = 0
  let bestFreq = played[0] ?? 0
  for (let i = 1; i < played.length; i++) {
    if (played[i] > bestFreq) { bestFreq = played[i]; bestIdx = i }
  }
  if (bestFreq <= 0) return null
  const action = actions[bestIdx] || {}
  return { idx: bestIdx, freq: bestFreq, type: action.type, amount: action.amount }
}

// Para colorir Raise (R), normalizamos o size relativo ao maior R do node.
// 0 = R mais pequeno (laranja claro); 1 = R maior / shove (vermelho escuro).
function raiseShade(amount, raiseAmounts) {
  if (!raiseAmounts.length) return 'rgba(245,158,11,0.55)'
  const max = Math.max(...raiseAmounts)
  const min = Math.min(...raiseAmounts)
  if (max === min) return 'rgba(245,158,11,0.6)'
  const t = (amount - min) / (max - min)
  // laranja (#f59e0b) -> vermelho escuro (#b91c1c)
  const r = Math.round(245 + (185 - 245) * t)
  const g = Math.round(158 + (28 - 158) * t)
  const b = Math.round(11 + (28 - 11) * t)
  return `rgba(${r},${g},${b},${0.55 + 0.3 * t})`
}

function actionColor(action, raiseAmounts) {
  if (!action) return 'rgba(100,116,139,0.15)'  // sem estrategia
  if (action.type === 'F') return 'rgba(100,116,139,0.25)'
  if (action.type === 'C') return 'rgba(34,197,94,0.55)'
  if (action.type === 'R') return raiseShade(action.amount, raiseAmounts)
  if (action.type === 'B') return 'rgba(59,130,246,0.55)'
  if (action.type === 'X') return 'rgba(148,163,184,0.4)'  // check
  return 'rgba(100,116,139,0.2)'
}

function actionLabel(action) {
  if (!action) return ''
  if (action.type === 'F') return 'F'
  if (action.type === 'C') return action.amount > 0 ? 'C' : 'X'
  if (action.type === 'R') return 'R'
  if (action.type === 'B') return 'B'
  return action.type || ''
}

function RangeMatrix({ node }) {
  const raiseAmounts = useMemo(
    () => (node?.actions || []).filter(a => a.type === 'R').map(a => a.amount),
    [node]
  )
  if (!node) return null
  const hands = node.hands_strategies || {}

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(13, 1fr)',
      gap: 2,
      width: '100%',
      maxWidth: 720,
      aspectRatio: '1 / 1',
    }}>
      {RANKS.flatMap((_, row) =>
        RANKS.map((_, col) => {
          const key = comboKey(row, col)
          const h = hands[key]
          const dom = h ? dominantAction(h.played, node.actions) : null
          const bg = actionColor(dom, raiseAmounts)
          const ev = dom ? h.evs[dom.idx] : null
          const evText = ev != null && Number.isFinite(ev) ? ev.toFixed(2) : ''
          const tip = h
            ? `${key} — played=[${h.played?.map(p => (p * 100).toFixed(0) + '%').join(' / ')}] evs=[${h.evs?.map(e => e.toFixed(2)).join(' / ')}]`
            : key

          return (
            <div
              key={`${row}-${col}`}
              title={tip}
              style={{
                background: bg,
                color: '#0f1117',
                aspectRatio: '1 / 1',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 10,
                fontWeight: 700,
                borderRadius: 3,
                fontFamily: "'Fira Code', monospace",
                lineHeight: 1.05,
                cursor: 'help',
              }}
            >
              <div>{key}</div>
              {dom && (
                <div style={{ fontSize: 9, fontWeight: 500, opacity: 0.85 }}>
                  {actionLabel(dom)}{ev != null && Number.isFinite(ev) ? ` ${evText}` : ''}
                </div>
              )}
            </div>
          )
        })
      )}
    </div>
  )
}

function Legend({ actions }) {
  if (!actions || !actions.length) return null
  const raiseAmounts = actions.filter(a => a.type === 'R').map(a => a.amount)
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 12, fontSize: 12, color: 'var(--muted)' }}>
      {actions.map((a, i) => (
        <span key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <span style={{
            width: 14, height: 14, borderRadius: 3,
            background: actionColor(a, raiseAmounts),
          }} />
          {actionLabel(a)}
          {a.type === 'R' || a.type === 'C' ? ` ${a.amount.toLocaleString()}` : ''}
        </span>
      ))}
    </div>
  )
}

function SettingsPanel({ settings }) {
  if (!settings) return null
  const handdata = settings.handdata || {}
  const eqmodel  = settings.eqmodel  || {}
  const structure = eqmodel.structure || {}
  const stacks = handdata.stacks || []
  const blinds = handdata.blinds || []  // [bb, sb, ante]
  const [bb, sb, ante] = [blinds[0], blinds[1], blinds[2]]
  const prizes = structure.prizes || {}
  const prizeEntries = Object.entries(prizes)
    .map(([place, amt]) => [Number(place), Number(amt)])
    .filter(([p]) => Number.isFinite(p))
    .sort((a, b) => a[0] - b[0])
    .slice(0, 5)

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16, marginBottom: 24 }}>
      <div className="card" style={{ padding: 16 }}>
        <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 12 }}>
          Mesa
        </div>
        <Row label="Stacks">
          <span style={{ fontFamily: "'Fira Code', monospace", fontSize: 12 }}>
            {stacks.length ? stacks.map(s => s.toLocaleString()).join(' / ') : '—'}
          </span>
        </Row>
        <Row label="Blinds (BB / SB / ante)">
          <span style={{ fontFamily: "'Fira Code', monospace", fontSize: 12 }}>
            {bb?.toLocaleString() ?? '—'} / {sb?.toLocaleString() ?? '—'} / {ante?.toLocaleString() ?? '—'}
          </span>
        </Row>
        <Row label="Ante type">{handdata.anteType || '—'}</Row>
        <Row label="Engine">{settings.engine?.type || '—'}</Row>
      </div>

      <div className="card" style={{ padding: 16 }}>
        <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 12 }}>
          Estrutura
        </div>
        <Row label="Equity model">{eqmodel.id || '—'}</Row>
        <Row label="Bounty type">{structure.bountyType || '—'}</Row>
        <Row label="Bounty">
          {structure.bounty != null ? `$${Number(structure.bounty).toFixed(2)}` : '—'}
        </Row>
        <Row label="Chips em jogo">
          {structure.chips != null ? Number(structure.chips).toLocaleString() : '—'}
        </Row>
        <Row label="Top 5 prizes">
          {prizeEntries.length === 0 ? '—' : (
            <span style={{ fontFamily: "'Fira Code', monospace", fontSize: 11 }}>
              {prizeEntries.map(([p, a]) => `#${p} $${a.toLocaleString()}`).join(' · ')}
            </span>
          )}
        </Row>
      </div>
    </div>
  )
}

function Row({ label, children }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', marginBottom: 8, gap: 8 }}>
      <span style={{ minWidth: 160, color: 'var(--muted)', fontSize: 12 }}>{label}</span>
      <span style={{ fontSize: 13 }}>{children}</span>
    </div>
  )
}

export default function HRCSessionDetailPage() {
  const { id } = useParams()
  const [session, setSession] = useState(null)
  const [rootNode, setRootNode] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancel = false
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const [s, n] = await Promise.all([hrc.session(id), hrc.node(id, 0)])
        if (cancel) return
        setSession(s)
        setRootNode(n)
      } catch (e) {
        if (!cancel) setError(String(e.message || e))
      } finally {
        if (!cancel) setLoading(false)
      }
    }
    load()
    return () => { cancel = true }
  }, [id])

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <div>
          <div className="page-title">
            {session ? session.name : `Session #${id}`}
          </div>
          <div className="page-subtitle">
            {session
              ? `${Number(session.total_nodes).toLocaleString()} nodes · source=${session.source} · importado ${new Date(session.uploaded_at).toLocaleString('pt-PT')}`
              : 'A carregar…'}
          </div>
        </div>
        <Link to="/hrc-sessions" className="btn btn-ghost btn-sm">← Voltar</Link>
      </div>

      {error && (
        <div style={{
          background: 'rgba(239,68,68,0.1)',
          border: '1px solid var(--red)',
          color: '#fca5a5',
          padding: '12px 16px',
          borderRadius: 'var(--radius)',
          marginBottom: 16,
        }}>
          {error}
        </div>
      )}

      {loading && !session && (
        <div style={{ color: 'var(--muted)' }}>A carregar…</div>
      )}

      {session && (
        <>
          <SettingsPanel settings={session.settings} />

          <div className="card" style={{ padding: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 16 }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>Range Matrix — Node 0 (root)</div>
                <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>
                  {rootNode
                    ? `Player ${rootNode.player} · street ${rootNode.street} · ${rootNode.actions?.length || 0} acções disponíveis`
                    : ''}
                </div>
              </div>
            </div>

            <RangeMatrix node={rootNode} />
            <Legend actions={rootNode?.actions} />
          </div>
        </>
      )}
    </div>
  )
}
