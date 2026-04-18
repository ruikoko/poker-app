import { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react'
import { study } from '../api/client'

/**
 * Sessão contínua de estudo com suporte a pause/resume.
 *
 * Modelo (servidor):
 *  - Cada "macro-sessão" de estudo pode ser composta por várias sessões no backend.
 *  - Start            → POST /study/start  (abre sessão no servidor)
 *  - Pause            → POST /study/stop   (fecha sessão; duração real é registada)
 *  - Resume           → POST /study/start  (abre nova sessão com o handId actual)
 *  - Stop             → POST /study/stop   (fecha sessão; termina macro-sessão)
 *  - Mudar de handId  → fecha sessão + abre nova com novo handId
 *    (se estiver pausado, só actualiza o handId pendente; não abre nova sessão)
 *
 * Modelo (cliente/UI):
 *  - `elapsed`        = accumulatedSecs + (running ? now - startedAt : 0)
 *  - Badge mostra total da macro-sessão, mesmo com várias sessões por baixo.
 */

const Ctx = createContext(null)

export function StudyTimerProvider({ children }) {
  const [sessionId, setSessionId]           = useState(null)   // id da sessão aberta no servidor
  const [handId, setHandIdState]            = useState(null)   // hand_id actualmente associado
  const [startedAt, setStartedAt]           = useState(null)   // início do segmento actual
  const [accumulatedSecs, setAccumulated]   = useState(0)      // segundos acumulados de segmentos já fechados
  const [paused, setPaused]                 = useState(false)  // se true → há macro-sessão mas sem sessão aberta
  const [tick, setTick]                     = useState(0)
  const pendingRef = useRef(false)

  // Tick de 1s só quando há sessão a correr (não pausado)
  useEffect(() => {
    if (!sessionId || paused) return
    const t = setInterval(() => setTick(x => x + 1), 1000)
    return () => clearInterval(t)
  }, [sessionId, paused])

  // Start/troca de mão. Se estiver pausado, só actualiza o handId pendente
  // (fica pausado, a esperar pelo Resume).
  const setHandId = useCallback(async (newHandId) => {
    if (newHandId == null) return
    if (pendingRef.current) return

    // Pausado: só regista qual é a mão actual para o próximo Resume
    if (paused) {
      if (newHandId !== handId) setHandIdState(newHandId)
      return
    }

    // Já estamos a estudar esta mão
    if (sessionId && newHandId === handId) return

    pendingRef.current = true
    try {
      // Fecha sessão anterior (se havia) — o backend soma duration_s
      if (sessionId) {
        try {
          const r = await study.stop(sessionId)
          setAccumulated(a => a + (r?.duration_s || 0))
        } catch (_) {}
      }
      // Abre nova sessão com a mão nova
      const res = await study.start(newHandId)
      setSessionId(res.session_id)
      setHandIdState(res.hand_id)
      setStartedAt(new Date(res.started_at || Date.now()))
      setPaused(false)
    } catch (e) {
      setSessionId(null); setStartedAt(null)
      console.warn('study.setHandId failed:', e)
    } finally {
      pendingRef.current = false
    }
  }, [sessionId, handId, paused])

  const pause = useCallback(async () => {
    if (!sessionId || paused || pendingRef.current) return
    pendingRef.current = true
    const id = sessionId
    // Congela o segmento actual de imediato (UI fica responsiva)
    const now = Date.now()
    const segSecs = startedAt ? Math.max(0, Math.floor((now - startedAt.getTime()) / 1000)) : 0
    setAccumulated(a => a + segSecs)
    setSessionId(null)
    setStartedAt(null)
    setPaused(true)
    try {
      await study.stop(id)   // servidor regista a duração real
    } catch (e) {
      console.warn('study.pause failed:', e)
    } finally {
      pendingRef.current = false
    }
  }, [sessionId, paused, startedAt])

  const resume = useCallback(async () => {
    if (!paused || pendingRef.current) return
    if (handId == null) { setPaused(false); return }
    pendingRef.current = true
    try {
      const res = await study.start(handId)
      setSessionId(res.session_id)
      setHandIdState(res.hand_id)
      setStartedAt(new Date(res.started_at || Date.now()))
      setPaused(false)
    } catch (e) {
      console.warn('study.resume failed:', e)
    } finally {
      pendingRef.current = false
    }
  }, [paused, handId])

  const stop = useCallback(async () => {
    if (pendingRef.current) return
    pendingRef.current = true
    const id = sessionId
    // Reset de UI imediato
    setSessionId(null); setHandIdState(null); setStartedAt(null)
    setAccumulated(0); setPaused(false)
    if (id) {
      try { await study.stop(id) } catch (e) { console.warn('study.stop failed:', e) }
    }
    pendingRef.current = false
  }, [sessionId])

  // Segundos do segmento actual (se estiver a correr)
  const runningSecs = (sessionId && startedAt && !paused)
    ? Math.max(0, Math.floor((Date.now() - startedAt.getTime()) / 1000))
    : 0
  const elapsed = accumulatedSecs + runningSecs
  void tick

  const active = !!sessionId || paused

  const value = {
    sessionId, handId, startedAt, elapsed,
    active, paused,
    setHandId, pause, resume, stop,
  }
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useStudyTimer() {
  const v = useContext(Ctx)
  if (!v) throw new Error('useStudyTimer must be used inside StudyTimerProvider')
  return v
}

/**
 * Hook de conveniência: liga handId do useParams ao timer.
 * Chamar no topo de páginas de detalhe de mão / replayer.
 */
export function useStudyHand(handId) {
  const { setHandId } = useStudyTimer()
  useEffect(() => {
    if (handId != null) setHandId(Number(handId))
  }, [handId, setHandId])
}
