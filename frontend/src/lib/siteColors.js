// Tech Debt #13a — fonte única para cores das salas (paletas preservadas por caller)
//
// NOTA: este ficheiro contém 3 paletas distintas porque a app actualmente tem cores
// inconsistentes para a mesma sala em ecrãs diferentes. #13a centraliza num único
// sítio para auditabilidade. #13b unificará para 1 paleta após decisão visual Rui.
//
// QUEM USA O QUÊ:
// - SITE_COLORS_VILLAINS  → Villains.jsx (página /villains)
// - SITE_COLORS_DASHBOARD → Dashboard.jsx (Recent villains panel + Últimas mãos)
// - SITE_COLORS_HANDROW   → HandRow.jsx (coluna "Sala" em todas as listas de mãos)

export const SITE_COLORS_VILLAINS = {
  GGPoker: '#dc2626',     // vermelho
  Winamax: '#f59e0b',     // laranja
  PokerStars: '#22c55e',  // verde
  WPN: '#3b82f6',         // azul
}

export const SITE_COLORS_DASHBOARD = {
  PokerStars: '#ef4444',  // vermelho
  Winamax: '#22c55e',     // verde
  GGPoker: '#f59e0b',     // laranja
  WPN: '#06b6d4',         // ciano
  '888poker': '#8b5cf6',  // púrpura (sala extra que só Dashboard tem)
}

export const SITE_COLORS_HANDROW = {
  Winamax: '#f59e0b',     // laranja
  PokerStars: '#ef4444',  // vermelho
  WPN: '#22c55e',         // verde
  // GGPoker cai no default
}

export const SITE_COLOR_DEFAULT = '#6366f1'  // índigo
