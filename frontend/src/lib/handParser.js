/**
 * ╔═══════════════════════════════════════════════════════════════════════╗
 * ║  Parser unificado de Hand Histories                                    ║
 * ║  Fonte única de verdade para: steps, pot, stacks, name mapping         ║
 * ║  Consumidores: ReplayerPage.jsx, Replayer.jsx, HandDetailPage.jsx      ║
 * ╚═══════════════════════════════════════════════════════════════════════╝
 *
 * Input:
 *   - raw: string HH original (do campo hands.raw)
 *   - apa: all_players_actions da BD (já tem _meta, seats, stack_bb, etc.)
 *
 * Output:
 *   {
 *     steps:    [{ street, label, action, actor, actorIdx, isHero, pot, potBB, board, ps, analysis, villainAnalysis }]
 *     heroIdx:  number  (-1 se não encontrado)
 *     players:  [{ name, position, stack, stack_bb, seat, is_hero, ... }]
 *     meta:     { bb, sb, ante, level, num_players, ... }
 *   }
 *
 * Suporta HH de: Winamax, PokerStars, WPN, GGPoker
 */

import { HERO_NAMES } from '../heroNames'

const SEAT_ORDER = ['UTG','UTG1','UTG+1','UTG2','UTG+2','MP','MP1','MP+1','HJ','CO','BTN','SB','BB']

// ─── Extract blind sizes from raw HH when _meta is missing/wrong ─────────────
// Formatos suportados:
//   GG:       "Level5(125/250(35))"           → bb=250, sb=125, ante=35
//   GG alt:   "Level5(125/250)"                → bb=250, sb=125
//   WN/PS:    "Level XXII (20000/40000)"      → bb=40000, sb=20000
//   WN/PS alt: "(20000/40000) - NL Holdem..."  → bb=40000
export function parseBlindsFromRaw(raw) {
  if (!raw) return { bb: 0, sb: 0, ante: 0, level: null }

  // Tenta formato GG com ante: Level5(125/250(35))
  const mGGAnte = raw.match(/Level\s*(\d+)\s*\(\s*(\d+)\s*\/\s*(\d+)\s*\(\s*(\d+)\s*\)\s*\)/i)
  if (mGGAnte) {
    return {
      level: parseInt(mGGAnte[1], 10),
      sb: parseInt(mGGAnte[2], 10),
      bb: parseInt(mGGAnte[3], 10),
      ante: parseInt(mGGAnte[4], 10),
    }
  }

  // Tenta formato GG sem ante: Level5(125/250)
  const mGG = raw.match(/Level\s*(\d+)\s*\(\s*(\d+)\s*\/\s*(\d+)\s*\)/i)
  if (mGG) {
    return {
      level: parseInt(mGG[1], 10),
      sb: parseInt(mGG[2], 10),
      bb: parseInt(mGG[3], 10),
      ante: 0,
    }
  }

  // Fallback genérico: qualquer (X/Y)
  const mGen = raw.match(/\(\s*(\d+)\s*\/\s*(\d+)\s*\)/)
  if (mGen) {
    return {
      level: null,
      sb: parseInt(mGen[1], 10),
      bb: parseInt(mGen[2], 10),
      ante: 0,
    }
  }

  return { bb: 0, sb: 0, ante: 0, level: null }
}

// ─── Parse principal ─────────────────────────────────────────────────────────
export function parseHH(raw, apa) {
  if (!raw) return { steps: [], heroIdx: -1, players: [], meta: {} }

  const metaRaw = apa?._meta || {}

  // Resolver bb: primeiro meta, depois fallback do raw
  let bb = metaRaw.bb || 0
  let sb = metaRaw.sb || 0
  let ante = metaRaw.ante || 0
  let level = metaRaw.level ?? null
  if (!bb) {
    const parsed = parseBlindsFromRaw(raw)
    bb = parsed.bb || 1  // último recurso para não dividir por zero
    sb = sb || parsed.sb
    ante = ante || parsed.ante
    if (level == null) level = parsed.level
  }
  const meta = {
    ...metaRaw,
    bb, sb, ante, level,
    num_players: metaRaw.num_players ?? 0,
  }

  const players = Object.entries(apa || {})
    .filter(([k]) => k !== '_meta')
    .map(([name, info]) => ({ name, ...info }))
    .sort((a, b) => {
      const ai = SEAT_ORDER.indexOf(a.position) === -1 ? 99 : SEAT_ORDER.indexOf(a.position)
      const bi = SEAT_ORDER.indexOf(b.position) === -1 ? 99 : SEAT_ORDER.indexOf(b.position)
      return ai - bi
    })

  const heroIdx = players.findIndex(p => p.is_hero || HERO_NAMES.has(p.name.toLowerCase()))

  // ── Build nameMap: anon hash → real name (GG specific) ───────────────────
  const nameMap = {}
  const seatLines = raw.match(/Seat \d+: .+? \([\d,]+(?:\.\d+)?(?:\s+in chips)?\)/g) || []
  for (const line of seatLines) {
    const sm = line.match(/Seat (\d+): (.+?) \(/)
    if (sm) {
      const seatNum = parseInt(sm[1])
      const anonName = sm[2].trim()
      for (const p of players) {
        if (p.seat === seatNum && p.name !== anonName) {
          nameMap[anonName] = p.name
          break
        }
      }
    }
  }
  const resolve = (n) => nameMap[n] || n

  // ── Initialize player state ──────────────────────────────────────────────
  const pState = players.map(p => ({
    name: p.name,
    position: p.position,
    startStack: p.stack || 0,
    stack: p.stack || 0,
    stackBB: p.stack_bb != null ? p.stack_bb : (bb > 1 ? +((p.stack || 0) / bb).toFixed(1) : 0),
    bounty: p.bounty,
    isHero: p.is_hero || HERO_NAMES.has(p.name.toLowerCase()),
    cards: [],
    folded: false,
    currentBet: 0,
    totalInvested: 0,
    actionLabel: '',
  }))

  const findPlayer = (rawName) => {
    const realName = resolve(rawName)
    return pState.findIndex(p => p.name === realName)
  }

  // ── Hero cards ───────────────────────────────────────────────────────────
  const dm = raw.match(/Dealt to (\S+)\s+\[(.+?)\]/)
  if (dm && heroIdx >= 0) pState[heroIdx].cards = dm[2].split(' ')

  // ── Board detection ──────────────────────────────────────────────────────
  const isW = raw.includes('*** PRE-FLOP ***')
  const pfm = isW ? '*** PRE-FLOP ***' : '*** HOLE CARDS ***'
  const bc = []
  const fm = raw.match(/\*\*\* FLOP \*\*\* \[(.+?)\]/); if (fm) bc.push(...fm[1].split(' '))
  const tmW = raw.match(/\*\*\* TURN \*\*\* \[.+?\]\s*\[(.+?)\]/); if (tmW) bc.push(...tmW[1].split(' '))
  const rmW = raw.match(/\*\*\* RIVER \*\*\* \[.+?\]\s*\[(.+?)\]/); if (rmW) bc.push(...rmW[1].split(' '))

  // ── Process antes and blinds ─────────────────────────────────────────────
  let pot = 0
  const anteMatches = [...raw.matchAll(/(.+?)(?::)?\s+posts\s+(?:the\s+)?ante\s+([\d,]+(?:\.\d+)?)/gi)]
  for (const am of anteMatches) {
    const name = am[1].trim()
    const amount = parseFloat(am[2].replace(/,/g, ''))
    pot += amount
    const pi = findPlayer(name)
    if (pi >= 0) {
      pState[pi].stack -= amount
      pState[pi].stackBB = +(pState[pi].stack / bb).toFixed(1)
    }
  }
  const sbMatch = raw.match(/(.+?)(?::)?\s+posts\s+(?:the\s+)?small blind\s+([\d,]+(?:\.\d+)?)/i)
  if (sbMatch) {
    const name = sbMatch[1].trim()
    const amount = parseFloat(sbMatch[2].replace(/,/g, ''))
    pot += amount
    const pi = findPlayer(name)
    if (pi >= 0) {
      pState[pi].stack -= amount
      pState[pi].stackBB = +(pState[pi].stack / bb).toFixed(1)
      pState[pi].totalInvested = amount
      pState[pi].currentBet = amount
    }
  }
  const bbMatch = raw.match(/(.+?)(?::)?\s+posts\s+(?:the\s+)?big blind\s+([\d,]+(?:\.\d+)?)/i)
  if (bbMatch) {
    const name = bbMatch[1].trim()
    const amount = parseFloat(bbMatch[2].replace(/,/g, ''))
    pot += amount
    const pi = findPlayer(name)
    if (pi >= 0) {
      pState[pi].stack -= amount
      pState[pi].stackBB = +(pState[pi].stack / bb).toFixed(1)
      pState[pi].totalInvested = amount
      pState[pi].currentBet = amount
    }
  }

  const snap = () => pState.map(p => ({ ...p }))
  const steps = [{
    street: 'preflop', label: 'Pre-Flop', action: 'Blinds posted',
    actor: null, actorIdx: -1, isHero: false,
    pot, potBB: +(pot / bb).toFixed(1),
    board: [], ps: snap(),
    analysis: null, villainAnalysis: null,
  }]

  // ── Process each street ──────────────────────────────────────────────────
  const sds = [
    { key: 'preflop', label: 'Pre-Flop', start: pfm, end: '*** FLOP ***' },
    { key: 'flop', label: 'Flop', start: '*** FLOP ***', end: '*** TURN ***' },
    { key: 'turn', label: 'Turn', start: '*** TURN ***', end: '*** RIVER ***' },
    { key: 'river', label: 'River', start: '*** RIVER ***', end: '*** SHOW' },
  ]

  for (const sd of sds) {
    const si = raw.indexOf(sd.start); if (si === -1) continue
    let ei = raw.indexOf(sd.end, si + sd.start.length)
    if (ei === -1) ei = raw.indexOf('*** SUMMARY ***', si)
    if (ei === -1) ei = raw.length
    const section = raw.slice(si, ei)
    const curBoard = sd.key === 'preflop' ? [] : sd.key === 'flop' ? bc.slice(0, 3) : sd.key === 'turn' ? bc.slice(0, 4) : bc.slice(0, 5)

    if (sd.key !== 'preflop' && curBoard.length > 0) {
      // New street: reset bets and totalInvested
      pState.forEach(p => { p.currentBet = 0; p.totalInvested = 0; p.actionLabel = '' })
      steps.push({
        street: sd.key, label: sd.label, action: `${sd.label} dealt`,
        actor: null, actorIdx: -1, isHero: false,
        pot, potBB: +(pot / bb).toFixed(1),
        board: [...curBoard], ps: snap(),
        analysis: null, villainAnalysis: null,
      })
    }

    for (const line of section.split('\n')) {
      const t = line.trim()
      if (!t || t.startsWith('***') || t.startsWith('Dealt') || t.startsWith('Main pot') || t.includes('posts')) continue

      // Showdown cards
      const showM = t.match(/^(.+?)(?::)?\s+shows\s+\[(.+?)\]/i)
      if (showM) {
        const pi = findPlayer(showM[1].trim())
        if (pi >= 0) pState[pi].cards = showM[2].split(' ')
        continue
      }

      // Uncalled bet returned
      const uncalledM = t.match(/Uncalled bet \(([\d,]+(?:\.\d+)?)\) returned to (.+)/i)
      if (uncalledM) {
        const amount = parseFloat(uncalledM[1].replace(/,/g, ''))
        const name = uncalledM[2].trim()
        const pi = findPlayer(name)
        pot -= amount
        if (pi >= 0) {
          pState[pi].stack += amount
          pState[pi].stackBB = +(pState[pi].stack / bb).toFixed(1)
          pState[pi].currentBet -= amount
        }
        continue
      }

      // Collected pot
      const collM = t.match(/^(.+?) collected ([\d,]+(?:\.\d+)?)/i)
      if (collM) {
        const name = collM[1].trim()
        const amount = parseFloat(collM[2].replace(/,/g, ''))
        const pi = findPlayer(name)
        if (pi >= 0) {
          pState[pi].stack += amount
          pState[pi].stackBB = +(pState[pi].stack / bb).toFixed(1)
        }
        continue
      }

      // Main action: folds, checks, calls, bets, raises
      const m = t.match(/^(.+?)(?::)?\s+(folds|checks|calls|bets|raises)(.*)$/i)
      if (!m) continue

      const actor = m[1].trim()
      const action = m[2].toLowerCase()
      const rest = m[3]
      let amount = 0
      const amtM = rest.match(/([\d,]+(?:\.\d+)?)/)
      if (amtM) amount = parseFloat(amtM[1].replace(/,/g, ''))
      const allIn = /all-in/i.test(rest)
      const toM = rest.match(/to\s+([\d,]+(?:\.\d+)?)/)
      const pi = findPlayer(actor)
      const isH = pi >= 0 && pState[pi].isHero

      let actionLabel = ''
      if (action === 'folds') {
        if (pi >= 0) { pState[pi].folded = true; pState[pi].currentBet = 0; pState[pi].actionLabel = '' }
        actionLabel = 'Fold'
      } else if (action === 'checks') {
        if (pi >= 0) { pState[pi].actionLabel = '' }
        actionLabel = 'Check'
      } else if (action === 'calls') {
        const callAmount = amount
        pot += callAmount
        if (pi >= 0) {
          pState[pi].stack -= callAmount
          pState[pi].stackBB = +(pState[pi].stack / bb).toFixed(1)
          pState[pi].totalInvested += callAmount
          pState[pi].currentBet = pState[pi].totalInvested
          pState[pi].actionLabel = `Call ${(callAmount / bb).toFixed(1)}bb`
        }
        actionLabel = `calls ${Math.round(callAmount).toLocaleString()}${allIn ? ' (all-in)' : ''}`
      } else if (action === 'bets') {
        pot += amount
        if (pi >= 0) {
          pState[pi].stack -= amount
          pState[pi].stackBB = +(pState[pi].stack / bb).toFixed(1)
          pState[pi].totalInvested += amount
          pState[pi].currentBet = amount
          pState[pi].actionLabel = `Bet ${(amount / bb).toFixed(1)}bb`
        }
        actionLabel = `bets ${Math.round(amount).toLocaleString()}${allIn ? ' (all-in)' : ''}`
      } else if (action === 'raises') {
        const raiseTo = toM ? parseFloat(toM[1].replace(/,/g, '')) : amount
        const prevInvested = pi >= 0 ? pState[pi].totalInvested : 0
        const additionalCost = raiseTo - prevInvested
        pot += additionalCost
        if (pi >= 0) {
          pState[pi].stack -= additionalCost
          pState[pi].stackBB = +(pState[pi].stack / bb).toFixed(1)
          pState[pi].totalInvested = raiseTo
          pState[pi].currentBet = raiseTo
          pState[pi].actionLabel = `Raise ${(raiseTo / bb).toFixed(1)}bb`
        }
        actionLabel = `raises to ${Math.round(raiseTo).toLocaleString()}${allIn ? ' (all-in)' : ''}`
      }

      // ── Analysis (pot odds, MDF, betting dimensions) ──────────────────
      let analysis = null
      let villainAnalysis = null

      if (isH && action === 'calls') {
        const facingBet = amount
        const potBefore = pot - amount
        if (facingBet > 0) {
          analysis = {
            type: 'facing',
            potBefore: Math.round(potBefore),
            facingBet: Math.round(facingBet),
            potOdds: +(facingBet / (potBefore + facingBet) * 100).toFixed(1),
            mdf: +(potBefore / (potBefore + facingBet) * 100).toFixed(1),
            potBB: +(potBefore / bb).toFixed(1),
            betBB: +(facingBet / bb).toFixed(1),
          }
        }
      } else if (isH && action === 'folds') {
        const lastBetStep = [...steps].reverse().find(s => s.analysis?.type === 'facing')
        if (lastBetStep?.analysis) analysis = { ...lastBetStep.analysis, heroFolded: true }
      } else if (isH && (action === 'bets' || action === 'raises')) {
        const betAmount = action === 'raises' ? (toM ? parseFloat(toM[1].replace(/,/g, '')) : amount) : amount
        const potBefore = pot - (betAmount - (pi >= 0 ? pState[pi].totalInvested - betAmount : 0))
        analysis = {
          type: 'betting',
          potBefore: Math.round(Math.abs(potBefore)),
          betSize: Math.round(betAmount),
          betToPot: potBefore > 0 ? +(betAmount / potBefore * 100).toFixed(1) : 0,
          mbf: +(betAmount / (potBefore + betAmount) * 100).toFixed(1),
          potBB: +(potBefore / bb).toFixed(1),
          betBB: +(betAmount / bb).toFixed(1),
        }
        villainAnalysis = {
          villainMDF: +(Math.abs(potBefore) / (Math.abs(potBefore) + betAmount) * 100).toFixed(1),
          potBefore: Math.round(Math.abs(potBefore)),
          heroBet: Math.round(betAmount),
        }
      } else if (!isH && (action === 'bets' || action === 'raises')) {
        const betAmount = action === 'raises' ? (toM ? parseFloat(toM[1].replace(/,/g, '')) : amount) : amount
        const potBefore = pot - betAmount
        if (potBefore > 0) {
          analysis = {
            type: 'facing',
            potBefore: Math.round(potBefore),
            facingBet: Math.round(betAmount),
            potOdds: +(betAmount / (potBefore + betAmount) * 100).toFixed(1),
            mdf: +(potBefore / (potBefore + betAmount) * 100).toFixed(1),
            potBB: +(potBefore / bb).toFixed(1),
            betBB: +(betAmount / bb).toFixed(1),
          }
        }
      } else if (!isH && (action === 'calls' || action === 'checks' || action === 'folds')) {
        const lastBetStep = [...steps].reverse().find(s => s.analysis?.type === 'facing')
        if (lastBetStep?.analysis) analysis = lastBetStep.analysis
      }

      steps.push({
        street: sd.key,
        label: sd.label,
        action: actionLabel,
        actor: resolve(actor),
        actorIdx: pi,
        isHero: isH,
        pot: Math.round(pot),
        potBB: +(pot / bb).toFixed(1),
        board: [...curBoard],
        ps: snap(),
        analysis,
        villainAnalysis,
      })
    }
  }

  // ── Showdown — parse cards ───────────────────────────────────────────────
  const sdSection = raw.match(/\*\*\* SHOW\s*DOWN \*\*\*([\s\S]*?)(\*\*\* SUMMARY|$)/i)
  if (sdSection) {
    for (const line of sdSection[1].split('\n')) {
      const sm = line.trim().match(/^(.+?)(?::)?\s+shows\s+\[(.+?)\]/i)
      if (sm) {
        const name = sm[1].trim()
        const cards = sm[2].split(' ').filter(c => c.trim())
        let pi = findPlayer(name)
        if (pi < 0) pi = pState.findIndex(p => p.name.startsWith(name) || name.startsWith(p.name))
        if (pi >= 0) pState[pi].cards = cards
      }
      const cm = line.trim().match(/^(.+?) collected ([\d,]+(?:\.\d+)?)/i)
      if (cm) {
        const name = cm[1].trim()
        let pi = findPlayer(name)
        if (pi < 0) pi = pState.findIndex(p => p.name.startsWith(name) || name.startsWith(p.name))
        if (pi >= 0) {
          const amt = parseFloat(cm[2].replace(/,/g, ''))
          pState[pi].stack += amt
          pState[pi].stackBB = +(pState[pi].stack / bb).toFixed(1)
        }
      }
    }
  }

  // SUMMARY section — "showed [cards]" (Winamax/PS format)
  const summarySection = raw.match(/\*\*\* SUMMARY \*\*\*([\s\S]*?)$/i)
  if (summarySection) {
    for (const line of summarySection[1].split('\n')) {
      const sm = line.trim().match(/:\s*(.+?)\s+showed\s+\[(.+?)\]/i)
      if (sm) {
        const name = sm[1].trim()
        const cards = sm[2].split(' ').filter(c => c.trim())
        let pi = findPlayer(name)
        if (pi < 0) pi = pState.findIndex(p => p.name.startsWith(name) || name.startsWith(p.name))
        if (pi >= 0 && pState[pi].cards.length === 0) pState[pi].cards = cards
      }
    }
  }

  // Add showdown step if at least 2 non-folded players have cards
  const playersWithCards = pState.filter(p => p.cards.length > 0 && !p.folded)
  if (playersWithCards.length >= 2) {
    steps.push({
      street: 'showdown', label: 'Showdown', action: 'Showdown',
      actor: null, actorIdx: -1, isHero: false,
      pot, potBB: +(pot / bb).toFixed(1),
      board: bc, ps: snap(),
      analysis: null, villainAnalysis: null,
    })
  }

  return { steps, heroIdx, players: pState, meta }
}

// ─── Formato simplificado para HandDetailPage ────────────────────────────────
// Devolve lista de streets com acções por street, no formato que o modal espera:
//   [{ name: 'PRE-FLOP'|'FLOP'|..., board: string[], actions: [{actor, action, label, amount, allIn, cards?}] }]
//
// Nota: usa o mesmo parseHH como fonte de verdade, mas reduz ao mínimo que o
// HandDetailPage precisa. Evita duplicar lógica de regex.
export function parseStreetsForDisplay(raw, apa) {
  const { steps, players } = parseHH(raw, apa)

  // Mapa step.street → nome UPPER CASE (PRE-FLOP/FLOP/TURN/RIVER/SHOWDOWN)
  const streetNameMap = {
    preflop: 'PRE-FLOP',
    flop: 'FLOP',
    turn: 'TURN',
    river: 'RIVER',
    showdown: 'SHOWDOWN',
  }

  // Construir acções por street
  const streetOrder = ['preflop', 'flop', 'turn', 'river', 'showdown']
  const byStreet = {}
  for (const key of streetOrder) {
    byStreet[key] = { name: streetNameMap[key], board: [], actions: [] }
  }

  for (const step of steps) {
    if (!step.street || !byStreet[step.street]) continue
    // Guardar o board mais recente para esta street
    if (step.board && step.board.length > byStreet[step.street].board.length) {
      byStreet[step.street].board = [...step.board]
    }
    // Se step tem actor real (não é "Blinds posted" ou "X dealt" nem showdown marker)
    if (step.actor && step.action && !/dealt|blinds posted|^showdown$/i.test(step.action)) {
      // Separar "raises to X" etc
      const actionMatch = step.action.match(/^(folds|checks|calls|bets|raises)/i)
      const action = actionMatch ? actionMatch[1].toLowerCase() : step.action
      const amtMatch = step.action.match(/([\d,]+(?:\.\d+)?)/)
      const amount = amtMatch ? parseFloat(amtMatch[1].replace(/,/g, '')) : 0
      const allIn = /all-in/i.test(step.action)
      byStreet[step.street].actions.push({
        actor: step.actor,
        action,
        label: step.action,
        amount,
        allIn,
      })
    }
    // Showdown: cards dos jogadores são snapshot — colocar como acções "shows"
    // Nota: showdown step não tem actor — os cards estão em step.ps. Tratamos em baixo.
  }

  // Para showdown: iterar players finais e adicionar acções "shows" + "collected"
  // (pstate final está no último step)
  const finalStep = steps[steps.length - 1]
  if (finalStep && finalStep.street === 'showdown' && finalStep.ps) {
    for (const p of finalStep.ps) {
      if (p.cards && p.cards.length > 0 && !p.folded) {
        byStreet.showdown.actions.push({
          actor: p.name,
          action: 'shows',
          cards: p.cards,
        })
      }
    }
  }

  // Devolver apenas streets que existem (preflop sempre existe; outras só se têm board ou acções)
  return streetOrder
    .map(k => byStreet[k])
    .filter(s => s.name === 'PRE-FLOP' || s.board.length > 0 || s.actions.length > 0)
}
