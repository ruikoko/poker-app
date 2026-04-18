import { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react'
import { study } from '../api/client'

/**
 * Sessão de estudo controlada MANUALMENTE pelo utilizador.
 *
 * Modelo simples:
 *  - start()  → abre sessão no servidor (sem hand_id associado)
 *  - pause()  → fecha sessão, tempo congela, paused=true
 *  - resume() → abre nova sessão, continua a somar
 *  - stop()   → termina, reset total
 *  - Navegação entre páginas NÃO afecta a sessão.
 */

const Ctx = createContext(null)

export function StudyTimerProvider({ children }) {
  const [sessionId, setSessionId]         = useState(null)
  const [startedAt, setStartedAt]         = useState(null)
  const [accumulatedSecs, setAccumulated] = useState(0)
  const [paused, setPaused]               = useState(false)
  const [tick, setTick]                   = useState(0)
  const pendingRef = useRef(false)

  useEffect(() => {
    if (!sessionId || paused) return
    const t = setInterval(() => setTick(x => x + 1), 1000)
    return () => clearInterval(t)
  }, [sessionId, paused])

  const start = useCallback(async () => {
    if (pendingRef.current || sessionId) return
    pendingRef.current = true
    try {
      const res = await study.start(null)
      setSessionId(res.session_id)
      setStartedAt(new Date(res.started_at || Date.now()))
      setAccumulated(0)
      setPaused(false)
    } catch (e) {
      console.warn('study.start failed:', e)
    } finally {
      pendingRef.current = false
    }
  }, [sessionId])

  const pause = useCallback(async () => {
    if (!sessionId || paused || pendingRef.current) return
    pendingRef.current = true
    const id = sessionId
    const now = Date.now()
    const segSecs = startedAt ? Math.max(0, Math.floor((now - startedAt.getTime()) / 1000)) : 0
    setAccumulated(a => a + segSecs)
    setSessionId(null)
    setStartedAt(null)
    setPaused(true)
    try {
      await study.stop(id)
    } catch (e) {
      console.warn('study.pause failed:', e)
    } finally {
      pendingRef.current = false
    }
  }, [sessionId, paused, startedAt])

  const resume = useCallback(async () => {
    if (!paused || pendingRef.current) return
    pendingRef.current = true
    try {
      const res = await study.start(null)
      setSessionId(res.session_id)
      setStartedAt(new Date(res.started_at || Date.now()))
      setPaused(false)
    } catch (e) {
      console.warn('study.resume failed:', e)
    } finally {
      pendingRef.current = false
    }
  }, [paused])

  const stop = useCallback(async () => {
    if (pendingRef.current) return
    pendingRef.current = true
    const id = sessionId
    setSessionId(null); setStartedAt(null); setAccumulated(0); setPaused(false)
    if (id) {
      try { await study.stop(id) } catch (e) { console.warn('study.stop failed:', e) }
    }
    pendingRef.current = false
  }, [sessionId])

  const runningSecs = (sessionId && startedAt && !paused)
    ? Math.max(0, Math.floor((Date.now() - startedAt.getTime()) / 1000))
    : 0
  const elapsed = accumulatedSecs + runningSecs
  void tick

  const active = !!sessionId || paused

  const value = { active, paused, elapsed, start, pause, resume, stop }
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useStudyTimer() {
  const v = useContext(Ctx)
  if (!v) throw new Error('useStudyTimer must be used inside StudyTimerProvider')
  return v
}
