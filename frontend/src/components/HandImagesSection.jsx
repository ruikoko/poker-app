import { useState, useEffect } from 'react'
import { hands as handsApi, screenshots, captureTriage } from '../api/client'
import { dateTimeLisbon } from '../utils/datetime'

/**
 * Secções de IMAGENS DA MÃO (regra 9 Jul): qualquer mão GG com imagem anexada
 * mostra-a, UMA SECÇÃO POR TIPO. Fonte: GET /api/hands/<id>/images (espelho
 * per-mão do _ft_images).
 *
 *   - Gold / replayer  → imagem guardada na entry da mão (desanon Gold / replayer
 *                        Discord). Servida por screenshots.imageUrl(entry_id).
 *   - SS do IT (table-SS) → captura de mesa do Intuitive Tables ligada/casada.
 *                        Servida por captureTriage.imageUrl(ss_id).
 *   - Lobby            → a IMAGEM do lobby NÃO é guardada; mostra-se só a LEITURA
 *                        (hora + players_left + aba) com nota.
 *
 * Só GG (as outras salas não têm este mecanismo de captura/desanon).
 */
export default function HandImagesSection({ hand }) {
  const [imgs, setImgs] = useState(null)
  const [err, setErr] = useState('')
  const [zoom, setZoom] = useState(null)  // src da imagem ampliada

  useEffect(() => {
    if (!hand?.id || hand.site !== 'GGPoker') { setImgs(null); return }
    setImgs(null); setErr('')
    handsApi.images(hand.id).then(setImgs).catch(e => setErr(e.message))
  }, [hand?.id, hand?.site])

  if (hand?.site !== 'GGPoker') return null

  const gold = imgs?.gold || []
  const tableSs = imgs?.table_ss || []
  const lobby = imgs?.lobby || []
  const total = gold.length + tableSs.length + lobby.length

  const thumb = (src, key, caption) => (
    <div key={key} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <img
        src={src}
        alt={caption || 'imagem'}
        onClick={() => setZoom(src)}
        style={{ width: '100%', maxWidth: 420, borderRadius: 6, border: '1px solid #2a2d3a', display: 'block', cursor: 'zoom-in' }}
      />
      {caption && <div style={{ fontSize: 12, color: '#64748b' }}>{caption}</div>}
    </div>
  )

  const subTitle = (txt) => (
    <div style={{ fontSize: 12, color: '#94a3b8', fontWeight: 700, margin: '4px 0 8px' }}>{txt}</div>
  )

  return (
    <div style={{ background: '#0f1117', borderRadius: 8, padding: 16, marginTop: 14 }}>
      <div style={{ fontSize: 13, color: '#94a3b8', fontWeight: 700, marginBottom: 10 }}>
        🖼️ IMAGENS DA MÃO{imgs ? ` (${total})` : ''}
      </div>

      {err && <div style={{ fontSize: 13, color: '#ef4444' }}>Erro a carregar imagens: {err}</div>}
      {!imgs && !err && <div style={{ fontSize: 13, color: '#64748b' }}>A carregar imagens…</div>}

      {imgs && total === 0 && (
        <div style={{ fontSize: 13, color: '#eab308' }}>Sem imagens ligadas a esta mão.</div>
      )}

      {/* GOLD / REPLAYER */}
      {gold.length > 0 && (
        <div style={{ marginBottom: tableSs.length || lobby.length ? 16 : 0 }}>
          {subTitle('👑 GOLD / REPLAYER')}
          <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
            {gold.map(g => thumb(screenshots.imageUrl(g.entry_id), `g${g.entry_id}`,
              `entry #${g.entry_id}${g.kind === 'replayer_link' ? ' · replayer' : ' · gold'}`))}
          </div>
        </div>
      )}

      {/* SS DO IT (table-SS) */}
      {tableSs.length > 0 && (
        <div style={{ marginBottom: lobby.length ? 16 : 0 }}>
          {subTitle('📷 SS DO IT (TABLE-SS)')}
          <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
            {tableSs.map(t => {
              const when = dateTimeLisbon(t.captured_at, { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
              const cap = [`captura #${t.ss_id}`, when || null,
                t.players_left != null ? `${t.players_left} restantes` : null].filter(Boolean).join(' · ')
              return thumb(captureTriage.imageUrl(t.ss_id), `t${t.ss_id}`, cap)
            })}
          </div>
        </div>
      )}

      {/* LOBBY — imagem não guardada, só a leitura */}
      {lobby.length > 0 && (
        <div>
          {subTitle('🏦 LOBBY (leitura — imagem não guardada)')}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {lobby.map((l, i) => {
              const when = dateTimeLisbon(l.posted_at, { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
              const parts = [
                when || '—',
                l.players_left != null ? `${l.players_left} restantes` : null,
                l.open_tab ? `aba ${l.open_tab}` : null,
                l.final_table_size != null ? `FT=${l.final_table_size}` : null,
              ].filter(Boolean)
              return (
                <div key={i} style={{ fontSize: 13, color: '#cbd5e1', background: '#12141c', borderRadius: 6, padding: '8px 12px' }}>
                  {parts.join(' · ')} <span style={{ color: '#64748b', fontStyle: 'italic' }}>· imagem não guardada</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Lightbox partilhado */}
      {zoom && (
        <div
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.92)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000, cursor: 'pointer' }}
          onClick={() => setZoom(null)}
        >
          <img src={zoom} alt="imagem" style={{ maxWidth: '95vw', maxHeight: '95vh', borderRadius: 8 }} onClick={e => e.stopPropagation()} />
          <button
            onClick={() => setZoom(null)}
            style={{ position: 'absolute', top: 20, right: 20, background: 'rgba(255,255,255,0.1)', border: 'none', color: '#fff', fontSize: 24, cursor: 'pointer', borderRadius: 8, padding: '4px 12px' }}
          >✕</button>
        </div>
      )}
    </div>
  )
}
