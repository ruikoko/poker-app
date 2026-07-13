import { useEffect, useState } from 'react'
import { hrcResults } from '../api/client'

// Resultados HRC — landing (Fase 1). Cartões 1 (totais) + 3 (top torneios por
// instância) + lista "últimas resolvidas" colapsável por instância de torneio.
// Cartão 2 (Top EV perdido) = Fase 1b (motor de EV). Página da mão = Fase 2.

const C = {
  bg: '#0f1216', card: '#171b21', border: 'rgba(255,255,255,0.08)',
  text: '#e6e9ee', muted: '#8a93a0', yellow: '#f2c14e', green: '#4ea86b',
  orange: '#e8873a', blue: '#4e79c1', red: '#d05a5a',
}

function siteColor(s) { return s === 'GGPoker' ? C.red : s === 'Winamax' ? C.orange : C.muted }
function fmtColor(f) { return f === 'PKO' ? C.orange : C.blue }

function Badge({ children, color }) {
  return (
    <span style={{
      display: 'inline-block', padding: '1px 8px', borderRadius: 10, fontSize: 11,
      fontWeight: 700, color, border: `1px solid ${color}`, opacity: 0.95,
    }}>{children}</span>
  )
}

function Card({ title, children, flex = 1 }) {
  return (
    <div style={{
      flex, minWidth: 240, background: C.card, border: `1px solid ${C.border}`,
      borderRadius: 12, padding: '16px 18px',
    }}>
      <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: 0.5, color: C.muted,
        textTransform: 'uppercase', marginBottom: 12 }}>{title}</div>
      {children}
    </div>
  )
}

export default function HRCResults() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  const [open, setOpen] = useState({})   // tn -> bool

  useEffect(() => {
    hrcResults.summary().then(setData).catch(e => setErr(e.message))
  }, [])

  if (err) return <div style={{ padding: 24, color: C.red }}>Erro: {err}</div>
  if (!data) return <div style={{ padding: 24, color: C.muted }}>A carregar…</div>

  // agrupa as recentes por instância de torneio (tn), preservando a ordem
  const groups = []
  const idx = {}
  for (const h of data.recent_by_tourney) {
    if (!(h.tn in idx)) { idx[h.tn] = groups.length; groups.push({ tn: h.tn, hands: [] }) }
    groups[idx[h.tn]].hands.push(h)
  }

  return (
    <div style={{ padding: '20px 24px', color: C.text, maxWidth: 1180, margin: '0 auto' }}>
      <h1 style={{ fontSize: 22, fontWeight: 800, margin: '0 0 4px' }}>Resultados HRC</h1>
      <div style={{ color: C.muted, fontSize: 13, marginBottom: 20 }}>
        Mãos resolvidas pelo robot (trees em <code>hrc_jobs</code>). Lei
        <b> 2026-07-15-sizings-v3</b>. Fase 1 — landing.
      </div>

      {/* Cartões 1 / 2 / 3 */}
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 22 }}>
        <Card title="Totais">
          <div style={{ fontSize: 40, fontWeight: 800, lineHeight: 1, color: C.yellow }}>
            {data.total_resolved}
          </div>
          <div style={{ fontSize: 12, color: C.muted, marginBottom: 12 }}>mãos resolvidas · {data.instances_total} torneios</div>
          <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontSize: 11, color: C.muted, marginBottom: 4 }}>Por sala</div>
              {Object.entries(data.by_site).map(([k, v]) => (
                <div key={k} style={{ fontSize: 13, marginBottom: 2 }}>
                  <span style={{ color: siteColor(k), fontWeight: 700 }}>{k}</span> · {v}
                </div>
              ))}
            </div>
            <div>
              <div style={{ fontSize: 11, color: C.muted, marginBottom: 4 }}>Por formato</div>
              {Object.entries(data.by_format).map(([k, v]) => (
                <div key={k} style={{ fontSize: 13, marginBottom: 2 }}>
                  <span style={{ color: fmtColor(k), fontWeight: 700 }}>{k}</span> · {v}
                </div>
              ))}
            </div>
          </div>
        </Card>

        <Card title="Top 5 EV perdido (vs HRC)">
          <div style={{ color: C.muted, fontSize: 13, lineHeight: 1.5 }}>
            Em cálculo — <b>próxima fase</b>.<br />
            Mede a % de equity ICM que a jogada real perdeu contra a resposta do HRC,
            lida dos <code>evs</code> de cada nó.
          </div>
        </Card>

        <Card title="Top 5 torneios (instâncias)">
          {data.top_tourneys_inst.map((t) => (
            <div key={t.tn} style={{ display: 'flex', justifyContent: 'space-between',
              alignItems: 'center', padding: '4px 0', borderBottom: `1px solid ${C.border}` }}>
              <div style={{ fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis',
                whiteSpace: 'nowrap', maxWidth: 220 }} title={t.label}>
                <span style={{ color: fmtColor(t.format), fontWeight: 700 }}>●</span> {t.label}
              </div>
              <div style={{ fontSize: 14, fontWeight: 800, color: C.yellow, marginLeft: 8 }}>{t.count}</div>
            </div>
          ))}
        </Card>
      </div>

      {/* Lista — últimas resolvidas, colapsável por instância de torneio */}
      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12,
        padding: '8px 6px' }}>
        <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: 0.5, color: C.muted,
          textTransform: 'uppercase', padding: '8px 12px' }}>Últimas resolvidas — por torneio</div>
        {groups.map((g) => {
          const first = g.hands[0]
          const isOpen = !!open[g.tn]
          return (
            <div key={g.tn} style={{ margin: '0 6px 6px' }}>
              <div onClick={() => setOpen(o => ({ ...o, [g.tn]: !o[g.tn] }))}
                style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer',
                  padding: '9px 12px', background: 'rgba(255,255,255,0.03)', borderRadius: 8,
                  transition: 'background 0.12s' }}
                onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.07)'}
                onMouseLeave={e => e.currentTarget.style.background = 'rgba(255,255,255,0.03)'}>
                <span style={{ color: C.muted, width: 12 }}>{isOpen ? '▾' : '▸'}</span>
                <span style={{ fontWeight: 700, fontSize: 14, flex: 1, overflow: 'hidden',
                  textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{first.tournament}</span>
                <Badge color={siteColor(first.site)}>{first.site}</Badge>
                <Badge color={fmtColor(first.format)}>{first.format}</Badge>
                <span style={{ color: C.muted, fontSize: 12, minWidth: 90, textAlign: 'right' }}>
                  {first.played_at ? first.played_at.slice(0, 16) : '—'}
                </span>
                <span style={{ fontWeight: 800, color: C.yellow, minWidth: 30, textAlign: 'right' }}>
                  {g.hands.length}
                </span>
              </div>
              {isOpen && (
                <div style={{ padding: '4px 0 6px 34px' }}>
                  {g.hands.map((h) => (
                    <div key={h.hand_id} style={{ display: 'flex', alignItems: 'center', gap: 12,
                      padding: '5px 10px', fontSize: 13, color: C.text,
                      borderBottom: `1px solid ${C.border}` }}>
                      <span style={{ fontFamily: 'monospace', color: C.muted, flex: 1 }}>{h.hand_id}</span>
                      <span style={{ color: C.muted, fontSize: 12 }}>
                        {h.played_at ? h.played_at.slice(0, 16) : '—'}
                      </span>
                      {h.buy_in && <span style={{ color: C.green, fontSize: 12 }}>${h.buy_in}</span>}
                      <span style={{ color: C.muted, fontSize: 11 }}>
                        {h.zsize ? `${(h.zsize / 1e6).toFixed(1)} MB` : ''}
                      </span>
                      {/* Fase 2: botão HRC (amarelo) -> página da mão */}
                      <span style={{ fontSize: 11, color: C.muted, fontStyle: 'italic' }}>
                        página da mão · próxima fase
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
