import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ggHealth, tableSs, API_ROOT } from '../api/client'

// "Saúde das mãos GG" — Fase 1 (mostrar) + Fase 2 (AÇÕES). Vista por IMAGEM.
// Só GG. Ação 1: tagar (multi-select). Ação 2: ligar órfã à mão. Ação 3:
// aceitar/rejeitar/rever suspeita. Confirmação nas Ações 2/3 (mexem em ligações).

const NEEDS = [
  { key: 'gold_no_tag', label: 'Gold sem tag', color: '#eab308' },
  { key: 'orphans', label: 'Órfãs (sem mão)', color: '#f59e0b' },
  { key: 'swap_suspects', label: 'Suspeitas de troca', color: '#f59e0b' },
  { key: 'tag_conflicts', label: 'Conflito de tags', color: '#ef4444' },
  { key: 'ft_quarantine', label: 'Fronteira FT (rever)', color: '#f59e0b' },
  { key: 'name_quarantine', label: 'Nomes em conflito', color: '#a78bfa' },
]
const HEALTHY = [
  { key: 'gold_matched', label: 'Gold que casou', color: '#22c55e' },
  { key: 'it_matched', label: 'IT desanon', color: '#22c55e' },
]
const LABELS = Object.fromEntries([...NEEDS, ...HEALTHY].map(g => [g.key, g.label]))
// As 11 tags canónicas (Ação 1) — espelho de _TAG_BUTTONS no backend.
const CANONICAL_TAGS = ['icm', 'icm-pko', 'pos-pko', 'pos-nko', 'speed-racer',
  'icm-ft', 'icm-pko-ft', 'pos-pko-ft', 'pos-nko-ft', 'speed-racer-ft', 'nota']

const card = { background: 'var(--card,#161b22)', border: '1px solid var(--border,#30363d)', borderRadius: 8 }
const btn = { background: '#21262d', border: '1px solid #30363d', color: '#c9d1d9', borderRadius: 5, cursor: 'pointer', fontSize: 12, padding: '3px 8px' }
const mono = "'Fira Code',monospace"
const inp = { fontFamily: mono, fontSize: 12, background: '#0b0d13', color: '#c9d1d9', border: '1px solid #30363d', borderRadius: 5, padding: '3px 6px' }

function Panel({ g, value, onClick }) {
  return (
    <button onClick={onClick} style={{
      ...card, padding: '16px 18px', minWidth: 160, cursor: 'pointer', textAlign: 'left',
      borderLeft: `3px solid ${g.color}`,
    }}>
      <div style={{ fontSize: 32, fontWeight: 800, color: g.color, lineHeight: 1 }}>{value ?? '—'}</div>
      <div style={{ fontSize: 13, color: 'var(--muted)', marginTop: 6 }}>{g.label} →</div>
    </button>
  )
}

function TipoBadge({ source }) {
  const gold = source === 'gold'
  return <span style={{ fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 5,
    color: gold ? '#eab308' : '#22c55e', background: gold ? 'rgba(234,179,8,0.12)' : 'rgba(34,197,94,0.12)' }}>
    {gold ? '🟡 Gold' : '🟢 IT'}</span>
}

function NumBadge({ im }) {
  if (im.num_matches === true) return <span style={{ fontSize: 11, color: '#22c55e' }}>✓ bate</span>
  if (im.num_matches === false) return <span style={{ fontSize: 11, fontWeight: 700, color: '#000', background: '#f59e0b', padding: '1px 7px', borderRadius: 5 }}>⚠ nº≠mão</span>
  return <span style={{ fontSize: 11, color: '#64748b' }}>—</span>
}

function imgSrc(im) { return API_ROOT + im.image_url }

function Row({ im, group, onZoom, selected, onToggleSel, onLink, onResolve = () => {} }) {
  const src = imgSrc(im)
  const [orph, setOrph] = useState('')
  const isGoldNoTag = group === 'gold_no_tag'
  const isOrphan = group === 'orphans'
  const isSwap = group === 'swap_suspects'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 10px', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
      {isGoldNoTag && (
        <input type="checkbox" checked={selected.has(im.hand_id)} onChange={() => onToggleSel(im.hand_id)}
          style={{ width: 16, height: 16, flexShrink: 0, cursor: 'pointer' }} />
      )}
      {/* Miniatura → clica abre a IMAGEM ampliada (lightbox). */}
      <img src={src} alt="" loading="lazy" onClick={() => onZoom(src)}
        style={{ width: 96, height: 60, objectFit: 'cover', borderRadius: 4, border: '1px solid #2a2d3a', flexShrink: 0, background: '#0b0d13', cursor: 'zoom-in' }} />
      <TipoBadge source={im.source} />
      <span style={{ fontFamily: "'Fira Code',monospace", fontSize: 12, color: '#94a3b8', minWidth: 96 }}>{im.filename_num || '—'}</span>
      {im.hand_db_id
        ? <Link to={`/hand/${im.hand_db_id}`} style={{ fontFamily: "'Fira Code',monospace", fontSize: 12, color: '#60a5fa', minWidth: 130, textDecoration: 'none' }}>{im.hand_id}</Link>
        : <span style={{ fontFamily: "'Fira Code',monospace", fontSize: 12, color: '#64748b', minWidth: 130 }}>sem mão</span>}
      <NumBadge im={im} />
      <span style={{ display: 'flex', gap: 4, flexWrap: 'wrap', flex: 1 }}>
        {(im.tags || []).map((t, i) => <span key={i} style={{ fontSize: 10, color: '#a5b4fc', background: 'rgba(99,102,241,0.12)', padding: '1px 6px', borderRadius: 4 }}>{t}</span>)}
        {(im.conflicts || []).map((c, i) => <span key={'c' + i} style={{ fontSize: 10, fontWeight: 700, color: '#fff', background: '#ef4444', padding: '1px 6px', borderRadius: 4 }}>conflito {c}</span>)}
      </span>
      {/* Ação 2 — ligar órfã à mão escolhida pelo Rui. */}
      {isOrphan && (
        <span style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
          <input value={orph} onChange={e => setOrph(e.target.value)} placeholder="GG-..."
            style={{ width: 130, fontFamily: "'Fira Code',monospace", fontSize: 12, background: '#0b0d13', color: '#c9d1d9', border: '1px solid #30363d', borderRadius: 4, padding: '3px 6px' }} />
          <button style={btn} onClick={() => onLink(im.ss_id, orph.trim())} disabled={!orph.trim()}>Ligar</button>
        </span>
      )}
      {/* Fase 1-A — resolver a suspeita escolhendo a dona certa (2 candidatas,
          com limpeza da mão antiga embutida no movimento). */}
      {isSwap && (
        <button style={{ ...btn, borderColor: '#818cf8', color: '#a5b4fc', flexShrink: 0 }}
          onClick={() => onResolve(im)}>Resolver ▸</button>
      )}
      <span style={{ fontSize: 11, color: im.state === 'órfã' ? '#f59e0b' : '#64748b', minWidth: 50, textAlign: 'right' }}>{im.state}</span>
    </div>
  )
}

// Fase 1-A — mini-tabela de seats de uma mão candidata (para comparar com a imagem).
function SeatMini({ seats }) {
  if (!seats || !seats.length) return <div style={{ fontSize: 11, color: '#64748b' }}>sem seats</div>
  return (
    <div style={{ fontFamily: "'Fira Code',monospace", fontSize: 11 }}>
      {seats.map((s, i) => (
        <div key={i} style={{ display: 'flex', gap: 8, color: s.is_hero ? '#fbbf24' : '#c9d1d9', lineHeight: 1.6 }}>
          <span style={{ width: 36, color: '#64748b' }}>{s.position || '—'}</span>
          <span style={{ width: 62, textAlign: 'right', color: '#94a3b8' }}>{s.stack_bb != null ? `${s.stack_bb}bb` : '—'}</span>
          <span>{s.nick || (s.raw_hash ? `(${s.raw_hash})` : '—')}</span>
        </div>
      ))}
    </div>
  )
}

function CandCard({ cand, onPick, busy }) {
  return (
    <div style={{ ...card, padding: 12, flex: 1, minWidth: 220, opacity: cand.exists ? 1 : 0.55 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 }}>
        <span style={{ fontFamily: "'Fira Code',monospace", fontSize: 12, color: '#60a5fa' }}>{cand.hand_id || 'sem mão'}</span>
        <span style={{ fontSize: 10, color: '#64748b' }}>{cand.role === 'current' ? 'ligada agora' : 'nº do ficheiro'}</span>
      </div>
      {cand.exists
        ? <SeatMini seats={cand.seats} />
        : <div style={{ fontSize: 12, color: '#f59e0b' }}>não existe na base</div>}
      {cand.exists && (
        <button onClick={() => onPick(cand.hand_id)} disabled={busy} style={{
          marginTop: 10, width: '100%', cursor: busy ? 'wait' : 'pointer',
          background: 'rgba(34,197,94,0.15)', border: '1px solid rgba(34,197,94,0.45)',
          color: '#4ade80', borderRadius: 5, fontSize: 12, fontWeight: 700, padding: '5px 8px',
        }}>✓ É esta a dona</button>
      )}
    </div>
  )
}

// Fase 1-A — escolher a dona certa da captura (2 candidatas, com pré-visualização
// dry-run da limpeza da mão antiga antes de gravar).
function SwapModal({ im, onClose, onDone }) {
  const [data, setData] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  useEffect(() => {
    if (!im) return
    setData(null); setErr(null)
    tableSs.swapCandidates(im.ss_id).then(setData).catch(e => setErr(e.message))
  }, [im])
  if (!im) return null
  const pick = async (owner) => {
    setBusy(true)
    try {
      const dry = await tableSs.resolveOwner(im.ss_id, owner, true)
      const rev = dry.plan && dry.plan.will_revert
      const msg = `Marcar ${owner} como dona desta captura.`
        + (rev ? `\n\nA mão ${rev.hand_id} (a antiga) volta a ANÓNIMA — limpa nomes, coroas e vilões.` : '')
        + `\n\nConfirmar?`
      if (!window.confirm(msg)) { setBusy(false); return }
      await tableSs.resolveOwner(im.ss_id, owner, false)
      onDone()
    } catch (e) { setErr(e.message || String(e)); setBusy(false) }
  }
  const unlink = async () => {
    if (!window.confirm('Desligar a captura de qualquer mão? (a antiga, se table_ss, volta a anónima)')) return
    setBusy(true)
    try { await tableSs.resolveOwner(im.ss_id, null, false); onDone() }
    catch (e) { setErr(e.message || String(e)); setBusy(false) }
  }
  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', zIndex: 2000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}>
      <div onClick={e => e.stopPropagation()} style={{ ...card, padding: 16, maxWidth: 920, width: '100%', maxHeight: '92vh', overflow: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <h3 style={{ margin: 0, fontSize: 15 }}>Qual é a dona desta captura?</h3>
          <button onClick={onClose} style={btn}>✕ fechar</button>
        </div>
        {err && <div style={{ color: '#fca5a5', marginBottom: 8, fontSize: 13 }}>Erro: {err}</div>}
        {!data ? <div style={{ color: 'var(--muted)' }}>A carregar…</div> : (
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            <img src={API_ROOT + data.capture.image_url} alt="" style={{ width: 300, maxWidth: '100%', borderRadius: 6, border: '1px solid #2a2d3a', alignSelf: 'flex-start' }} />
            <div style={{ flex: 1, minWidth: 300, display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>Ficheiro nº <b>{data.capture.filename_num || '—'}</b> — compara os stacks da imagem com cada mão e clica na dona.</div>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                <CandCard cand={data.candidates[0]} onPick={pick} busy={busy} />
                <CandCard cand={data.candidates[1]} onPick={pick} busy={busy} />
              </div>
              <button onClick={unlink} disabled={busy} style={{ ...btn, alignSelf: 'flex-start' }}>Nenhuma destas — desligar a captura</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function Lightbox({ src, onClose }) {
  if (!src) return null
  return (
    <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.92)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000, cursor: 'zoom-out' }}>
      <img src={src} alt="" style={{ maxWidth: '95vw', maxHeight: '95vh', borderRadius: 8 }} onClick={e => e.stopPropagation()} />
      <button onClick={onClose} style={{ position: 'absolute', top: 20, right: 20, background: 'rgba(255,255,255,0.1)', border: 'none', color: '#fff', fontSize: 24, cursor: 'pointer', borderRadius: 8, padding: '4px 12px' }}>✕</button>
    </div>
  )
}

// ── F4: quarentena/ensaio da fronteira FT (por TORNEIO, não por imagem) ──────
const FT_STATUS = {
  match: ['✓ bate', '#22c55e'], mismatch: ['⚠ discorda', '#ef4444'],
  n_unavailable: ['N indisponível', '#eab308'], incoherent: ['incoerente', '#f59e0b'],
  none: ['sem sinal', '#64748b'],
}
const FT_DECISION = {
  pending: ['pendente', '#64748b'], confirmed: ['confirmada', '#22c55e'],
  corrected: ['corrigida', '#818cf8'], promoted: ['promovida', '#22c55e'],
  dismissed: ['dispensada', '#64748b'],
}
function Pill({ map, k }) {
  const [lbl, col] = map[k] || [k, '#64748b']
  return <span style={{ fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 5, color: col, background: col + '22' }}>{lbl}</span>
}
function Cell({ label, children }) {
  return <div style={{ minWidth: 150 }}>
    <div style={{ fontSize: 10, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 0.4 }}>{label}</div>
    <div style={{ fontSize: 13, marginTop: 2 }}>{children}</div>
  </div>
}
const fmtT = (iso) => iso ? iso.replace('T', ' ').slice(0, 19) : '—'

function FtCard({ t, busy, onConfirm, onCorrect, onPromote, onApprove = () => {}, onDismiss = () => {}, onZoom = () => {} }) {
  const [ob, setOb] = useState('')
  const [on_, setOn] = useState('')
  const [plan, setPlan] = useState(null)   // plano dry-run do promote
  const cc = t.cross_check || {}
  const canPromote = t.decision === 'confirmed' || t.decision === 'corrected'
  const staleN = t.hrc_stale_count ?? (t.hrc_stale || []).length
  return (
    <div style={{ padding: '4px 2px 6px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10, flexWrap: 'wrap' }}>
        <Pill map={FT_STATUS} k={t.status} />
        <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--muted)' }}>
          {t.n_changes} mão(s) mudam · {staleN} HRC stale
        </span>
      </div>
      <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', paddingBottom: 6 }}>
        <Cell label="lobby (N lido)">{t.n_lobby != null ? `N = ${t.n_lobby}` : '— (sem print Info)'}</Cell>
        <Cell label="fronteira / via">{fmtT(t.boundary)}<br /><span style={{ color: '#818cf8' }}>{t.source || '—'}</span></Cell>
        <Cell label="1ª mão pós-fronteira">{t.seats_first_hand != null ? `${t.seats_first_hand} sentados` : '—'}</Cell>
        <Cell label="salvaguarda (cross-check)">
          {cc.match === true ? '✓ N = sentados' : cc.match === false ? `✗ N=${cc.n} ≠ ${cc.hh_seats}` : '— (sem N independente)'}
        </Cell>
      </div>
      {(t.warnings || []).map((w, i) => <div key={i} style={{ fontSize: 12, color: '#fbbf24', margin: '2px 0' }}>⚠ {w}</div>)}
      {t.via_b_diag && (
        <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4, fontFamily: mono }}>
          players_left: [{(t.via_b_diag.players_left_sequence || []).join(', ')}]
          {t.via_b_diag.outlier_dropped ? ' — outlier descartado' : ''}
          {t.via_b_diag.coherent === false ? ' — INCOERENTE' : ''}
        </div>
      )}
      {t.images && (
        <div style={{ marginTop: 10 }}>
          {(t.images.table_ss || []).length > 0 && (<>
            <div style={{ fontSize: 10, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 4 }}>
              Capturas de mesa — players_left (verde = ≤9)
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {t.images.table_ss.map((im, i) => (
                <div key={i} style={{ textAlign: 'center' }}>
                  <img src={API_ROOT + im.image_url} alt="" loading="lazy"
                    onClick={() => onZoom(API_ROOT + im.image_url)}
                    style={{ width: 100, height: 66, objectFit: 'cover', borderRadius: 5, cursor: 'zoom-in', border: '1px solid #30363d' }} />
                  <div style={{ fontSize: 12, fontWeight: 700, color: (im.players_left != null && im.players_left <= 9) ? '#22c55e' : '#c9d1d9' }}>{im.players_left ?? '—'}</div>
                  <div style={{ fontSize: 9, color: 'var(--muted)' }}>{(im.captured_at || '').slice(11, 16)}</div>
                </div>
              ))}
            </div>
          </>)}
          {(t.images.lobby || []).length > 0 && (<>
            <div style={{ fontSize: 10, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 0.4, margin: '8px 0 3px' }}>Lobbys (imagem não guardada)</div>
            {t.images.lobby.map((l, i) => (
              <div key={i} style={{ fontSize: 11, color: 'var(--muted)', fontFamily: mono }}>
                {(l.posted_at || '').replace('T', ' ').slice(0, 16)} · open_tab={l.open_tab || '—'} · pl={l.players_left ?? '—'}{l.final_table_size ? ` · N=${l.final_table_size}` : ''}
              </div>
            ))}
          </>)}
          {(t.images.hand_images || []).length > 0 && (<>
            <div style={{ fontSize: 10, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 0.4, margin: '8px 0 3px' }}>Outras imagens das mãos ({t.images.hand_images.length})</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {t.images.hand_images.map((im, i) => (
                <img key={i} src={API_ROOT + im.image_url} alt="" loading="lazy" title={im.hand_id}
                  onClick={() => onZoom(API_ROOT + im.image_url)}
                  style={{ width: 76, height: 50, objectFit: 'cover', borderRadius: 5, cursor: 'zoom-in', border: '1px solid #30363d' }} />
              ))}
            </div>
          </>)}
        </div>
      )}
      {(t.changes || []).length > 0 && (
        <details style={{ marginTop: 8 }}>
          <summary style={{ cursor: 'pointer', fontSize: 12, color: 'var(--muted)' }}>{t.changes.length} mãos: from → to</summary>
          <div style={{ maxHeight: 160, overflow: 'auto', marginTop: 6 }}>
            {t.changes.map((c, i) => (
              <div key={i} style={{ fontSize: 11, fontFamily: mono }}>
                {c.hand_id}: [{(c.from || []).join(', ')}] → [{(c.to || []).join(', ')}]
              </div>
            ))}
          </div>
        </details>
      )}
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 10, flexWrap: 'wrap' }}>
        {t.status === 'match' && (
          <button style={{ ...btn, borderColor: '#22c55e', fontWeight: 700 }} disabled={busy}
            onClick={async () => setPlan(await onApprove(t.tournament_number))}>
            Aprovar…
          </button>
        )}
        <button style={btn} disabled={busy} onClick={() => onConfirm(t.tournament_number)}>Confirmar</button>
        <span style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          <input value={ob} onChange={e => setOb(e.target.value)} placeholder="corrigir fronteira (ISO)" style={{ ...inp, width: 180 }} />
          <input value={on_} onChange={e => setOn(e.target.value)} placeholder="N" style={{ ...inp, width: 46 }} />
          <button style={btn} disabled={busy} onClick={() => onCorrect(t.tournament_number, ob, on_)}>Corrigir</button>
        </span>
        <button style={{ ...btn, borderColor: canPromote ? '#22c55e' : '#30363d', opacity: canPromote ? 1 : 0.4 }}
          disabled={busy || !canPromote}
          onClick={async () => setPlan(await onPromote(t.tournament_number, false))}>
          Promover…
        </button>
        {!canPromote && <span style={{ fontSize: 11, color: 'var(--muted)' }}>(confirma/corrige primeiro)</span>}
        <button style={{ ...btn, marginLeft: 'auto' }} disabled={busy}
          onClick={() => { if (window.confirm(`Dispensar ${t.tournament_number} (sem FT)?\nNão toca nas mãos nem nas tags — só regista a decisão de fronteira.`)) onDismiss(t.tournament_number) }}>
          Dispensar (sem FT)
        </button>
      </div>
      {t.reactivated && <div style={{ fontSize: 12, color: '#fbbf24', marginTop: 6 }}>⚠ sinal novo pós-dispensa — voltou a pendente</div>}
      {plan && (
        <div style={{ ...card, padding: 10, marginTop: 8, borderColor: '#22c55e' }}>
          <div style={{ fontSize: 12, marginBottom: 6 }}>
            Plano dry-run: <b>{(plan.plan?.changed || []).length}</b> mão(s) mudariam.
            {(t.hrc_stale_count ?? (t.hrc_stale || []).length) > 0 && <span> · <b>{t.hrc_stale_count ?? t.hrc_stale.length}</b> HRC stale (re-solve = F6)</span>} Escrever agora?
          </div>
          {t.partial_coverage && <div style={{ fontSize: 12, color: '#fbbf24', marginBottom: 6 }}>⚠ cobertura parcial: N={t.n} — a fronteira via-b pode perder as 1ªs mãos da FT. Promove COM este aviso.</div>}
          <button style={{ ...btn, borderColor: '#22c55e' }} disabled={busy}
            onClick={async () => { await onPromote(t.tournament_number, true); setPlan(null) }}>✓ Escrever (promover)</button>
          <button style={{ ...btn, marginLeft: 6 }} onClick={() => setPlan(null)}>Cancelar</button>
        </div>
      )}
    </div>
  )
}

function FtRow({ c, expanded, onToggle, full, busy, onConfirm, onCorrect, onPromote, onApprove, onDismiss, onZoom }) {
  return (
    <div style={{ ...card, marginBottom: 8, overflow: 'hidden' }}>
      <div onClick={onToggle} style={{ display: 'flex', gap: 10, alignItems: 'center', padding: '9px 12px', cursor: 'pointer', flexWrap: 'wrap' }}>
        <span style={{ fontSize: 11, color: 'var(--muted)', transform: expanded ? 'rotate(90deg)' : 'none', transition: 'transform .1s' }}>▸</span>
        <span style={{ fontFamily: mono, fontWeight: 700 }}>{c.tournament_number}</span>
        <span style={{ fontSize: 13 }}>{c.tournament_name || '—'}</span>
        <span style={{ fontSize: 12, color: 'var(--muted)' }}>{c.day || ''} · {c.n_hands} mãos</span>
        {c.status && <Pill map={FT_STATUS} k={c.status} />}
        {c.section === 'ready' && c.n != null && <span style={{ fontSize: 11, color: 'var(--muted)' }}>N={c.n}</span>}
        {c.partial_coverage && <span style={{ fontSize: 11, fontWeight: 700, color: '#000', background: '#fbbf24', padding: '1px 7px', borderRadius: 5 }}>⚠ cobertura parcial (N={c.n})</span>}
        <span style={{ marginLeft: 'auto' }}><Pill map={FT_DECISION} k={c.decision} /></span>
      </div>
      {expanded && (
        <div style={{ padding: '0 12px 10px', borderTop: '1px solid var(--border,#30363d)' }}>
          {full
            ? <FtCard t={full} busy={busy} onConfirm={onConfirm} onCorrect={onCorrect} onPromote={onPromote} onApprove={onApprove} onDismiss={onDismiss} onZoom={onZoom} />
            : <div style={{ padding: 12, color: 'var(--muted)' }}>A carregar ensaio…</div>}
        </div>
      )}
    </div>
  )
}

function FtQuarantinePanel() {
  const [list, setList] = useState(null)
  const [full, setFull] = useState({})       // tn → ensaio full
  const [expanded, setExpanded] = useState(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  const [zoom, setZoom] = useState(null)
  const loadList = () => ggHealth.ftPreview().then(r => setList(r.candidates || [])).catch(e => setMsg('Erro: ' + e.message))
  useEffect(() => { loadList() }, [])
  const loadFull = (tn) => ggHealth.ftPreview(tn)
    .then(r => setFull(f => ({ ...f, [tn]: r.tournaments[0] })))
    .catch(e => setMsg('Erro: ' + e.message))
  const toggle = (tn) => {
    if (expanded === tn) { setExpanded(null); return }
    setExpanded(tn)
    if (!full[tn]) loadFull(tn)
  }
  const refresh = (tn) => { loadFull(tn); loadList() }
  const wrap = (fn) => async (...a) => {
    setBusy(true); setMsg(null)
    try { return await fn(...a) }
    catch (e) { setMsg('Erro: ' + e.message) }
    finally { setBusy(false) }
  }
  const onConfirm = wrap(async (tn) => { await ggHealth.ftConfirm(tn); setMsg(`${tn}: fronteira confirmada.`); refresh(tn) })
  const onCorrect = wrap(async (tn, ob, n) => { await ggHealth.ftCorrect(tn, ob, n); setMsg(`${tn}: fronteira corrigida.`); refresh(tn) })
  const onPromote = wrap(async (tn, confirm) => {
    const r = await ggHealth.ftPromote(tn, confirm)
    if (confirm) { setMsg(`${tn}: promovida.`); refresh(tn) }
    return r
  })
  const onDismiss = wrap(async (tn) => { await ggHealth.ftDismiss(tn); setMsg(`${tn}: dispensada (sem FT) — mãos e tags intactas.`); refresh(tn) })
  // APROVAR (match limpo): fixa a fronteira (confirm) + devolve o plano dry-run; a
  // escrita real só no clique "Escrever" do plano (onPromote confirm=true).
  const onApprove = wrap(async (tn) => { await ggHealth.ftConfirm(tn); return await ggHealth.ftPromote(tn, false) })
  if (!list) return <div style={{ color: 'var(--muted)' }}>A carregar candidatos…</div>
  const rowsOf = (items) => items.map(c => (
    <FtRow key={c.tournament_number} c={c} expanded={expanded === c.tournament_number}
      onToggle={() => toggle(c.tournament_number)} full={full[c.tournament_number]}
      busy={busy} onConfirm={onConfirm} onCorrect={onCorrect} onPromote={onPromote}
      onApprove={onApprove} onDismiss={onDismiss} onZoom={setZoom} />
  ))
  const needs = list.filter(c => c.section === 'needs')
  const ready = list.filter(c => c.section === 'ready')
  const done = list.filter(c => c.section === 'done')
  const dismissed = list.filter(c => c.section === 'dismissed')
  const SecHead = ({ label, hint, color }) => (
    <div style={{ margin: '18px 0 8px' }}>
      <div style={{ fontSize: 13, fontWeight: 700, color }}>{label}</div>
      <div style={{ fontSize: 11, color: 'var(--muted)' }}>{hint}</div>
    </div>
  )
  return (
    <div>
      {msg && <div style={{ ...card, padding: '8px 12px', marginBottom: 10, fontSize: 13, color: /erro/i.test(msg) ? '#fca5a5' : '#93c5fd' }}>{msg}</div>}
      <SecHead label={`Precisam de ti (${needs.length})`} color="#f59e0b"
        hint="exige decisão tua — o motor não fixou fronteira ou o cross-check discorda. Corrige/investiga." />
      {needs.length ? rowsOf(needs) : <div style={{ padding: 12, color: '#22c55e', fontSize: 13 }}>✓ Nada a decidir.</div>}
      <SecHead label={`Prontas a aprovar (${ready.length})`} color="#22c55e"
        hint="match limpo — expande, vê o ensaio (dry-run), Confirmar fixa a fronteira e Promover escreve (com confirmação explícita)." />
      {ready.length ? rowsOf(ready) : <div style={{ padding: 12, color: 'var(--muted)', fontSize: 13 }}>— Nenhuma pronta.</div>}
      {done.length > 0 && (<>
        <SecHead label={`Concluídas (${done.length})`} color="var(--muted)" hint="já promovidas." />
        {rowsOf(done)}
      </>)}
      {dismissed.length > 0 && (<>
        <SecHead label={`Dispensados (${dismissed.length})`} color="var(--muted)"
          hint="sem FT (rebentou na bolha) — só anotação de fronteira; mãos e tags intactas. Volta a pendente se entrar sinal novo forte." />
        {rowsOf(dismissed)}
      </>)}
      <Lightbox src={zoom} onClose={() => setZoom(null)} />
    </div>
  )
}

// ── Fase 3: painel da propagação de nomes por hash + quarentena ──────────────

// Bloco de Seats do raw (OBRA 2a): a matéria do cruzamento posição+stack que o Rui usou
// à mão. Hash em disputa destacado.
function SeatBlock({ seats }) {
  return (
    <div style={{ margin: '3px 0 6px 14px', border: '1px solid #21262d', borderRadius: 5, overflow: 'hidden' }}>
      {(seats || []).map((s, i) => (
        <div key={i} style={{ display: 'flex', gap: 8, fontSize: 11, fontFamily: mono, padding: '2px 8px',
          background: s.disputed ? 'rgba(167,139,250,0.16)' : 'transparent',
          color: s.disputed ? '#c4b5fd' : '#94a3b8' }}>
          <span style={{ width: 34, color: '#64748b' }}>#{s.seat}</span>
          <span style={{ flex: 1, fontWeight: s.disputed ? 700 : 400 }}>{s.hash}{s.disputed ? ' ◀' : ''}</span>
          <span style={{ color: '#fbbf24' }}>{(s.stack ?? 0).toLocaleString()}</span>
        </div>
      ))}
    </div>
  )
}

// Uma aparição (mão) no lado: linha clicável (Link) + fonte + toggle Seats + anexar imagem.
function HandAppearance({ a, busy, onAttach }) {
  const [open, setOpen] = useState(false)
  const fileRef = useRef(null)
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
        {a.seats?.length > 0 && (
          <span onClick={() => setOpen(o => !o)} title="ver Seats do raw"
            style={{ cursor: 'pointer', color: '#64748b', transform: open ? 'rotate(90deg)' : 'none', transition: 'transform .1s', width: 10 }}>▸</span>
        )}
        {a.db_id
          ? <Link to={`/hand/${a.db_id}`} style={{ fontFamily: mono, color: '#60a5fa', textDecoration: 'none' }}>{a.hand_id}</Link>
          : <span style={{ fontFamily: mono, color: '#64748b' }}>{a.hand_id || '—'}</span>}
        <span style={{ fontSize: 10, fontWeight: 700, padding: '0 6px', borderRadius: 4,
          color: a.source === 'strong' ? '#86efac' : '#fbbf24',
          background: a.source === 'strong' ? 'rgba(34,197,94,0.12)' : 'rgba(251,191,36,0.12)' }}>
          {a.source === 'strong' ? 'forte' : 'fraca'}</span>
        <span style={{ color: 'var(--muted)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.name}</span>
        {a.hand_id && (
          <>
            <button disabled={busy} style={{ ...btn, fontSize: 10, padding: '1px 6px' }}
              title="Anexar Gold/captura do disco a esta mão (corre a Vision + liga)"
              onClick={() => fileRef.current?.click()}>+ imagem</button>
            <input ref={fileRef} type="file" accept="image/*" style={{ display: 'none' }}
              onChange={e => { const f = e.target.files?.[0]; if (f) onAttach(a.hand_id, f); e.target.value = '' }} />
          </>
        )}
      </div>
      {open && a.seats?.length > 0 && <SeatBlock seats={a.seats} />}
    </div>
  )
}

// Um LADO do conflito: o candidato (hash ou variante de nome) com as suas mãos
// (clicáveis + fonte forte/fraca + Seats), as imagens dessas mãos (miniatura → lightbox)
// e o "+ imagem" por mão. É com as imagens/Seats que o Rui reconhece o jogador.
function SideColumn({ side, isHash, actionLabel, onAct, busy, onZoom, onAttach }) {
  const appear = side.appearances || []
  const imgs = side.images || []
  return (
    <div style={{ ...card, padding: 10, flex: 1, minWidth: 260, background: '#0d1017' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
        {isHash
          ? <code style={{ fontSize: 13, color: '#c9d1d9' }}>{side.hash}</code>
          : <span style={{ fontSize: 13, fontWeight: 700 }}>{side.name}</span>}
        {isHash && <span style={{ fontSize: 12, color: 'var(--muted)' }}>lê-se <b>{side.name}</b></span>}
        <button disabled={busy} style={{ ...btn, marginLeft: 'auto', borderColor: '#22c55e', color: '#86efac', fontWeight: 700 }}
          onClick={onAct} title="Este é o jogador verdadeiro — fica com o nome; o outro fica branco">{actionLabel}</button>
      </div>
      {imgs.length > 0 ? (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
          {imgs.map((im, i) => (
            <img key={i} src={API_ROOT + im.image_url} alt="" loading="lazy" title={im.hand_id || ''}
              onClick={() => onZoom(API_ROOT + im.image_url)}
              style={{ width: 92, height: 60, objectFit: 'cover', borderRadius: 5, cursor: 'zoom-in', border: '1px solid #30363d' }} />
          ))}
        </div>
      ) : <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 8 }}>— sem imagens guardadas (usa «+ imagem» numa mão p/ anexar a Gold)</div>}
      <div style={{ fontSize: 10, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 3 }}>
        {appear.length} mão(s)
      </div>
      <div style={{ maxHeight: 220, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 2 }}>
        {appear.map((a, i) => <HandAppearance key={i} a={a} busy={busy} onAttach={onAttach} />)}
      </div>
    </div>
  )
}

function NameConflictCard({ it, busy, onChoose, onMerge, onDismiss, onReentry, onAttach, onZoom }) {
  const [custom, setCustom] = useState('')
  const isHash = it.kind !== 'same_hash'   // name_2_hash → lados são hashes; same_hash → variantes
  const sides = it.sides || []
  const re = it.reentry || {}
  const showReentry = isHash && re.applies && !re.co_present   // co-presentes → nunca re-entrada
  return (
    <div style={{ ...card, padding: 12, marginBottom: 10 }}>
      <div style={{ fontSize: 13, marginBottom: 8 }}>
        Torneio <b>{it.tournament_number}</b> · {isHash
          ? <>o nome <b>{it.conflict_key}</b> está em <b>2 lugares</b>. <span style={{ color: 'var(--muted)' }}>Ou é um lugar errado (escolhe «É este»), ou é a MESMA pessoa por re-entrada.</span></>
          : <>o hash <code>{it.conflict_key}</code> foi lido com <b>nomes diferentes</b>. <span style={{ color: 'var(--muted)' }}>Confirma qual a leitura certa.</span></>}
      </div>
      {/* Sinal de re-entrada / veneno duro (co-presentes) */}
      {isHash && re.applies && (
        re.co_present
          ? <div style={{ fontSize: 12, color: '#fca5a5', marginBottom: 8 }}>⛔ os 2 hashes aparecem na MESMA mão → impossível ser 1 pessoa (veneno real).</div>
          : re.likely_reentry
            ? <div style={{ fontSize: 12, color: '#86efac', marginBottom: 8 }}>↻ provável <b>re-entrada</b>: mesmo nick, fontes fortes dos 2 lados, janelas sem sobreposição. Confirma tu.</div>
            : <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>{re.same_nick ? 'mesmo nick' : 'nicks diferentes'}{re.disjoint_windows === false ? ' · janelas sobrepõem-se' : re.disjoint_windows ? ' · janelas disjuntas' : ''}{re.both_strong ? '' : ' · falta fonte forte num lado'}.</div>
      )}
      {sides.length > 0 ? (
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {sides.map((s, i) => (
            <SideColumn key={i} side={s} isHash={isHash} busy={busy} onZoom={onZoom} onAttach={onAttach}
              actionLabel={isHash ? 'É este' : 'É esta'}
              onAct={() => isHash ? onChoose(it, it.conflict_key, s.hash) : onMerge(it, s.name)} />
          ))}
        </div>
      ) : (
        // fallback (backend antigo, sem `sides`): só os candidatos como botões
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
          {(it.candidates || []).map(c => (
            <button key={c} disabled={busy} style={btn}
              onClick={() => isHash ? onChoose(it, it.conflict_key, c) : onMerge(it, c)}>
              {isHash ? <code>{c}</code> : c}</button>
          ))}
        </div>
      )}
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 10, flexWrap: 'wrap' }}>
        {showReentry && (
          <button disabled={busy} style={{ ...btn, borderColor: re.likely_reentry ? '#22c55e' : '#818cf8', color: re.likely_reentry ? '#86efac' : '#a5b4fc', fontWeight: re.likely_reentry ? 700 : 500 }}
            onClick={() => onReentry(it)} title="Os 2 hashes são a mesma pessoa (re-entrada) — o nome fica válido nos dois">
            ↻ Mesma pessoa (re-entrada)</button>
        )}
        {!isHash && <>
          <span style={{ color: 'var(--muted)', fontSize: 12 }}>ou outro nome:</span>
          <input value={custom} onChange={e => setCustom(e.target.value)} placeholder="nome certo"
            style={{ ...inp, width: 160 }} />
          <button disabled={busy || !custom.trim()} style={btn} onClick={() => onChoose(it, custom.trim(), null)}>Escolher</button>
        </>}
        <button disabled={busy} style={{ ...btn, marginLeft: 'auto', borderColor: '#6b7280', color: '#9ca3af' }}
          onClick={() => onDismiss(it)} title="Nenhum é fiável — ambos ficam brancos (honesto)">Dispensar</button>
      </div>
    </div>
  )
}

function NamePropagationPanel() {
  const [agg, setAgg] = useState(null)
  const [quar, setQuar] = useState(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  const [zoom, setZoom] = useState(null)

  const load = () => {
    ggHealth.namesQuarantine().then(r => setQuar(r.items || [])).catch(e => setMsg('Erro: ' + e.message))
    ggHealth.namesApply(null, true).then(setAgg).catch(() => {})   // dry-run agregado leve
  }
  useEffect(() => { load() }, [])

  const wrap = (fn) => async (...a) => {
    setBusy(true); setMsg(null)
    try { await fn(...a); load() } catch (e) { setMsg('Erro: ' + e.message) } finally { setBusy(false) }
  }
  const apply = wrap(async () => {
    const r = await ggHealth.namesApply()
    setMsg(`Propagação aplicada: ${r.hands_written} mãos escritas, ${r.fills} nomes. Quarentena: ${r.quarantine_pending}.`)
  })
  const onChoose = wrap(async (it, name, hash) => { await ggHealth.namesChoose({ tournament_number: it.tournament_number, kind: it.kind, conflict_key: it.conflict_key, chosen_name: name, chosen_hash: hash }); setMsg('Nome escolhido e propagado.') })
  const onMerge = wrap(async (it, name) => { await ggHealth.namesMerge({ tournament_number: it.tournament_number, kind: it.kind, conflict_key: it.conflict_key, chosen_name: name }); setMsg('Variantes fundidas e propagadas.') })
  const onDismiss = wrap(async (it) => { await ggHealth.namesDismiss({ tournament_number: it.tournament_number, kind: it.kind, conflict_key: it.conflict_key }); setMsg('Dispensado — fica branco.') })
  const onReentry = wrap(async (it) => { await ggHealth.namesReentry({ tournament_number: it.tournament_number, kind: it.kind, conflict_key: it.conflict_key, chosen_name: it.conflict_key }); setMsg('Re-entrada confirmada — o nome fica nos dois lugares.') })
  const onAttach = wrap(async (handId, file) => { const r = await tableSs.attachToHand(file, handId); setMsg(`Imagem anexada a ${handId} (${r.result || 'ok'}).`) })

  return (
    <div>
      <div style={{ ...card, padding: 12, marginBottom: 12 }}>
        <div style={{ fontSize: 13, marginBottom: 8 }}>
          A propagação copia nomes de <b>fonte forte</b> (Gold/verificada) para os mesmos hashes nas
          mãos <b>tagadas</b> do torneio. Casos limpos escrevem-se automaticamente; conflitos ficam aqui.
        </div>
        {agg && (
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 13, color: 'var(--muted)' }}>
            <span>Preenchimentos: <b style={{ color: 'inherit' }}>{agg.fills}</b></span>
            <span>Quarentena pendente: <b style={{ color: '#a78bfa' }}>{agg.quarantine_pending}</b></span>
            <span>Torneios: {agg.tournaments}</span>
          </div>
        )}
        <button disabled={busy} style={{ ...btn, marginTop: 10 }} onClick={apply}>
          {busy ? 'A aplicar…' : '⤵ Aplicar propagação (casos limpos)'}
        </button>
      </div>
      {msg && <div style={{ ...card, padding: '8px 12px', marginBottom: 10, fontSize: 13,
        color: /erro/i.test(msg) ? '#fca5a5' : '#93c5fd' }}>{msg}</div>}
      {!quar ? <div style={{ color: 'var(--muted)' }}>A carregar…</div> :
        quar.length === 0 ? <div style={{ ...card, padding: 16, color: '#22c55e' }}>✓ Sem nomes em conflito.</div> : (
          <>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>{quar.length} conflito(s) a decidir:</div>
            {quar.map((it, i) => (
              <NameConflictCard key={i} it={it} busy={busy}
                onChoose={onChoose} onMerge={onMerge} onDismiss={onDismiss}
                onReentry={onReentry} onAttach={onAttach} onZoom={setZoom} />
            ))}
          </>
        )}
      <Lightbox src={zoom} onClose={() => setZoom(null)} />
    </div>
  )
}

export default function GGHealth() {
  const [sum, setSum] = useState(null)
  const [err, setErr] = useState(null)
  const [searchParams] = useSearchParams()
  // Deep-link do selo "nome em revisão" (OBRA 3): ?panel=name_quarantine abre o painel.
  const [group, setGroup] = useState(searchParams.get('panel') || null)
  const [list, setList] = useState(null)
  const [page, setPage] = useState(1)
  const [zoom, setZoom] = useState(null)
  const [selected, setSelected] = useState(new Set())   // Ação 1: hand_ids marcados
  const [msg, setMsg] = useState(null)
  const [swapResolve, setSwapResolve] = useState(null)  // Fase 1-A: im em resolução
  // Pesquisa GLOBAL por nº de mão (só frontend: usa group=all, filtra localmente).
  const [q, setQ] = useState('')
  const [allImgs, setAllImgs] = useState(null)          // cache de TODAS as imagens
  const [loadingAll, setLoadingAll] = useState(false)

  // Carrega todas as imagens uma vez (páginas de 300) para pesquisar sem folhear.
  const ensureAll = () => {
    if (allImgs || loadingAll) return
    setLoadingAll(true)
    ;(async () => {
      try {
        const PS = 300
        const first = await ggHealth.list('all', 1, PS)
        let imgs = first.images || []
        const pages = Math.ceil((first.total || 0) / (first.page_size || PS))
        for (let p = 2; p <= pages; p++) {
          const r = await ggHealth.list('all', p, PS)
          imgs = imgs.concat(r.images || [])
        }
        setAllImgs(imgs)
      } catch (e) { setErr(e.message) }
      finally { setLoadingAll(false) }
    })()
  }
  useEffect(() => { if (q.trim()) ensureAll() }, [q])   // eslint-disable-line react-hooks/exhaustive-deps

  const qt = q.trim()
  const qDigits = qt.replace(/\D/g, '')
  const results = qt && allImgs
    ? allImgs.filter(im => {
        const hid = (im.hand_id || '').toLowerCase()
        const fn = im.filename_num || ''
        return (qDigits && (fn.includes(qDigits) || hid.replace(/\D/g, '').includes(qDigits)))
          || (!qDigits && hid.includes(qt.toLowerCase()))
      })
    : null

  const loadSummary = () => ggHealth.summary().then(setSum).catch(e => setErr(e.message))
  useEffect(() => { loadSummary() }, [])
  useEffect(() => {
    if (!group || group === 'ft_quarantine' || group === 'name_quarantine') { setList(null); return }
    setList(null)
    ggHealth.list(group, page).then(setList).catch(e => setErr(e.message))
  }, [group, page])

  const open = (k) => { setGroup(k); setPage(1); setSelected(new Set()); setMsg(null) }
  const reload = () => {
    loadSummary()
    ggHealth.list(group, page).then(setList).catch(e => setErr(e.message))
  }
  const toggleSel = (hid) => setSelected(s => {
    const n = new Set(s); n.has(hid) ? n.delete(hid) : n.add(hid); return n
  })

  // Ação 1 — tagar as mãos selecionadas.
  const applyTag = async (tag) => {
    const ids = [...selected]
    if (!ids.length) { setMsg('Seleciona pelo menos uma mão.'); return }
    try {
      let res = await ggHealth.tag(ids, tag, false)
      if (res.needs_confirm) {
        const w = (res.warnings || []).map(x => `${x.hand_id} (${x.tournament_format})`).join(', ')
        if (!window.confirm(`A tag "${tag}" contradiz o formato do torneio em: ${w}.\nAplicar mesmo assim?`)) return
        res = await ggHealth.tag(ids, tag, true)
      }
      setMsg(`${res.applied} mão(s) tagada(s) com "${tag}".`)
      setSelected(new Set())
      reload()
    } catch (e) { setMsg('Erro: ' + e.message) }
  }

  // Ação 2 — ligar órfã à mão (com confirmação).
  const linkOrphan = async (ssId, handId) => {
    if (!handId) return
    if (!window.confirm(`Ligar esta captura à mão ${handId}? (a Gold não é sobrescrita)`)) return
    try { await tableSs.link(ssId, handId); setMsg(`Ligada a ${handId}.`); reload() }
    catch (e) { setMsg('Erro: ' + e.message) }
  }

  // Fase 1-A — a suspeita resolve-se agora no SwapModal (escolher a dona certa).

  return (
    <div style={{ padding: 24, maxWidth: 1200 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
        <h1 style={{ fontSize: 20, margin: 0 }}>Saúde das mãos GG</h1>
        {sum && <span style={{ fontSize: 13, color: 'var(--muted)' }}>{sum.total_images} imagens · {sum.total_hands_with_image} mãos com imagem</span>}
      </div>
      {err && <div style={{ ...card, padding: 16, color: '#ef4444', marginTop: 12 }}>Erro: {err}</div>}

      {/* Pesquisa GLOBAL por nº de mão — salta para a mão em qualquer grupo. */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 14 }}>
        <input value={q} onChange={e => setQ(e.target.value)}
          placeholder="Procurar por nº de mão (ex. 6116735459)"
          style={{ width: 320, fontFamily: "'Fira Code',monospace", fontSize: 13, background: '#0b0d13', color: '#c9d1d9', border: '1px solid #30363d', borderRadius: 6, padding: '6px 10px' }} />
        {qt && <button style={btn} onClick={() => setQ('')}>✕ limpar</button>}
      </div>

      {qt && (
        <div style={{ marginTop: 12 }}>
          {loadingAll && !allImgs ? <div style={{ color: 'var(--muted)' }}>A procurar…</div> : (
            <>
              <div style={{ fontSize: 13, color: 'var(--muted)', margin: '4px 0 8px' }}>
                {(results || []).length} resultado(s) para “{qt}”
              </div>
              <div style={{ ...card, overflow: 'hidden' }}>
                {(results || []).map((im, i) => (
                  <Row key={i} im={im} group={null} onZoom={setZoom}
                    selected={selected} onToggleSel={() => {}}
                    onLink={() => {}} onResolve={setSwapResolve} />
                ))}
                {(results || []).length === 0 && <div style={{ padding: 16, color: 'var(--muted)' }}>Nenhuma imagem com esse número.</div>}
              </div>
            </>
          )}
        </div>
      )}

      {!qt && !group && sum && (
        <>
          <div style={{ fontSize: 12, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 0.5, margin: '20px 0 8px' }}>Precisa de ti</div>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {NEEDS.map(g => <Panel key={g.key} g={g} value={sum.needs_you[g.key]} onClick={() => open(g.key)} />)}
          </div>
          <div style={{ fontSize: 12, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 0.5, margin: '24px 0 8px' }}>Saudável</div>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {HEALTHY.map(g => <Panel key={g.key} g={g} value={sum.healthy[g.key]} onClick={() => open(g.key)} />)}
          </div>
        </>
      )}

      {!qt && group && (
        <div style={{ marginTop: 16 }}>
          <button onClick={() => setGroup(null)} style={{ background: 'none', border: 'none', color: '#818cf8', cursor: 'pointer', fontSize: 14, fontWeight: 600 }}>&larr; Dashboard</button>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, margin: '6px 0 12px' }}>
            <h2 style={{ fontSize: 16, margin: 0 }}>{LABELS[group]}</h2>
            {list && <span style={{ fontSize: 13, color: 'var(--muted)' }}>{list.total} imagens</span>}
          </div>

          {group === 'ft_quarantine' ? <FtQuarantinePanel /> :
           group === 'name_quarantine' ? <NamePropagationPanel /> : (<>
          {/* Ação 1 — barra de tags (só no grupo "Gold sem tag"). */}
          {group === 'gold_no_tag' && (
            <div style={{ ...card, padding: '10px 12px', marginBottom: 10 }}>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 6 }}>
                Selecionadas: <b>{selected.size}</b> — carrega numa tag para aplicar a todas:
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {CANONICAL_TAGS.map(t => (
                  <button key={t} style={{ ...btn, opacity: selected.size ? 1 : 0.4 }}
                    disabled={!selected.size} onClick={() => applyTag(t)}>{t}</button>
                ))}
              </div>
            </div>
          )}
          {msg && <div style={{ ...card, padding: '8px 12px', marginBottom: 10, fontSize: 13,
            color: /erro/i.test(msg) ? '#fca5a5' : '#93c5fd',
            borderColor: /erro/i.test(msg) ? '#ef4444' : 'var(--border,#30363d)' }}>{msg}</div>}

          {!list ? <div style={{ color: 'var(--muted)' }}>A carregar…</div> : (
            <>
              <div style={{ ...card, overflow: 'hidden' }}>
                {list.images.map((im, i) => (
                  <Row key={i} im={im} group={group} onZoom={setZoom}
                    selected={selected} onToggleSel={toggleSel}
                    onLink={linkOrphan} onResolve={setSwapResolve} />
                ))}
                {list.images.length === 0 && <div style={{ padding: 16, color: '#22c55e' }}>✓ Nenhuma imagem neste grupo.</div>}
              </div>
              {list.total > list.page_size && (
                <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginTop: 12 }}>
                  <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Anterior</button>
                  <span style={{ fontSize: 12, color: 'var(--muted)' }}>página {page} / {Math.ceil(list.total / list.page_size)}</span>
                  <button disabled={page >= Math.ceil(list.total / list.page_size)} onClick={() => setPage(p => p + 1)}>Seguinte →</button>
                </div>
              )}
            </>
          )}
          </>)}
        </div>
      )}

      <Lightbox src={zoom} onClose={() => setZoom(null)} />
      <SwapModal im={swapResolve} onClose={() => setSwapResolve(null)}
        onDone={() => { setSwapResolve(null); setMsg('Suspeita resolvida.'); reload() }} />
    </div>
  )
}
