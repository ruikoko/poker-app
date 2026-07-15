import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ggHealth, tableSs, captureTriage, suspicious, importHealth, absImageUrl } from '../api/client'
import ImportHealthPage from './ImportHealth'
import CaptureTriagePage from './CaptureTriage'
import SuspiciousHandsPage from './SuspiciousHands'
import LiveZeroCrownsPage from './LiveZeroCrowns'
import CrossingSamplePage from './CrossingSample'
import HandImage from '../components/HandImage'

// "Saúde Import" (casa única consolidada 11 Jul — desenho da antiga Saúde GG).
// Vista por IMAGEM + painéis migrados (Saúde Import, Marcadas/captura, Mãos
// suspeitas) + painel novo Coroas. Só GG. Ações: tagar, ligar órfã, resolver
// suspeitas, verificar coroas à vista.

const NEEDS = [
  { key: 'gold_no_tag', label: 'Gold sem tag', color: '#eab308' },
  { key: 'orphans', label: 'Órfãs (sem mão)', color: '#f59e0b' },
  { key: 'swap_suspects', label: 'Suspeitas de troca', color: '#f59e0b' },
  { key: 'tag_conflicts', label: 'Conflito de tags', color: '#ef4444' },
  { key: 'ft_quarantine', label: 'Fronteira FT (rever)', color: '#f59e0b' },
  { key: 'name_quarantine', label: 'Nomes em conflito', color: '#a78bfa' },
  { key: 'lobby_edition', label: 'Edições de lobby (Raiz 2)', color: '#38bdf8' },
  { key: 'golds_unread', label: 'Golds por ler', color: '#f59e0b' },
  // Migrados/novo (consolidação 11 Jul):
  { key: 'marcadas', label: 'Marcadas/captura', color: '#f59e0b' },
  { key: 'suspeitas', label: 'Mãos suspeitas', color: '#ef4444' },
  { key: 'coroas', label: 'Coroas (verificar)', color: '#eab308' },
  { key: 'live_zero', label: 'Vivo com coroa $0', color: '#ef4444' },
  { key: 'crossing_sample', label: 'Cruzamento — amostra', color: '#38bdf8' },
]
const HEALTHY = [
  { key: 'gold_matched', label: 'Gold que casou', color: '#22c55e' },
  { key: 'it_matched', label: 'IT desanon', color: '#22c55e' },
]
// Secção nova "Import & processamento" (← antiga página Saúde Import).
const IMPORTP = [
  { key: 'import', label: 'Saúde do Import', color: '#38bdf8' },
]
// Grupos migrados que renderizam uma página inteira (não a lista de imagens).
const MIGRATED = new Set(['import', 'marcadas', 'suspeitas', 'coroas', 'golds_unread', 'live_zero', 'crossing_sample'])
const LABELS = Object.fromEntries([...NEEDS, ...HEALTHY, ...IMPORTP].map(g => [g.key, g.label]))
// As 11 tags canónicas (Ação 1) — espelho de _TAG_BUTTONS no backend.
const CANONICAL_TAGS = ['icm', 'icm-pko', 'pos-pko', 'pos-nko', 'speed-racer',
  'icm-ft', 'icm-pko-ft', 'pos-pko-ft', 'pos-nko-ft', 'speed-racer-ft', 'nota']

// Soma defensiva das falhas/sem-match dos pipelines p/ o número do painel Import.
function sumImportIssues(r) {
  if (!r) return null
  const ps = Array.isArray(r.pipelines) ? r.pipelines
    : (r.pipelines && typeof r.pipelines === 'object') ? Object.values(r.pipelines) : []
  let t = 0
  for (const p of ps) t += (p?.fail || 0) + (p?.gg_sem_match || 0) + (p?.errors || 0)
  return t
}

const card = { background: 'var(--card,#161b22)', border: '1px solid var(--border,#30363d)', borderRadius: 8 }
const btn = { background: '#21262d', border: '1px solid #30363d', color: '#c9d1d9', borderRadius: 5, cursor: 'pointer', fontSize: 12, padding: '3px 8px' }
const mono = "'Fira Code',monospace"
const inp = { fontFamily: mono, fontSize: 12, background: '#0b0d13', color: '#c9d1d9', border: '1px solid #30363d', borderRadius: 5, padding: '3px 6px' }
// data/hora (ISO Lisboa-naive) → "MM-DD HH:MM"; formato PKO vs Vanilla (tudo o que
// não é Vanilla é bounty/PKO p/ o filtro binário).
const fmtDT = (iso) => iso ? String(iso).replace('T', ' ').slice(5, 16) : '—'
const isPKO = (fmt) => !!fmt && !/vanilla/i.test(fmt)
const isSpeedRacer = (name) => !!name && /speed\s*racer/i.test(name)

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

function imgSrc(im) { return absImageUrl(im.image_url) }

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
      {/* Metadados de triagem (só golds enriquecidos): torneio · data/hora · formato · anónima. */}
      {im.tournament_name != null && (
        <span style={{ display: 'flex', flexDirection: 'column', minWidth: 200, gap: 2 }}>
          <span style={{ fontSize: 11, color: '#cbd5e1', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 220 }}>{im.tournament_name || '—'}</span>
          <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <span style={{ fontSize: 10, color: '#64748b' }}>{fmtDT(im.played_at)}</span>
            {im.tournament_format && <span style={{ fontSize: 9, fontWeight: 700, padding: '1px 5px', borderRadius: 3, color: isPKO(im.tournament_format) ? '#fca5a5' : '#93c5fd', background: isPKO(im.tournament_format) ? 'rgba(239,68,68,0.12)' : 'rgba(59,130,246,0.12)' }}>{isPKO(im.tournament_format) ? 'PKO' : 'Vanilla'}</span>}
            {im.anon && <span style={{ fontSize: 9, fontWeight: 700, padding: '1px 5px', borderRadius: 3, color: '#fbbf24', background: 'rgba(245,158,11,0.12)' }}>mão anónima</span>}
          </span>
        </span>
      )}
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
            <HandImage url={data.capture.image_url} style={{ width: 300, alignSelf: 'flex-start' }} />
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
                  <img src={imgSrc(im)} alt="" loading="lazy"
                    onClick={() => onZoom(imgSrc(im))}
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
                <img key={i} src={imgSrc(im)} alt="" loading="lazy" title={im.hand_id}
                  onClick={() => onZoom(imgSrc(im))}
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
            <img key={i} src={imgSrc(im)} alt="" loading="lazy" title={im.hand_id || ''}
              onClick={() => onZoom(imgSrc(im))}
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
  const isHash = it.kind === 'name_2_hash'          // name_2_hash → lados são hashes
  const isMismatch = it.kind === 'strong_weak_mismatch'
  const sides = it.sides || []
  // No mismatch, o lado FORTE (com aparições 'strong') é o nome a confirmar.
  const strongSide = sides.find(s => (s.appearances || []).some(a => a.source === 'strong'))
  const strongName = strongSide?.name
  const re = it.reentry || {}
  // re-entrada exige o MESMO nick (conta única) e nunca co-presentes; nicks diferentes
  // (ex. OHmyBUDDHA) não são re-entrada → não oferece o verbo.
  const showReentry = isHash && re.applies && !re.co_present && re.same_nick
  return (
    <div style={{ ...card, padding: 12, marginBottom: 10 }}>
      <div style={{ fontSize: 13, marginBottom: 8 }}>
        Torneio <b>{it.tournament_number}</b> · {isHash
          ? <>o nome <b>{it.conflict_key}</b> está em <b>2 lugares</b>. <span style={{ color: 'var(--muted)' }}>Ou é um lugar errado (escolhe «É este»), ou é a MESMA pessoa por re-entrada.</span></>
          : isMismatch
            ? <>o hash <code>{it.conflict_key}</code> foi lido <b style={{ color: '#86efac' }}>FORTE como {strongName}</b> mas tem leituras <b style={{ color: '#fbbf24' }}>fracas divergentes</b>. <span style={{ color: 'var(--muted)' }}>Confirma o forte (limpa as fracas) ou dispensa.</span></>
            : <>o hash <code>{it.conflict_key}</code> foi lido com <b>nomes diferentes</b>. <span style={{ color: 'var(--muted)' }}>Confirma qual a leitura certa.</span></>}
      </div>
      {/* Sinal de re-entrada / veneno duro (co-presentes) + EVIDÊNCIA DURA */}
      {isHash && re.applies && (
        re.co_present
          ? <div style={{ fontSize: 12, color: '#fca5a5', marginBottom: 8 }}>⛔ os 2 hashes aparecem na MESMA mão → impossível ser 1 pessoa (veneno real).</div>
          : re.level === 'confirmed'
            ? <div style={{ fontSize: 12.5, color: '#86efac', marginBottom: 8, background: 'rgba(34,197,94,0.10)', border: '1px solid rgba(34,197,94,0.3)', borderRadius: 6, padding: '6px 10px' }}>
                ✓ <b>re-entrada confirmada</b> — <code>{re.bust?.hash}</code> bustou às <b>{(re.bust?.played_at || '').slice(11, 16)}</b> (all-in perdido{re.bust?.db_id ? <> · <Link to={`/hand/${re.bust.db_id}`} style={{ color: '#60a5fa' }}>{re.bust.hand_id}</Link></> : ''}), re-compra <b>+{Math.max(0, Math.round((re.gap_seconds || 0) / 60))}m</b> depois com bala fresca <b>{(re.rebuy?.stack ?? 0).toLocaleString()}</b> (arranque ~{(re.rebuy?.start_stack ?? 0).toLocaleString()}).
              </div>
            : re.likely_reentry
              ? <div style={{ fontSize: 12, color: '#a5b4fc', marginBottom: 8 }}>↻ provável <b>re-entrada</b>: mesmo nick, fortes dos 2 lados, janelas sem sobreposição{re.bust && !re.bust.lost ? ' — sem bust legível na app (fica provável)' : ''}. Confirma tu.</div>
              : <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>{re.same_nick ? 'mesmo nick' : 'nicks diferentes'}{re.disjoint_windows === false ? ' · janelas sobrepõem-se' : re.disjoint_windows ? ' · janelas disjuntas' : ''}{re.both_strong ? '' : ' · falta fonte forte num lado'}.</div>
      )}
      {sides.length > 0 ? (
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {sides.map((s, i) => (
            <SideColumn key={i} side={s} isHash={isHash} busy={busy} onZoom={onZoom} onAttach={onAttach}
              actionLabel={isHash ? 'É este' : (isMismatch && s.name === strongName) ? 'Confirmar (forte)' : 'É esta'}
              onAct={() => isHash ? onChoose(it, it.conflict_key, s.hash)
                : isMismatch ? onChoose(it, s.name, null)
                : onMerge(it, s.name)} />
          ))}
        </div>
      ) : (
        // fallback (backend antigo, sem `sides`): só os candidatos como botões
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
          {(it.candidates || []).map(c => (
            <button key={c} disabled={busy} style={btn}
              onClick={() => isHash ? onChoose(it, it.conflict_key, c) : isMismatch ? onChoose(it, c, null) : onMerge(it, c)}>
              {isHash ? <code>{c}</code> : c}</button>
          ))}
        </div>
      )}
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 10, flexWrap: 'wrap' }}>
        {showReentry && (
          <button disabled={busy} style={{ ...btn, borderColor: re.level === 'confirmed' ? '#22c55e' : re.likely_reentry ? '#22c55e' : '#818cf8', color: re.likely_reentry ? '#86efac' : '#a5b4fc', fontWeight: re.likely_reentry ? 700 : 500 }}
            onClick={() => onReentry(it)} title="Os 2 hashes são a mesma pessoa (re-entrada) — o nome fica válido nos dois">
            ↻ Mesma pessoa (re-entrada{re.level === 'confirmed' ? ' confirmada' : ''})</button>
        )}
        {isMismatch && strongName && (
          <button disabled={busy} style={{ ...btn, borderColor: '#22c55e', color: '#86efac', fontWeight: 700 }}
            onClick={() => onChoose(it, strongName, null)}
            title="Confirma o nome forte no hash → propaga e limpa as leituras fracas divergentes">
            ✓ Confirmar o forte ({strongName})</button>
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
  const [rotten, setRotten] = useState(null)   // capturas rotacionadas (≥3 conflitos)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  const [zoom, setZoom] = useState(null)

  const load = () => {
    ggHealth.namesQuarantine().then(r => setQuar(r.items || [])).catch(e => setMsg('Erro: ' + e.message))
    ggHealth.namesApply(null, true).then(setAgg).catch(() => {})   // dry-run agregado leve
    ggHealth.namesRotationScan().then(r => setRotten(r.rotten || [])).catch(() => {})
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
  // Rotação: 1 captura podre → 1 ação. Reverter à anónima + re-propagar (os N conflitos
  // caem sozinhos, o forte re-preenche do mapa correto). NÃO confirmar por hash.
  const onRevertRotten = wrap(async (hid) => {
    await tableSs.revertToAnon(hid)
    await ggHealth.namesApply()
    setMsg(`Captura rotacionada ${hid} revertida à anónima — conflitos re-propagados do mapa forte.`)
  })

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
      {/* Detetor de ROTAÇÃO — N conflitos = 1 captura podre. 1 ação (reverter), não N confirmações. */}
      {rotten && rotten.length > 0 && (
        <div style={{ ...card, padding: 12, marginBottom: 12, borderColor: '#b45309', background: 'rgba(180,83,9,0.08)' }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#fbbf24', marginBottom: 6 }}>
            ⟳ Rotação suspeita — {rotten.length} captura(s) podre(s)
          </div>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 10, maxWidth: 720 }}>
            Estes conflitos vêm de UMA captura cuja âncora <b>rodou a roda</b> (cada seat recebeu o nick do vizinho;
            os stacks desmentem-na). NÃO confirmes por hash — <b>reverte a captura podre</b> e o forte re-preenche do mapa correto.
          </div>
          {rotten.map((r, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', padding: '6px 0', borderTop: i ? '1px solid rgba(255,255,255,0.06)' : 'none' }}>
              <span style={{ fontFamily: mono, fontSize: 12, color: '#fca5a5', fontWeight: 700 }}>{r.hand_id}</span>
              <span style={{ fontSize: 11, color: 'var(--muted)' }}>tn {r.tournament_number} · mm={r.match_method} · <b style={{ color: '#fca5a5' }}>{r.n_conflicts}</b> hashes trocados</span>
              <span style={{ fontSize: 10, color: '#94a3b8', fontFamily: mono }}>
                {(r.conflicts || []).slice(0, 4).map(c => `${c.hash}: ${c.read}→${c.strong}`).join(' · ')}{r.conflicts.length > 4 ? ' …' : ''}
              </span>
              <button disabled={busy} style={{ ...btn, marginLeft: 'auto', background: '#b91c1c', color: '#fff', fontWeight: 700 }}
                onClick={() => onRevertRotten(r.hand_id)} title="Reverte a captura à anónima + re-propaga do mapa forte">
                Reverter captura podre
              </button>
            </div>
          ))}
        </div>
      )}
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

// RAIZ 2 (11 Jul) — resolver de EDIÇÕES GG: crivo (payout de edição errada) +
// quarentena (2+ edições sem prova) com decisão manual do Rui.
function LobbyEditionPanel() {
  const [scan, setScan] = useState(null)
  const [quar, setQuar] = useState(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)

  const load = () => {
    ggHealth.lobbyEditionScan().then(setScan).catch(e => setMsg('Erro crivo: ' + e.message))
    ggHealth.lobbyEditionQuarantine().then(r => setQuar(r.items || [])).catch(e => setMsg('Erro quarentena: ' + e.message))
  }
  useEffect(() => { load() }, [])

  const resolve = async (mid, tn, name) => {
    if (!window.confirm(`Colar este lobby à edição ${tn} (${name})?\nEscreve o payout (manual_edition) e marca success.`)) return
    setBusy(true); setMsg(null)
    try {
      const r = await ggHealth.lobbyEditionResolve(mid, tn, false)
      setMsg(`✓ Colado a ${tn} — payout ${r.payout_action || 'escrito'}.`); load()
    } catch (e) { setMsg('Erro: ' + e.message) } finally { setBusy(false) }
  }

  const contam = scan?.edition_contamination ?? null
  return (
    <div>
      {/* CRIVO — gate de contaminação de payout */}
      <div style={{ ...card, padding: 12, marginBottom: 12,
        borderLeft: `3px solid ${contam === 0 ? '#22c55e' : contam > 0 ? '#ef4444' : '#30363d'}` }}>
        <div style={{ fontSize: 13, marginBottom: 8 }}>
          <b>Crivo de edições</b> — varre cada payout GG escrito por um lobby e re-corre a prova
          de edição sobre o lobby que o escreveu. Contaminação = o ICM usou prémios da edição errada.
        </div>
        {!scan ? <div style={{ color: 'var(--muted)' }}>A correr crivo…</div> : (
          <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', fontSize: 13, alignItems: 'center' }}>
            <span style={{ fontSize: 26, fontWeight: 800, color: contam > 0 ? '#ef4444' : '#22c55e' }}>
              {contam > 0 ? `⚠ ${contam}` : '✓ 0'}
            </span>
            <span style={{ color: contam > 0 ? '#fca5a5' : '#22c55e' }}>
              {contam > 0 ? 'PARAR — payout de edição errada no ICM' : 'sem contaminação de payout'}
            </span>
            <span style={{ color: 'var(--muted)' }}>varridos {scan.scanned_lobby_payouts} · limpos {scan.counts?.clean} · suspeitos {scan.counts?.suspect}</span>
          </div>
        )}
        {scan?.contamination?.length > 0 && (
          <div style={{ marginTop: 8, fontSize: 12, fontFamily: mono }}>
            {scan.contamination.map((c, i) => (
              <div key={i} style={{ color: '#fca5a5' }}>
                payout {c.payout_tn} ({c.tournament_name}) → o escritor é da edição {c.new_tn}
              </div>
            ))}
          </div>
        )}
      </div>
      {msg && <div style={{ ...card, padding: '8px 12px', marginBottom: 10, fontSize: 13,
        color: /erro/i.test(msg) ? '#fca5a5' : '#93c5fd' }}>{msg}</div>}
      {/* QUARENTENA — decisão manual */}
      <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8 }}>
        Lobbys sem prova dura para separar 2+ edições do mesmo torneio/dia — o pipeline NÃO cola
        (branco é honesto). Decide a edição pela evidência:
      </div>
      {!quar ? <div style={{ color: 'var(--muted)' }}>A carregar…</div> :
        quar.length === 0 ? <div style={{ ...card, padding: 16, color: '#22c55e' }}>✓ Sem lobbys em quarentena de edição.</div> : (
          quar.map((it, i) => (
            <div key={i} style={{ ...card, padding: 12, marginBottom: 10 }}>
              <div style={{ fontSize: 13, marginBottom: 6 }}>
                <b>{it.tournament_name}</b>
                {it.now_resolvable_tn && <span style={{ color: '#22c55e', marginLeft: 8 }}>→ já resolúvel ({it.now_resolvable_tn}); o reconcile vai colá-la.</span>}
                <span style={{ color: 'var(--muted)', marginLeft: 8, fontFamily: mono, fontSize: 11 }}>
                  print {it.anchor_lisbon?.slice(11, 16)} · entrants {it.entrants ?? '—'} · left {it.players_left ?? '—'}
                </span>
              </div>
              {(it.candidates || []).map((c, j) => (
                <div key={j} style={{ display: 'flex', gap: 10, alignItems: 'center', fontSize: 12,
                  fontFamily: mono, padding: '4px 0', borderTop: j ? '1px solid #21262d' : 'none' }}>
                  <span style={{ minWidth: 90 }}>{c.tournament_number}</span>
                  <span style={{ color: 'var(--muted)' }}>
                    start {c.start_time?.slice(11, 16)} · campo {c.total_players ?? '—'}
                    · mãos {c.first_hand?.slice(11, 16) || '—'}–{c.last_hand?.slice(11, 16) || '—'}
                    · {c.started_at_capture ? 'a decorrer' : 'por arrancar'}
                  </span>
                  <button disabled={busy} style={{ ...btn, marginLeft: 'auto' }}
                    onClick={() => resolve(it.message_id, c.tournament_number, it.tournament_name)}>
                    Colar aqui
                  </button>
                </div>
              ))}
            </div>
          ))
        )}
    </div>
  )
}

// Painel COROAS (consolidação 11 Jul) — mãos GG PKO com coroa < base÷2, com a
// IMAGEM ao lado, para o Rui CONFIRMAR à vista (coroa real → salta a guarda) ou
// CORRIGIR o valor. `impossible` (valor >0 e <½ = chama-lida-como-coroa, vermelho)
// e `unread` (coroa a $0 = por ler, âmbar). Escreve via tableSs.setBounties.
function CrownHand({ h, onDone }) {
  const [edit, setEdit] = useState({})   // seatName -> novo valor
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  const confirmReal = async () => {
    setBusy(true); setMsg(null)
    try {
      await tableSs.setBounties(h.hand_id, { confirm: h.seats.map(s => s.name) })
      setMsg('Coroa(s) confirmada(s) como reais.'); onDone && onDone()
    } catch (e) { setMsg('Erro: ' + e.message) } finally { setBusy(false) }
  }
  const saveCorrections = async () => {
    const bounties = Object.fromEntries(Object.entries(edit)
      .filter(([, v]) => v !== '' && v != null).map(([k, v]) => [k, Number(v)]))
    if (!Object.keys(bounties).length) { setMsg('Escreve pelo menos um valor.'); return }
    setBusy(true); setMsg(null)
    try {
      await tableSs.setBounties(h.hand_id, { bounties })
      setMsg('Coroa(s) corrigida(s).'); onDone && onDone()
    } catch (e) { setMsg('Erro: ' + e.message) } finally { setBusy(false) }
  }
  const reread = async () => {
    setBusy(true); setMsg(null)
    try {
      const r = await ggHealth.crownsReread([h.hand_id])
      const res = (r.results || [])[0] || {}
      if (res.error) { setMsg('Vision: ' + res.error) }
      else { setMsg(`Re-lido (${res.n_changes || 0} alteração(ões)).`); onDone && onDone() }
    } catch (e) { setMsg('Erro: ' + e.message) } finally { setBusy(false) }
  }
  return (
    <div style={{ ...card, padding: 12, marginBottom: 10, display: 'flex', gap: 12 }}>
      <HandImage url={h.image_url} style={{ width: 260, maxWidth: '38%', alignSelf: 'flex-start' }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
          <Link to={`/hand/${h.id}`} style={{ fontFamily: mono, color: '#818cf8', fontSize: 13, fontWeight: 700 }}>{h.hand_id}</Link>
          {(() => {
            const src = h.crown_source
            const spec = src === 'table_ss' ? { t: 'origem: table-SS', c: '#38bdf8' }
              : src === 'gold' ? { t: 'origem: Gold', c: '#eab308' }
              : { t: 'origem: carry/reread', c: '#94a3b8' }
            return <span title={`imagem mostrada = a fonte do valor · match_method ${h.match_method || '?'}`}
              style={{ fontSize: 10.5, fontWeight: 700, padding: '2px 7px', borderRadius: 5, color: spec.c, border: `1px solid ${spec.c}55`, background: `${spec.c}18` }}>{spec.t}{h.has_both ? ' (SS+Gold)' : ''}</span>
          })()}
          <span style={{ fontSize: 12, color: 'var(--muted)' }}>{h.tournament_name} · {(h.played_at || '').slice(0, 16)} · {h.kind === 'high' ? `teto $${h.ceil}` : `piso $${h.floor}`}</span>
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, marginTop: 8 }}>
          <tbody>
            {h.seats.map((s, i) => (
              <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,.05)' }}>
                <td style={{ padding: '3px 6px' }}>{s.name}</td>
                <td style={{ padding: '3px 6px', color: h.kind === 'high' ? '#38bdf8' : '#ef4444', fontFamily: mono }}>
                  ${s.value ?? 0}
                  {h.kind === 'high' && s.reread !== undefined && (
                    <span style={{ color: 'var(--muted)', fontSize: 11 }}> vs re-leitura {s.reread == null ? 'NULL' : `$${s.reread}`}</span>
                  )}
                </td>
                <td style={{ padding: '3px 6px' }}>
                  <input type="number" step="1" placeholder="coroa real $" value={edit[s.name] ?? ''}
                    onChange={e => setEdit(x => ({ ...x, [s.name]: e.target.value }))}
                    style={{ ...inp, width: 90 }} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div style={{ display: 'flex', gap: 8, marginTop: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <button style={{ ...btn, borderColor: '#818cf8', color: '#818cf8' }} disabled={busy} onClick={reread}>↻ Re-ler (prompt novo)</button>
          <button style={{ ...btn, borderColor: '#22c55e', color: '#22c55e' }} disabled={busy} onClick={confirmReal}>✓ Coroa real (confirmar)</button>
          <button style={{ ...btn, borderColor: '#eab308', color: '#eab308' }} disabled={busy} onClick={saveCorrections}>Corrigir valor(es)</button>
          {msg && <span style={{ fontSize: 12, color: msg.startsWith('Erro') ? '#ef4444' : '#22c55e' }}>{msg}</span>}
        </div>
      </div>
    </div>
  )
}

function CoroasPanel() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  const [bulk, setBulk] = useState(null)   // {done,total,changed} durante o disparo
  const load = () => ggHealth.crowns().then(setData).catch(e => setErr(e.message))
  useEffect(() => { load() }, [])
  const rereadAll = async () => {
    const ids = [...(data.impossible || []), ...(data.unread || [])].map(h => h.hand_id)
    if (!ids.length) return
    if (!window.confirm(`Re-ler ${ids.length} mão(s) com o prompt novo e escrever as coroas corrigidas?`)) return
    setBulk({ done: 0, total: ids.length, changed: 0 })
    let changed = 0
    for (let i = 0; i < ids.length; i += 5) {          // lotes de 5
      const batch = ids.slice(i, i + 5)
      try {
        const r = await ggHealth.crownsReread(batch)
        changed += (r.results || []).reduce((a, x) => a + (x.n_changes || 0), 0)
      } catch { /* continua o lote seguinte */ }
      setBulk({ done: Math.min(i + 5, ids.length), total: ids.length, changed })
    }
    setBulk(b => ({ ...b, finished: true }))
    load()
  }
  if (err) return <div style={{ ...card, padding: 16, color: '#ef4444' }}>Erro: {err}</div>
  if (!data) return <div style={{ color: 'var(--muted)' }}>A carregar…</div>
  const Section = ({ title, color, hands, desc }) => (
    <div style={{ marginTop: 12 }}>
      <div style={{ fontSize: 13, fontWeight: 700, color }}>{title} ({hands.length})</div>
      <div style={{ fontSize: 12, color: 'var(--muted)', margin: '2px 0 8px' }}>{desc}</div>
      {hands.length === 0
        ? <div style={{ color: 'var(--muted)', fontSize: 12 }}>Nada aqui.</div>
        : hands.map(h => <CrownHand key={h.id} h={h} onDone={load} />)}
    </div>
  )
  return (
    <div>
      <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>
        Coroa = KO instantâneo = <b>metade</b> do bounty → nunca &lt; base÷2. Confirma à vista (real → salta a guarda), corrige, ou <b>re-lê com o prompt novo</b> (placa de $).
      </div>
      <div style={{ ...card, padding: '8px 12px', margin: '6px 0', display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <button style={{ ...btn, borderColor: '#818cf8', color: '#818cf8', fontWeight: 700 }}
          disabled={!!bulk && !bulk.finished} onClick={rereadAll}>
          ↻ Re-ler todas as {data.count} (prompt novo)
        </button>
        {bulk && (
          <span style={{ fontSize: 12, color: bulk.finished ? '#22c55e' : 'var(--muted)' }}>
            {bulk.finished ? `Concluído: ${bulk.done}/${bulk.total} re-lidas · ${bulk.changed} coroa(s) alterada(s).`
              : `A re-ler ${bulk.done}/${bulk.total}… (${bulk.changed} alteradas)`}
          </span>
        )}
        <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>
          Corre a Vision com o prompt corrigido sobre a imagem guardada e escreve as coroas certas (guarda base÷2).
        </span>
      </div>
      {data.by_source && (
        <div style={{ ...card, padding: '8px 12px', margin: '6px 0 4px', fontSize: 12, display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'center' }}>
          <b>Origem das {data.count}:</b>
          <span style={{ color: '#38bdf8' }}>table-SS <b>{data.by_source.table_ss}</b></span>
          <span style={{ color: '#eab308' }}>Gold <b>{data.by_source.gold}</b></span>
          <span style={{ color: '#94a3b8' }}>carry/reread <b>{data.by_source.other}</b></span>
          <span style={{ color: 'var(--muted)' }}>— a fresta está sobretudo no <b>Gold</b>; o prompt corrigido (pt95) só fecha o table-SS.</span>
        </div>
      )}
      <Section title="Valor impossível (provável chama)" color="#ef4444" hands={data.impossible}
        desc="Coroa >0 mas < base÷2 — a Vision leu a chama (VPIP %) em vez da coroa ($)." />
      <Section title="Coroa por ler ($0)" color="#eab308" hands={data.unread}
        desc="Coroa a $0 — não foi lida (avatar tapado). Rever/re-ler, não é valor errado." />
      {/* "Valor alto — confirmar" REMOVIDO (15 Jul): era o fantasma do gate >3× extinto
          (#CROWN-HIGH-IS-ACCUMULATION) — coroa alta = acumulação legítima, exporta sem
          confirmar. Pedia trabalho sem objeto. */}
    </div>
  )
}

// Painel "Golds por ler" — mãos com Gold ligada mas vision_done=false (a leitura
// nunca correu). Ler individual ("Ler agora") ou em lote ("Ler todas", com confirmação
// — a regra anti-massivo: o botão é do Rui, nada corre sozinho).
function GoldsUnreadPanel() {
  const [data, setData] = useState(null)
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(null)   // hand_id em curso, ou '__all__'
  const load = () => ggHealth.goldsUnread().then(setData).catch(e => setMsg('Erro: ' + e.message))
  useEffect(() => { load() }, [])
  const fmt = (iso) => iso ? String(iso).replace('T', ' ').slice(0, 16) : '—'

  const readOne = async (hid) => {
    setBusy(hid); setMsg('')
    try {
      const r = await ggHealth.goldVisionRun([hid])
      const x = (r.results || [])[0] || {}
      setMsg(x.mm === 'position_v3'
        ? `${hid}: leu ${x.n_names} nome(s) → ${x.mm}, hero=${x.hero}.`
        : `${hid}: sem nomes (${x.status || x.mm || 'alarme'}) — fica anónima.`)
      load()
    } catch (e) { setMsg('Erro: ' + e.message) } finally { setBusy(null) }
  }

  const readAll = async () => {
    const ids = (data?.hands || []).map(h => h.hand_id)
    if (!ids.length) return
    if (!window.confirm(`Ler TODAS as ${ids.length} Golds por ler? (${ids.length} chamadas Vision, uns minutos)`)) return
    setBusy('__all__'); setMsg('A ler…')
    let named = 0, done = 0
    try {
      for (let i = 0; i < ids.length; i += 10) {
        const r = await ggHealth.goldVisionRun(ids.slice(i, i + 10))
        for (const x of (r.results || [])) { done++; if (x.mm === 'position_v3') named++ }
        setMsg(`Lidas ${done}/${ids.length} · nomearam ${named}…`)
      }
      setMsg(`Concluído: ${named}/${done} nomearam. As restantes ficam anónimas honestas.`)
      load()
    } catch (e) { setMsg('Erro: ' + e.message) } finally { setBusy(null) }
  }

  if (!data) return <div style={{ color: 'var(--muted)' }}>A carregar…</div>
  const hands = data.hands || []
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap', marginBottom: 8 }}>
        <b style={{ fontSize: 15 }}>Golds por ler</b>
        <span style={{ fontSize: 13, color: 'var(--muted)' }}>{hands.length} mão(s) — a Gold existe mas a leitura nunca correu</span>
        <button style={{ ...btn, background: hands.length ? '#16a34a' : undefined, color: hands.length ? '#fff' : undefined, fontWeight: 700, opacity: hands.length ? 1 : 0.4 }}
          disabled={!hands.length || busy} onClick={readAll}>Ler todas ({hands.length})</button>
      </div>
      <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 10, maxWidth: 760 }}>
        A Vision destas Golds nunca correu (falhou/nunca disparou no funil de ingest, sem recuperação).
        Ler = extrai nomes + desanonimiza pela via premium (position_v3). As que não lerem ficam anónimas honestas.
      </div>
      {msg && <div style={{ ...card, padding: '8px 12px', marginBottom: 10, fontSize: 13 }}>{msg}</div>}
      <div style={{ ...card, overflow: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: 12 }}>
          <thead><tr>
            {['Mão', 'Data/hora', 'Torneio', 'SS?', 'Estado', ''].map(h =>
              <th key={h} style={{ textAlign: 'left', padding: '6px 8px', color: 'var(--muted)', borderBottom: '1px solid #30363d', whiteSpace: 'nowrap' }}>{h}</th>)}
          </tr></thead>
          <tbody>
            {hands.map(h => (
              <tr key={h.hand_id}>
                <td style={{ padding: '5px 8px', fontFamily: mono }}>
                  <Link to={`/hand/${h.id}`} style={{ color: '#60a5fa', textDecoration: 'none' }}>{h.hand_id}</Link>
                </td>
                <td style={{ padding: '5px 8px', whiteSpace: 'nowrap', color: 'var(--muted)' }}>{fmt(h.played_at)}</td>
                <td style={{ padding: '5px 8px' }}>{h.tournament_name || '—'}</td>
                <td style={{ padding: '5px 8px' }}>{h.has_ss ? '✓' : '—'}</td>
                <td style={{ padding: '5px 8px' }}>
                  {h.anon
                    ? <span style={{ color: '#f59e0b', fontWeight: 600 }}>mão anónima</span>
                    : <span style={{ color: '#22c55e' }}>já com nomes</span>}
                </td>
                <td style={{ padding: '5px 8px' }}>
                  <button style={{ ...btn }} disabled={busy} onClick={() => readOne(h.hand_id)}>
                    {busy === h.hand_id ? '…' : 'Ler agora'}
                  </button>
                </td>
              </tr>
            ))}
            {hands.length === 0 && <tr><td colSpan={6} style={{ padding: 16, color: '#22c55e' }}>✓ Nenhuma Gold por ler.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function GGHealth() {
  const [sum, setSum] = useState(null)
  const [extra, setExtra] = useState({})   // contagens dos painéis migrados/novo
  const [err, setErr] = useState(null)
  const [searchParams] = useSearchParams()
  // Deep-link do selo "nome em revisão" (OBRA 3): ?panel=name_quarantine abre o painel.
  const [group, setGroup] = useState(searchParams.get('panel') || null)
  const [list, setList] = useState(null)
  const [page, setPage] = useState(1)
  const [zoom, setZoom] = useState(null)
  const [selected, setSelected] = useState(new Set())   // Ação 1: hand_ids marcados
  const [selectedTags, setSelectedTags] = useState(new Set())  // Ação 1: tags em toggle (multi)
  const [gFilter, setGFilter] = useState({ fmt: 'all', sr: 'all', trn: 'all', date: 'all' })  // filtros do "Gold sem tag"
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
  // Contagens dos painéis migrados/novo (fetch à parte p/ o dashboard abrir rápido).
  const loadExtra = () => Promise.all([
    ggHealth.crowns().then(r => r.count).catch(() => null),
    captureTriage.count().then(r => (r.count ?? r.total ?? null)).catch(() => null),
    suspicious.count().then(r => r.total).catch(() => null),
    importHealth.get().then(sumImportIssues).catch(() => null),
    ggHealth.liveZeroList().then(r => r.count).catch(() => null),
  ]).then(([coroas, marcadas, suspeitas, imp, live_zero]) =>
    setExtra({ coroas, marcadas, suspeitas, import: imp, live_zero }))
  useEffect(() => { loadSummary(); loadExtra() }, [])
  useEffect(() => {
    if (!group || group === 'ft_quarantine' || group === 'name_quarantine' || group === 'lobby_edition' || MIGRATED.has(group)) { setList(null); return }
    setList(null)
    // gold_no_tag: carrega TUDO (page_size grande) → filtros + "selecionar todos os
    // filtrados" operam sobre o grupo inteiro, não só a página atual.
    ggHealth.list(group, page, group === 'gold_no_tag' ? 2000 : undefined).then(setList).catch(e => setErr(e.message))
  }, [group, page])

  const open = (k) => { setGroup(k); setPage(1); setSelected(new Set()); setSelectedTags(new Set()); setGFilter({ fmt: 'all', sr: 'all', trn: 'all', date: 'all' }); setMsg(null) }
  // Número do painel: summary (needs/healthy) → senão as contagens extra (migrados/coroas).
  const countOf = (k) => (sum?.needs_you?.[k] ?? sum?.healthy?.[k] ?? extra[k])
  const toggleTag = (t) => setSelectedTags(s => { const n = new Set(s); n.has(t) ? n.delete(t) : n.add(t); return n })
  const reload = () => {
    loadSummary()
    ggHealth.list(group, page, group === 'gold_no_tag' ? 2000 : undefined).then(setList).catch(e => setErr(e.message))
  }
  const toggleSel = (hid) => setSelected(s => {
    const n = new Set(s); n.has(hid) ? n.delete(hid) : n.add(hid); return n
  })

  // Ação 1 — aplicar TODAS as tags ligadas (toggle) às mãos selecionadas, de uma vez.
  // ACRESCENTA (nunca substitui). confirm=true força apesar do conflito de formato.
  const applyTags = async () => {
    const ids = [...selected]
    const tags = [...selectedTags]
    if (!ids.length) { setMsg('Seleciona pelo menos uma mão.'); return }
    if (!tags.length) { setMsg('Liga pelo menos uma tag.'); return }
    try {
      let res = await ggHealth.tag(ids, tags, false)
      if (res.needs_confirm) {
        const w = (res.warnings || []).map(x => `${x.hand_id}:${x.tag} (${x.tournament_format})`).join(', ')
        if (!window.confirm(`Tag(s) que contradizem o formato do torneio em: ${w}.\nAplicar mesmo assim?`)) return
        res = await ggHealth.tag(ids, tags, true)
      }
      setMsg(`${res.applied} etiqueta(s) aplicada(s) em ${res.hands ?? '?'} mão(s): ${tags.join(', ')}.`)
      setSelected(new Set()); setSelectedTags(new Set())
      reload()
    } catch (e) { setMsg('Erro: ' + e.message) }
  }

  // Ferramenta de edição — REMOVE as tags ligadas das mãos selecionadas (limpa
  // espúrias, ex. um SS mal casado deixou pos-pko numa vizinha). Oposto de Aplicar.
  const removeTags = async () => {
    const ids = [...selected]
    const tags = [...selectedTags]
    if (!ids.length) { setMsg('Seleciona pelo menos uma mão.'); return }
    if (!tags.length) { setMsg('Liga pelo menos uma tag para remover.'); return }
    if (!window.confirm(`Remover ${tags.join(', ')} de ${ids.length} mão(s)?`)) return
    try {
      const res = await ggHealth.untag(ids, tags)
      setMsg(`${res.removed} etiqueta(s) removida(s) de ${res.hands ?? '?'} mão(s): ${tags.join(', ')}.`)
      setSelected(new Set()); setSelectedTags(new Set())
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

  // Filtros do "Gold sem tag" (combináveis) — operam sobre o grupo inteiro (carregado
  // todo). As opções dos dropdowns saem das imagens presentes.
  const _goldImgs = list?.images || []
  const _matchG = (im) => {
    if (gFilter.fmt === 'pko' && !isPKO(im.tournament_format)) return false
    if (gFilter.fmt === 'vanilla' && isPKO(im.tournament_format)) return false
    if (gFilter.sr === 'yes' && !isSpeedRacer(im.tournament_name)) return false
    if (gFilter.sr === 'no' && isSpeedRacer(im.tournament_name)) return false
    if (gFilter.trn !== 'all' && im.tournament_name !== gFilter.trn) return false
    if (gFilter.date !== 'all' && (im.played_at || '').slice(0, 10) !== gFilter.date) return false
    return true
  }
  const gFiltered = group === 'gold_no_tag' ? _goldImgs.filter(_matchG) : _goldImgs
  const gTournaments = [...new Set(_goldImgs.map(im => im.tournament_name).filter(Boolean))].sort()
  const gDates = [...new Set(_goldImgs.map(im => (im.played_at || '').slice(0, 10)).filter(Boolean))].sort().reverse()
  const selectAllFiltered = () => setSelected(new Set(gFiltered.map(im => im.hand_id)))

  return (
    <div style={{ padding: 24, maxWidth: 1200 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
        <h1 style={{ fontSize: 20, margin: 0 }}>Saúde Import</h1>
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
            {NEEDS.map(g => <Panel key={g.key} g={g} value={countOf(g.key)} onClick={() => open(g.key)} />)}
          </div>
          <div style={{ fontSize: 12, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 0.5, margin: '24px 0 8px' }}>Saudável</div>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {HEALTHY.map(g => <Panel key={g.key} g={g} value={countOf(g.key)} onClick={() => open(g.key)} />)}
          </div>
          <div style={{ fontSize: 12, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 0.5, margin: '24px 0 8px' }}>Import &amp; processamento</div>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {IMPORTP.map(g => <Panel key={g.key} g={g} value={countOf(g.key)} onClick={() => open(g.key)} />)}
          </div>
        </>
      )}

      {!qt && group && (
        <div style={{ marginTop: 16 }}>
          <button onClick={() => setGroup(null)} style={{ background: 'none', border: 'none', color: '#818cf8', cursor: 'pointer', fontSize: 14, fontWeight: 600 }}>&larr; Dashboard</button>
          {/* Grupos migrados (import/marcadas/suspeitas) trazem o próprio título → sem h2 duplicado. */}
          {!MIGRATED.has(group) || group === 'coroas' ? (
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, margin: '6px 0 12px' }}>
            <h2 style={{ fontSize: 16, margin: 0 }}>{LABELS[group]}</h2>
            {list && <span style={{ fontSize: 13, color: 'var(--muted)' }}>{list.total} imagens</span>}
          </div>) : <div style={{ marginBottom: 6 }} />}

          {group === 'ft_quarantine' ? <FtQuarantinePanel /> :
           group === 'name_quarantine' ? <NamePropagationPanel /> :
           group === 'lobby_edition' ? <LobbyEditionPanel /> :
           group === 'import' ? <ImportHealthPage /> :
           group === 'marcadas' ? <CaptureTriagePage /> :
           group === 'suspeitas' ? <SuspiciousHandsPage /> :
           group === 'golds_unread' ? <GoldsUnreadPanel /> :
           group === 'live_zero' ? <LiveZeroCrownsPage /> :
           group === 'crossing_sample' ? <CrossingSamplePage /> :
           group === 'coroas' ? <CoroasPanel /> : (<>
          {/* Ação 1 — barra de tags (só no grupo "Gold sem tag"). */}
          {group === 'gold_no_tag' && (
            <div style={{ ...card, padding: '10px 12px', marginBottom: 10 }}>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 6 }}>
                <b>{selected.size}</b> mão(s) · <b>{selectedTags.size}</b> tag(s) — liga as tags (podes ligar várias, ex. <b>icm</b> + <b>nota</b>) e carrega em <b>Aplicar</b>. ACRESCENTA, nunca substitui.
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                {CANONICAL_TAGS.map(t => {
                  const on = selectedTags.has(t)
                  return (
                    <button key={t} onClick={() => toggleTag(t)}
                      style={{ ...btn, background: on ? '#2563eb' : undefined, color: on ? '#fff' : undefined,
                               borderColor: on ? '#2563eb' : undefined, fontWeight: on ? 700 : 400 }}>
                      {on ? '✓ ' : ''}{t}
                    </button>
                  )
                })}
                <button style={{ ...btn, marginLeft: 8, background: (selected.size && selectedTags.size) ? '#16a34a' : undefined,
                                 color: (selected.size && selectedTags.size) ? '#fff' : undefined, fontWeight: 700,
                                 opacity: (selected.size && selectedTags.size) ? 1 : 0.4 }}
                  disabled={!selected.size || !selectedTags.size} onClick={applyTags}>
                  Aplicar{selectedTags.size ? ` ${selectedTags.size} tag(s)` : ''}
                </button>
                <button style={{ ...btn, background: (selected.size && selectedTags.size) ? '#b91c1c' : undefined,
                                 color: (selected.size && selectedTags.size) ? '#fff' : undefined, fontWeight: 700,
                                 opacity: (selected.size && selectedTags.size) ? 1 : 0.4 }}
                  disabled={!selected.size || !selectedTags.size} onClick={removeTags}
                  title="Remove as tags ligadas das mãos selecionadas (limpa espúrias)">
                  Remover{selectedTags.size ? ` ${selectedTags.size} tag(s)` : ''}
                </button>
              </div>
            </div>
          )}
          {/* Filtros de triagem em lote (só "Gold sem tag") — combináveis, sobre o grupo todo. */}
          {group === 'gold_no_tag' && list && (
            <div style={{ ...card, padding: '8px 12px', marginBottom: 10, display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
              <span style={{ fontSize: 11, color: 'var(--muted)' }}>Filtros:</span>
              <select value={gFilter.fmt} onChange={e => setGFilter(f => ({ ...f, fmt: e.target.value }))} style={inp}>
                <option value="all">Formato: todos</option><option value="pko">PKO</option><option value="vanilla">Vanilla</option>
              </select>
              <select value={gFilter.sr} onChange={e => setGFilter(f => ({ ...f, sr: e.target.value }))} style={inp}>
                <option value="all">Speed Racer: todos</option><option value="yes">só Speed Racer</option><option value="no">sem Speed Racer</option>
              </select>
              <select value={gFilter.trn} onChange={e => setGFilter(f => ({ ...f, trn: e.target.value }))} style={{ ...inp, maxWidth: 260 }}>
                <option value="all">Torneio: todos</option>
                {gTournaments.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
              <select value={gFilter.date} onChange={e => setGFilter(f => ({ ...f, date: e.target.value }))} style={inp}>
                <option value="all">Data: todas</option>
                {gDates.map(d => <option key={d} value={d}>{d}</option>)}
              </select>
              <span style={{ fontSize: 11, color: '#93c5fd', fontWeight: 600 }}>{gFiltered.length} filtrada(s) · {selected.size} selec.</span>
              <button style={{ ...btn, background: gFiltered.length ? '#2563eb' : undefined, color: gFiltered.length ? '#fff' : undefined }}
                onClick={selectAllFiltered} disabled={!gFiltered.length}>Selecionar todos os filtrados</button>
              {selected.size > 0 && <button style={btn} onClick={() => setSelected(new Set())}>Limpar seleção</button>}
            </div>
          )}
          {msg && <div style={{ ...card, padding: '8px 12px', marginBottom: 10, fontSize: 13,
            color: /erro/i.test(msg) ? '#fca5a5' : '#93c5fd',
            borderColor: /erro/i.test(msg) ? '#ef4444' : 'var(--border,#30363d)' }}>{msg}</div>}

          {!list ? <div style={{ color: 'var(--muted)' }}>A carregar…</div> : (
            <>
              <div style={{ ...card, overflow: 'hidden' }}>
                {(group === 'gold_no_tag' ? gFiltered : list.images).map((im, i) => (
                  <Row key={im.hand_id || i} im={im} group={group} onZoom={setZoom}
                    selected={selected} onToggleSel={toggleSel}
                    onLink={linkOrphan} onResolve={setSwapResolve} />
                ))}
                {(group === 'gold_no_tag' ? gFiltered : list.images).length === 0 && <div style={{ padding: 16, color: '#22c55e' }}>✓ Nenhuma imagem neste grupo{group === 'gold_no_tag' ? ' (com estes filtros)' : ''}.</div>}
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
