import { useEffect, useRef, useState } from 'react'
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
function fmtPct(v) {
  if (v == null) return '—'
  if (v === 0) return '0%'
  const a = Math.abs(v)
  const d = a >= 0.1 ? 2 : a >= 0.01 ? 3 : 4
  return v.toFixed(d) + '%'
}

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
  const [evTop, setEvTop] = useState(null)     // top_ev_loss (preenche progressivo)
  const [evLeft, setEvLeft] = useState(null)   // nº por calcular durante o EV
  const evStarted = useRef(false)

  useEffect(() => {
    hrcResults.summary().then(d => { setData(d); setEvTop(d.top_ev_loss || []) })
      .catch(e => setErr(e.message))
  }, [])

  // Cartão 2 — calcula o EV perdido em ciclo incremental (cada chamada abre um
  // punhado de zips; nenhum request abre os 74 de uma vez → sem timeout). Atualiza
  // um estado SEPARADO (evTop/evLeft) para não re-disparar este effect.
  useEffect(() => {
    if (!data || evStarted.current || data.ev_ready || !data.ev_pending) return
    evStarted.current = true
    let cancelled = false
    ;(async () => {
      let remaining = data.ev_pending
      setEvLeft(remaining)
      while (remaining > 0 && !cancelled) {
        try {
          const r = await hrcResults.evCompute(12)
          remaining = r.remaining
          setEvLeft(remaining)
          const fresh = await hrcResults.summary()
          if (cancelled) break
          setEvTop(fresh.top_ev_loss || [])   // top5 progressivo, sem tocar `data`
        } catch { break }
      }
      if (!cancelled) setEvLeft(null)
    })()
    return () => { cancelled = true }
  }, [data])

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
          {evTop && evTop.length > 0 ? (
            <>
              {evTop.map((e) => (
                <div key={e.hand_id} style={{ padding: '4px 0', borderBottom: `1px solid ${C.border}` }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                    <span style={{ fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap', maxWidth: 170 }} title={`${e.tournament} · ${e.num}`}>
                      <span style={{ color: C.yellow, fontWeight: 700 }}>{e.hero_pos}</span> {e.hero_class} · {e.num}
                    </span>
                    <span style={{ color: C.red, fontWeight: 800, fontSize: 14, marginLeft: 8 }}>
                      −{fmtPct(e.loss_eq_pct)}
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: C.muted, overflow: 'hidden',
                    textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {e.real_label} → HRC {e.best_label}
                  </div>
                </div>
              ))}
              {evLeft ? <div style={{ fontSize: 11, color: C.muted, marginTop: 6 }}>a calcular… {evLeft} por fazer</div> : null}
            </>
          ) : evLeft != null ? (
            <div style={{ color: C.muted, fontSize: 13 }}>A calcular EV… {evLeft} mãos por fazer</div>
          ) : (
            <div style={{ color: C.muted, fontSize: 13 }}>Sem dados de EV (% equity ICM perdida vs HRC).</div>
          )}
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
                <div style={{ padding: '2px 0 8px 34px' }}>
                  {/* cabeçalho de colunas */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 0, padding: '3px 10px',
                    fontSize: 10, fontWeight: 700, letterSpacing: 0.3, color: C.muted,
                    textTransform: 'uppercase' }}>
                    <span style={{ width: 52 }}>Data</span>
                    <span style={{ width: 46 }}>Hora</span>
                    <span style={{ width: 58, textAlign: 'right' }}>Tree</span>
                    <span style={{ width: 130, paddingLeft: 14 }}>Mão nº</span>
                    <span style={{ width: 48, textAlign: 'right' }}>Left</span>
                    <span style={{ width: 66, textAlign: 'right' }}>Hero</span>
                    <span style={{ width: 70, textAlign: 'right' }}>Stack</span>
                    <span style={{ width: 66, textAlign: 'right' }}>1ª ação</span>
                  </div>
                  {g.hands.map((h) => {
                    const dt = h.played_at || ''
                    const data = dt.length >= 10 ? `${dt.slice(8, 10)}/${dt.slice(5, 7)}` : '—'
                    const hora = dt.length >= 16 ? dt.slice(11, 16) : '—'
                    return (
                      <div key={h.hand_id} title={h.hand_id} style={{ display: 'flex', alignItems: 'center',
                        gap: 0, padding: '5px 10px', fontSize: 13, color: C.text,
                        borderBottom: `1px solid ${C.border}` }}>
                        <span style={{ width: 52, color: C.muted, fontSize: 12 }}>{data}</span>
                        <span style={{ width: 46, color: C.muted, fontSize: 12 }}>{hora}</span>
                        <span style={{ width: 58, textAlign: 'right', color: C.muted, fontSize: 12 }}>
                          {h.zsize ? `${(h.zsize / 1e6).toFixed(1)} MB` : '—'}
                        </span>
                        <span style={{ width: 130, paddingLeft: 14, fontFamily: 'monospace',
                          fontWeight: 700, color: C.text }}>{h.num}</span>
                        <span style={{ width: 48, textAlign: 'right', color: C.muted }}>
                          {h.players_left ?? '—'}
                        </span>
                        <span style={{ width: 66, textAlign: 'right', color: C.yellow, fontWeight: 700 }}>
                          {h.hero_pos || '—'}
                        </span>
                        <span style={{ width: 70, textAlign: 'right', color: C.green }}>
                          {h.hero_stack_bb != null ? `${h.hero_stack_bb}bb` : '—'}
                        </span>
                        <span style={{ width: 66, textAlign: 'right', color: C.blue }}>
                          {h.first_action_pos || '—'}
                        </span>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
