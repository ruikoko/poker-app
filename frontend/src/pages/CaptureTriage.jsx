import { useEffect, useState, useCallback } from 'react'
import { captureTriage } from '../api/client'
import ZoomableImage from '../components/Lightbox'

// Tags de 1 clique (nomes de canal Discord) + descartar. A tag integra a mão no
// fluxo normal (Estudo/Vilões) como se viesse do Discord.
const TAGS = [
  { tag: 'icm-pko', label: 'icm-pko', color: '#6366f1' },
  { tag: 'pos-pko', label: 'pos-pko', color: '#0ea5e9' },
  { tag: 'icm',     label: 'icm',     color: '#22c55e' },
  { tag: 'nota',    label: 'nota',    color: '#f59e0b' },
  { tag: '__discard__', label: 'descartar', color: '#ef4444' },
]

function fmtDate(iso) {
  if (!iso) return '—'
  // ISO sem offset = Lisboa naive (pt51) → mostra directo (data+hora curtas).
  return iso.replace('T', ' ').slice(0, 16)
}

export default function CaptureTriagePage() {
  const [hands, setHands] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState({})      // hand_id -> true enquanto aplica
  const [flash, setFlash] = useState(null)  // mensagem efémera

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const data = await captureTriage.list()
      setHands(data?.hands || [])
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  async function apply(handId, tag) {
    setBusy(b => ({ ...b, [handId]: true }))
    try {
      const res = await captureTriage.tag(handId, tag)
      // Optimista: tira da lista (resolvida ou descartada).
      setHands(hs => hs.filter(h => h.hand_id !== handId))
      const msg = res.status === 'discarded'
        ? `${handId} descartada`
        : `${handId} → ${tag}` + (res.villains_created ? ` (+${res.villains_created} vilão)` : '')
      setFlash(msg)
      setTimeout(() => setFlash(null), 2600)
    } catch (e) {
      setError(`Falha em ${handId}: ${e.message || e}`)
    } finally {
      setBusy(b => { const n = { ...b }; delete n[handId]; return n })
    }
  }

  return (
    <div style={{ padding: 24, maxWidth: 1180, margin: '0 auto' }}>
      <h1 style={{ fontSize: 20, fontWeight: 700, margin: '0 0 4px' }}>Marcadas por captura</h1>
      <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 16 }}>
        Mãos GG desanonimizadas pela SS de mesa (sem entrada Discord). Escolhe UMA tag —
        integra-se no Estudo/Vilões como se viesse do Discord — ou descarta.
      </div>

      {flash && (
        <div style={{ padding: '8px 12px', borderRadius: 8, marginBottom: 12, fontSize: 12,
          background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.3)', color: '#22c55e' }}>
          {flash}
        </div>
      )}
      {error && (
        <div style={{ padding: 12, borderRadius: 8, marginBottom: 14, fontSize: 13,
          background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', color: '#ef4444' }}>
          {error}
        </div>
      )}

      {loading && (
        <div style={{ padding: 28, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>A carregar…</div>
      )}
      {!loading && hands.length === 0 && (
        <div style={{ padding: 28, textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>
          Nada para triar. Capturas novas do Intuitive Tables aparecem aqui.
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {hands.map(h => (
          <div key={h.hand_id} style={{
            display: 'flex', gap: 14, padding: 12,
            border: '1px solid var(--border)', borderRadius: 'var(--radius)',
            background: 'var(--surface)', opacity: busy[h.hand_id] ? 0.5 : 1,
          }}>
            {/* SS de mesa ao lado da mão */}
            {h.table_ss_id != null ? (
              <ZoomableImage
                src={captureTriage.imageUrl(h.table_ss_id)}
                alt="SS de mesa"
                thumbStyle={{ width: 240, height: 'auto', borderRadius: 6, objectFit: 'contain',
                  border: '1px solid var(--border)', flexShrink: 0, alignSelf: 'flex-start' }}
                onError={e => { e.currentTarget.style.display = 'none' }}
              />
            ) : null}

            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 13, fontWeight: 600 }}>{h.tournament_name || h.hand_id}</span>
                <span style={{ fontSize: 11, color: 'var(--muted)' }}>{fmtDate(h.played_at)}</span>
                {h.deanon_partial && (
                  <span title="Nem todos os bancos foram mapeados (ambíguos ficaram por mapear)"
                    style={{ fontSize: 10, fontWeight: 600, padding: '2px 6px', borderRadius: 4,
                      background: 'rgba(245,158,11,0.12)', border: '1px solid rgba(245,158,11,0.3)', color: '#f59e0b' }}>
                    parcial
                  </span>
                )}
              </div>
              <div style={{ fontSize: 11, color: 'var(--muted)', margin: '6px 0 4px' }}>{h.hand_id}</div>
              <div style={{ fontSize: 12, lineHeight: 1.5 }}>
                {(h.players || []).map((p, i) => (
                  <span key={i} style={{ fontWeight: p === h.hero ? 700 : 400,
                    color: p === h.hero ? 'var(--text)' : 'var(--muted)' }}>
                    {p}{i < h.players.length - 1 ? ' · ' : ''}
                  </span>
                ))}
              </div>

              {/* Botões de 1 clique */}
              <div style={{ display: 'flex', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
                {TAGS.map(t => (
                  <button key={t.tag}
                    disabled={!!busy[h.hand_id]}
                    onClick={() => apply(h.hand_id, t.tag)}
                    style={{ padding: '5px 12px', fontSize: 12, fontWeight: 600, borderRadius: 5,
                      cursor: busy[h.hand_id] ? 'default' : 'pointer',
                      background: t.tag === '__discard__' ? 'transparent' : `${t.color}1a`,
                      border: `1px solid ${t.color}55`, color: t.color }}>
                    {t.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
