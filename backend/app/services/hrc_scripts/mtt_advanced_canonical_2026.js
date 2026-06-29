/*
 * Advanced MTT script suitable for deeper stacks
 *
 * Only SB can complete/limp
 *
 * Canonical template versionado em 2026 — substitui as 8 variantes legacy.
 * Os arrays SIZES_* são overridden per-hand pelo gerador Python do backend
 * (services/hrc_script_gen.py) consoante o sizing real da HH. Arrays não
 * tocados pelo override mantêm os defaults aqui.
 */

let ALLIN = 9999;

// =====================================================================
// Start of Preflop configuration
// =====================================================================

// Preflop open sizing in big blinds.
// pt29 tree-size control: ALLIN removido dos arrays OPEN — agora controlado
// exclusivamente por shouldAddPreflopAllIn (filtro por stack BB individual
// vs STACK_BB_FOR_OPEN_ALLIN_OPTION). Sem isto, ALLIN=9999 entrava sempre
// via applyAllinThreshold e causava explosao da tree em mesas com mistura
// de short + deep stacks (smoke pt29 GG-5944816316: 26.9 GB > limite 20.4
// GB). 3-bet/4-bet/5-bet arrays mantem o ALLIN literal (lógica SPR-efectivo
// continua valida em pots ja levantados).
// pt89 (#GTO-OPEN-SIZE-NOT-PER-POSITION): opens per-posição (era o bucket
// partilhado SIZES_OPEN_OTHERS). Cada posição não-blind/não-BU tem a sua var,
// para o gerador overridar SÓ a do opener (size + ALLIN por stack individual)
// sem vazar para as fundas. Default [2] em todas (= o antigo OTHERS).
let SIZES_OPEN_UTG1 = [2];
let SIZES_OPEN_UTG  = [2];
let SIZES_OPEN_MP   = [2];
let SIZES_OPEN_HJ   = [2];
let SIZES_OPEN_CO   = [2];
// SIZES_OPEN_OTHERS = fallback defensivo p/ labels inesperados (fora de UTG1/UTG/MP/HJ/CO).
let SIZES_OPEN_OTHERS = [2];
let SIZES_OPEN_BU = [2];
let SIZES_OPEN_SB = [3.5];
let SIZES_OPEN_BB = [4];

// general 3-bet sizing in big blinds
// ⚠️ pt91 (Regra 2 do Rui): os arrays de 3-bet CLÁSSICO abaixo (IP/UTG1..BU e
// SB_VS_*/BB_VS_*) deixaram de ser LIDOS — getSizings3Bets passou a calcular o
// 3bet dinamicamente por efetivo min(3bettor,opener) + IP/OP. Mantidos só como
// referência histórica / defaults inertes. O gerador Python já NÃO os
// sobrescreve. Os SIZES_3BET_SQUEEZE_* CONTINUAM activos (squeeze inalterado).
let SIZES_3BET_IP = [6, ALLIN];
let SIZES_3BET_UTG1 = [6];
let SIZES_3BET_UTG = [6];
let SIZES_3BET_MP = [6];
let SIZES_3BET_HJ = [6];
let SIZES_3BET_CO = [6];
let SIZES_3BET_BU = [6];
let SIZES_3BET_BB_VS_SB = [10, ALLIN];
let SIZES_3BET_BB_VS_OTHER = [8, ALLIN];
let SIZES_3BET_SB_VS_BB = [11, ALLIN];
let SIZES_3BET_SB_VS_OTHER = [8, ALLIN];

// special sizing for squeezes in big blinds
let SIZES_3BET_SQUEEZE_IP = [8, ALLIN];
let SIZES_3BET_SQUEEZE_SB = [11, ALLIN];
let SIZES_3BET_SQUEEZE_BB = [11, ALLIN];
let SQUEEZE_INCREASE_PER_CALL = 1.0;

// general 4-bet rules, sized in relation to pot
let SIZES_POT_4BET_IP = [0.5, ALLIN];
let SIZES_POT_4BET_OOP = [0.4, ALLIN];

// general 5-bet rules, sized in relation to pot
let SIZES_POT_5BET_IP = [0.4, ALLIN];
let SIZES_POT_5BET_OOP = [0.5, ALLIN];

// All-In threshold, works like the UI version
let PREFLOP_ALLIN_THRESHOLD = 1;

// Add all-in as an option if SPR is below this value (3-bet+ only post-pt29).
let PREFLOP_ADD_ALLIN_SPR = 7;

// pt29 tree-size control: threshold para ALLIN em opens (primeira raise
// voluntaria preflop). SPR efectivo nao funciona para opens porque um short
// na mesa puxa effective stacks para baixo e adiciona ALLIN como opcao a
// TODOS os jogadores (incluindo deep stacks 100+BB). Filtro individual por
// stack BB do jogador activo evita a explosao multiway. Threshold 30 BB
// definido em despacho pt29 (Rui). Reduzir para 25 se 30 nao chegar.
//
// pt86 (despacho Rui): o limiar passa a 25 BB GERAL; 30 BB SO em blind-vs-blind
// (SB-vs-BB / BB-vs-SB; na tabela de opens = a SB). SEGURO re: pt29 — o filtro
// CONTINUA por stack INDIVIDUAL (nao efetiva), por isso os deep 100+BB
// continuam excluidos (100 > 25); baixar 30->25 so REMOVE ALLINs (arvore igual
// ou menor), nunca reintroduz a explosao multiway.
const STACK_BB_FOR_OPEN_ALLIN_OPTION = 25;       // geral (era 30 pre-pt86)
const STACK_BB_FOR_OPEN_ALLIN_OPTION_BVB = 30;   // SO blind-vs-blind

// pt91 (Regra 3 do Rui) — flag de formato bounty (PKO/KO/SuperKO/Mystery/...).
// O gerador Python (hrc_script_gen.generate_hrc_script_for_hand) faz replace
// para `true` quando a mão é de um formato com bounty (BOUNTY_FORMATS em
// queue_export.py). Default `false` = comportamento não-PKO (sem ISO extra).
let IS_PKO = false;

// pt91 (Regra 3 do Rui) — gatilho do shortie relevante, em BB. Se houver um
// adversário vivo com stack <= este valor, em PKO acrescenta-se all-in (ISO):
// nos 3bets (qualquer adversário vivo) e nos opens (jogador AINDA POR FALAR).
let PKO_SHORTIE_BB = 4;

// pt91 (Regra 1 do Rui) — open com efetivo <= este valor (capado pelo maior
// adversário vivo, recalculado no nó) → SÓ all-in (remove o min-raise).
let OPEN_ALLIN_ONLY_EFF_BB = 9;

// pt91 (preservação da ação real) — mapa {posição: {bets: size}} das raises
// REAIS preflop desta mão (bets = 1+betCount: open=2, 3bet=3, 4bet=4, 5bet=5;
// size em BB, ou ALLIN). O gerador Python preenche-o. A ação real é RE-INJETADA
// por cima dos sizes das regras (1/2/3), com dedupe, SÓ no nó onde aconteceu —
// garante que a árvore contém sempre a linha real (navegação tem sempre caminho)
// sem apagar os sizes das regras. Default {} = sem mão (comportamento das regras).
let REAL_PREFLOP_RAISES = {};

// Flatting rules: betcount → allowed flats
let ALLOWED_FLATS_PER_RAISE = {
	2: 3,
	3: 2,
	4: 1,
	5: 0,
	6: 0
};

let ALLOW_COLD_CALLS = true;
let ALLOW_FLATS_CLOSING_ACTION = true;


// pt42b — Mirror de `_POSITION_LABELS_BY_N` (backend/app/services/queue_export.py).
// Idx 0 = first-to-act preflop = UTG (N>=3) ou BU/SB (HU). Mantém em sync
// se a tabela Python mudar — não há single-source-of-truth cross-language.
const POSITION_LABELS_BY_N = {
	2: ["BU/SB", "BB"],
	3: ["BU", "SB", "BB"],
	4: ["UTG", "BU", "SB", "BB"],
	5: ["UTG", "HJ", "BU", "SB", "BB"],
	6: ["UTG", "HJ", "CO", "BU", "SB", "BB"],
	7: ["UTG", "EP", "MP", "CO", "BU", "SB", "BB"],
	8: ["UTG", "EP", "MP", "HJ", "CO", "BU", "SB", "BB"],
	9: ["UTG", "EP1", "EP2", "MP", "HJ", "CO", "BU", "SB", "BB"]
};


// =====================================================================
// Start of Postflop configuration
// =====================================================================

let POSTFLOP_PRIMARY_HINT = 0.75;
let POSTFLOP_ADD_FLOP_BET_POT = [0.20];
let POSTFLOP_ADD_FLOP_CBET_POT = [];
let POSTFLOP_ADD_ALLIN_SPR = 5;
let POSTFLOP_ALLOW_DONK = false;
let POSTFLOP_ALLOW_DONK_PREV_AGGRESSION = true;

// pt42 — variante "pré-flop + flop only". Forçar checkdown após FLOP para
// todos os live counts (2..9): turn e river ficam sem betting modelado, só
// check. Reduz substancialmente o tamanho da árvore HRC para mesas de
// estudo onde só interessam decisões pré-flop e flop.
let POSTFLOP_FORCE_CHECKDOWN_AFTER = {
	2: FLOP,
	3: FLOP,
	4: FLOP,
	5: FLOP,
	6: FLOP,
	7: FLOP,
	8: FLOP,
	9: FLOP
}


// =====================================================================
// ACTUAL SCRIPT STARTS HERE
// =====================================================================

function getSizingsPreflop(ctx) {
	let bets = 1 + ctx.getBetCount();
	let sizings = [];
	switch (bets) {
		case 2: //opening
			sizings = getSizingsOpening(ctx); break;
		case 3: //3-bets
			sizings = getSizings3Bets(ctx); break;
		case 4: //4-bets
			sizings = getSizings4Bets(ctx); break;
		case 5: //5-bets
			sizings = getSizings5Bets(ctx); break;
		default: //6-bets+
			return ctx.sizingAllIn();
	}

	if (shouldAddPreflopAllIn(ctx))
		sizings.push(ctx.sizingAllIn());

	// pt91 — preserva a ação REAL no seu nó (re-injeta por cima das regras,
	// dedupe). As regras 1/2/3 são a camada hipotética; isto garante que a
	// linha real existe sempre na árvore.
	sizings = preserveRealRaise(ctx, sizings);

	return applyAllinThreshold(ctx, sizings);
}

// pt91 — size real (BB ou ALLIN) para o nó atual (posição + bets), ou undefined.
function realRaiseForNode(ctx) {
	let pos = positionLabelForIdx(ctx.getActivePlayer(), ctx.getNumberOfPlayers());
	if (pos == null)
		return undefined;
	let byBets = REAL_PREFLOP_RAISES[pos];
	if (byBets == null)
		return undefined;
	return byBets[1 + ctx.getBetCount()];   // chave = bets (open=2, 3bet=3, …)
}

// pt91 — acrescenta a ação real a `sizings` (in place) se houver e ainda não
// estiver presente (dedupe). "ALLIN" → sizingAllIn(); número → sizingBigBlinds.
function preserveRealRaise(ctx, sizings) {
	let real = realRaiseForNode(ctx);
	if (real === undefined)
		return sizings;
	let s = (real === "ALLIN" || real === ALLIN)
		? ctx.sizingAllIn()
		: ctx.sizingBigBlinds(real);
	if (sizings.indexOf(s) < 0)
		sizings.push(s);
	return sizings;
}

function applyAllinThreshold(ctx, sizings) {
	let sizeallin = ctx.sizingAllIn();
	let activechips = ctx.getPotState().getChipsActive(ctx.getActivePlayer());
	let thresholdchips = activechips +
		(sizeallin - activechips) * PREFLOP_ALLIN_THRESHOLD;
	return sizings.map(s => s >= thresholdchips ? sizeallin : s);
}

// pt29 tree-size control helpers (despacho Rui).
// Em opens (primeira raise voluntaria preflop) a decisao "adicionar ALLIN
// como opcao" passa a depender da stack INDIVIDUAL do jogador activo (BB
// equivalent) em vez do SPR efectivo. Em pots ja levantados (3-bet+) a
// logica SPR-efectivo original mantem-se via PREFLOP_ADD_ALLIN_SPR.

function getActivePlayerStackBB(ctx) {
	let pot = ctx.getPotState();
	let player = ctx.getActivePlayer();
	return pot.getChipsRemaining(player) / ctx.getSizeBigBlind();
}

function isPreflopFirstVoluntaryRaise(ctx) {
	// Blinds contam como bet 1 preflop. betCount === 1 = ainda nenhuma raise voluntaria.
	return ctx.getStreet() == PREFLOP && ctx.getBetCount() == 1;
}

// pt86: blind-vs-blind = so restam as duas blinds vivas (SB-vs-BB folded-to-SB,
// ou BB-vs-SB com a SB a limpar). Usa so a API ja existente.
function isBlindVsBlind(ctx) {
	let p = ctx.getActivePlayer();
	let sb = ctx.getPlayerIndexSmallBlind();
	let bb = ctx.getPlayerIndexBigBlind();
	if (p != sb && p != bb)
		return false;
	let state = ctx.getPotState();
	for (let q = 0; q < ctx.getNumberOfPlayers(); q++) {
		if (q == sb || q == bb)
			continue;
		if (!state.hasPlayerFolded(q))
			return false;   // algum nao-blind ainda vivo -> multiway, nao BvB
	}
	return true;
}

function shouldAddPreflopAllIn(ctx) {
	if (isPreflopFirstVoluntaryRaise(ctx)) {
		// Opens: filtra por stack individual do jogador activo (pt29).
		// pt86: 25 BB geral, 30 BB so em blind-vs-blind.
		let threshold = isBlindVsBlind(ctx)
			? STACK_BB_FOR_OPEN_ALLIN_OPTION_BVB
			: STACK_BB_FOR_OPEN_ALLIN_OPTION;
		return getActivePlayerStackBB(ctx) <= threshold;
	}
	// pt91 (Regra 2 do Rui): o 3bet (betCount==2) controla o all-in DENTRO de
	// getSizings3Bets (bandas IP/OP por efetivo + ISO da Regra 3). Não adicionar
	// aqui, senão um 3bet fundo (>=40 IP / >=45 OP, que a Regra 2 quer SEM
	// all-in) ganhava o jam pelo SPR. Squeeze (também betCount==2) mantém o
	// all-in via os seus arrays SIZES_3BET_SQUEEZE_* (contêm ALLIN).
	if (ctx.getBetCount() == 2)
		return false;
	// 4-bet+: mantem logica original SPR-efectivo.
	return ctx.getStackPotRatio() <= PREFLOP_ADD_ALLIN_SPR;
}

function getSizingsOpening(ctx) {
	let player = ctx.getActivePlayer();
	let baseSizes = getOpenBaseSizes(ctx, player);

	// pt91 (Regra 1 do Rui): open com EFETIVO <= OPEN_ALLIN_ONLY_EFF_BB (capado
	// pelo maior adversário vivo, nó-a-nó) → SÓ all-in (remove o min-raise).
	// EXCEÇÃO (Regra 3): em PKO, se o PRÓPRIO opener for o shortie
	// (<= PKO_SHORTIE_BB), mantém [min, all-in] em vez de só all-in.
	let effBB = effectiveStackBBAtOpen(ctx, player);
	let ownStackBB = totalStackChips(ctx, player) / ctx.getSizeBigBlind();
	let shortieOwnOpen = IS_PKO && ownStackBB <= PKO_SHORTIE_BB;

	if (effBB <= OPEN_ALLIN_ONLY_EFF_BB && !shortieOwnOpen)
		return [ctx.sizingAllIn()];

	let sizings = baseSizes;

	// pt91 (Regra 3): o shortie a abrir (PKO, <= PKO_SHORTIE_BB) leva min + all-in.
	if (shortieOwnOpen)
		sizings = pushAllInOnce(ctx, sizings.slice());

	// pt91 (Regra 3): PKO + jogador AINDA POR FALAR já all-in ou <= PKO_SHORTIE_BB
	// → +all-in (ISO) ADITIVO. Num nó de open, todos os adversários vivos ainda
	// estão por falar (os anteriores já foldaram).
	if (IS_PKO && anyYetToActOpponentShortOrAllIn(ctx, player, PKO_SHORTIE_BB))
		sizings = pushAllInOnce(ctx, sizings.slice());

	return sizings;
}

function getOpenBaseSizes(ctx, player) {
	if (player == ctx.getPlayerIndexButton()) //BU
		return SIZES_OPEN_BU.map(s => ctx.sizingBigBlinds(s));
	if (player == ctx.getPlayerIndexSmallBlind()) //SB
		return SIZES_OPEN_SB.map(s => ctx.sizingBigBlinds(s));
	if (player == ctx.getPlayerIndexBigBlind()) //BB
		return SIZES_OPEN_BB.map(s => ctx.sizingBigBlinds(s));

	// pt89 (#GTO-OPEN-SIZE-NOT-PER-POSITION) — per-posição (era SIZES_OPEN_OTHERS
	// partilhado). Reusa positionLabelForIdx (helper pt42b).
	return openSizesForPosition(positionLabelForIdx(player, ctx.getNumberOfPlayers()))
		.map(s => ctx.sizingBigBlinds(s));
}

// pt91 (Regra 1) — efetivo (BB) no nó de open = min(stack total do opener, maior
// stack total entre adversários vivos). Nó-a-nó: foldados não contam.
function effectiveStackBBAtOpen(ctx, player) {
	let state = ctx.getPotState();
	let bb = ctx.getSizeBigBlind();
	let pTotal = totalStackChips(ctx, player);
	let maxOpp = 0;
	for (let q = 0; q < ctx.getNumberOfPlayers(); q++) {
		if (q == player)
			continue;
		if (state.hasPlayerFolded(q))
			continue;
		let t = totalStackChips(ctx, q);
		if (t > maxOpp)
			maxOpp = t;
	}
	if (maxOpp <= 0)
		return pTotal / bb;   // sem adversários vivos (degenerado)
	return Math.min(pTotal, maxOpp) / bb;
}

// pt91 (Regra 3 do open) — há adversário AINDA POR FALAR já all-in ou com stack
// total <= thresholdBB? Num nó de open, todos os vivos estão por falar.
function anyYetToActOpponentShortOrAllIn(ctx, player, thresholdBB) {
	let state = ctx.getPotState();
	let bb = ctx.getSizeBigBlind();
	for (let q = 0; q < ctx.getNumberOfPlayers(); q++) {
		if (q == player)
			continue;
		if (state.hasPlayerFolded(q))
			continue;
		if (state.isPlayerAllIn(q))
			return true;
		if (totalStackChips(ctx, q) / bb <= thresholdBB)
			return true;
	}
	return false;
}

function openSizesForPosition(label) {
	switch (label) {
		case "UTG1": return SIZES_OPEN_UTG1;
		case "UTG":  return SIZES_OPEN_UTG;
		case "MP":   return SIZES_OPEN_MP;
		case "HJ":   return SIZES_OPEN_HJ;
		case "CO":   return SIZES_OPEN_CO;
		default:     return SIZES_OPEN_OTHERS;   // fallback defensivo
	}
}

// pt91 (Regra 2 do Rui) — sizing de 3bet por EFETIVO = min(stack total do
// 3bettor, stack total do opener), em BB. IP/OP vs o opener. SUBSTITUI o
// dispatch por posição (pt42b) E os arrays especiais SB/BB. Squeeze (callers>0)
// mantém a lógica atual (SIZES_3BET_SQUEEZE_*). Regra 3 (PKO + adversário vivo
// <= PKO_SHORTIE_BB) acrescenta all-in (ISO) ADITIVO, nó-a-nó.
function getSizings3Bets(ctx) {
	let player = ctx.getActivePlayer();
	let raiser = ctx.getLastRaiseAction().getPlayer();
	let callers = ctx.getFlatCallCount();

	if (callers > 0)
		return getSizingsSqueeze(ctx, player, callers);

	let isIP = ctx.isPlayerInPosition(player, raiser);
	let effBB = effectiveStackBBVsRaiser(ctx, player, raiser);
	let openToBB = totalChipsThisStreet(ctx, raiser) / ctx.getSizeBigBlind();

	let sizings = threeBetSizings(effBB, isIP, openToBB)
		.map(s => sizingBBorAllIn(ctx, s));

	// pt91 (Regra 3) — PKO + adversário vivo <= PKO_SHORTIE_BB → +all-in (ISO).
	if (IS_PKO && anyLiveOpponentAtMostBB(ctx, player, PKO_SHORTIE_BB))
		pushAllInOnce(ctx, sizings);

	return sizings;
}

// pt91 (Regra 2) — array de 3bet em BB (com sentinela ALLIN) por efetivo+IP/OP.
//   IP: <18 -> [ALLIN]; 18..40 -> [size, ALLIN]; >=40 -> [size]
//   OP: <20 -> [ALLIN]; 20..45 -> [size, ALLIN]; >=45 -> [size]
//   size = multiplicador(eff) * openToBB. Mirror EXACTO de
//   hrc_script_gen.threebet_sizings_bb (manter em sync — drift cross-language).
function threeBetSizings(effBB, isIP, openToBB) {
	let lo = isIP ? 18 : 20;          // abaixo -> só all-in
	let hi = isIP ? 40 : 45;          // >= -> só size (sem all-in)
	let size = round2(threeBetMultiplier(effBB, isIP) * openToBB);
	if (effBB < lo)
		return [ALLIN];
	if (effBB < hi)
		return [size, ALLIN];
	return [size];
}

// pt91 (Regra 2) — multiplicador "x" sobre o raise inicial (open).
//   IP: <20 -> 2.3 fixo; 20..50 interp linear 2.3->3.0; >50 -> 3.0
//   OP: <20 -> 2.5 fixo; 20..50 interp linear 2.5->4.0; >50 -> 4.0
function threeBetMultiplier(effBB, isIP) {
	let loX = isIP ? 2.3 : 2.5;
	let hiX = isIP ? 3.0 : 4.0;
	if (effBB < 20)
		return loX;
	if (effBB > 50)
		return hiX;
	return loX + (effBB - 20) / (50 - 20) * (hiX - loX);
}

function round2(v) {
	return Math.round(v * 100) / 100;
}

// Mapeia um valor do array (BB ou sentinela ALLIN) para um sizing HRC.
function sizingBBorAllIn(ctx, s) {
	return s == ALLIN ? ctx.sizingAllIn() : ctx.sizingBigBlinds(s);
}

// Efetivo (BB) do confronto 3bettor vs opener = min dos stacks TOTAIS (resto +
// o que já está no pote nesta street). Capado SÓ pelo opener (não por shorties
// atrás) — despacho do Rui.
function effectiveStackBBVsRaiser(ctx, player, raiser) {
	let bb = ctx.getSizeBigBlind();
	let pTotal = totalStackChips(ctx, player);
	let rTotal = totalStackChips(ctx, raiser);
	return Math.min(pTotal, rTotal) / bb;
}

function totalStackChips(ctx, p) {
	let state = ctx.getPotState();
	return state.getChipsRemaining(p) + state.getChipsActive(p);
}

function totalChipsThisStreet(ctx, p) {
	return ctx.getPotState().getChipsActive(p);
}

// pt91 (Regra 3) — há algum adversário vivo (não-foldado) com stack total
// <= thresholdBB? Nó-a-nó: foldados não contam.
function anyLiveOpponentAtMostBB(ctx, player, thresholdBB) {
	let state = ctx.getPotState();
	let bb = ctx.getSizeBigBlind();
	for (let q = 0; q < ctx.getNumberOfPlayers(); q++) {
		if (q == player)
			continue;
		if (state.hasPlayerFolded(q))
			continue;
		if (totalStackChips(ctx, q) / bb <= thresholdBB)
			return true;
	}
	return false;
}

// Acrescenta o all-in ao array (in place) só se ainda não estiver presente.
function pushAllInOnce(ctx, sizings) {
	let allin = ctx.sizingAllIn();
	if (sizings.indexOf(allin) < 0)
		sizings.push(allin);
	return sizings;
}

function positionLabelForIdx(idx, n) {
	let labels = POSITION_LABELS_BY_N[n];
	if (labels == null) return null;
	return labels[idx] || null;
}

function getSizings4Bets(ctx) {
	let player = ctx.getActivePlayer();
	let inposition = ctx.isPlayerInPosition(player, ctx.getLastRaiseAction().getPlayer());

	return inposition ?
		SIZES_POT_4BET_IP.map(s => ctx.sizingPot(s)) :
		SIZES_POT_4BET_OOP.map(s => ctx.sizingPot(s));
}

function getSizings5Bets(ctx) {
	let player = ctx.getActivePlayer();
	let inposition = ctx.isPlayerInPosition(player, ctx.getLastRaiseAction().getPlayer());

	return inposition ?
		SIZES_POT_5BET_IP.map(s => ctx.sizingPot(s)) :
		SIZES_POT_5BET_OOP.map(s => ctx.sizingPot(s));
}

function getSizingsSqueeze(ctx, player, callers) {
	let sizings = SIZES_3BET_SQUEEZE_IP;
	if (player == ctx.getPlayerIndexSmallBlind())
		sizings = SIZES_3BET_SQUEEZE_SB;
	if (player == ctx.getPlayerIndexBigBlind())
		sizings = SIZES_3BET_SQUEEZE_BB;
	return sizings.map(s => ctx.sizingBigBlinds(s + SQUEEZE_INCREASE_PER_CALL * (callers - 1)));
}

function getSizingsPostflop(ctx) {
	let player = ctx.getActivePlayer();
	if (!POSTFLOP_ALLOW_DONK && ctx.isDonkBet()) {
		if (!POSTFLOP_ALLOW_DONK_PREV_AGGRESSION ||
			Array.from(ctx.getActionSequenceFull())
				.findIndex(pa => pa.getPlayer() == player && pa.getActionType() == RAISE) < 0)
			return [];
	}

	let sizings = [ctx.sizingGeometricHint(POSTFLOP_PRIMARY_HINT)];

	if (ctx.getStreet() == FLOP && ctx.getBetCount() == 0) {
		sizings.push(...POSTFLOP_ADD_FLOP_BET_POT.map(s => ctx.sizingPot(s)));
		let raise = ctx.getLastRaiseAction();
		if (raise != null && raise.getPlayer() == player)
			sizings.push(...POSTFLOP_ADD_FLOP_CBET_POT.map(s => ctx.sizingPot(s)));
	}

	if (ctx.getStackPotRatio() <= POSTFLOP_ADD_ALLIN_SPR)
		sizings.push(ctx.sizingAllIn());

	return sizings;
}

function canFlatCallPreflop(ctx) {
	let bets = ctx.getBetCount();
	if (bets == 1) //only SB is allowed to complete
		return ctx.getActivePlayer() == ctx.getPlayerIndexSmallBlind();
	if (ALLOW_FLATS_CLOSING_ACTION && isClosingActionPreflop(ctx))
		return true;
	if (!ALLOW_COLD_CALLS && isColdCall(ctx, ctx.getActivePlayer()))
		return false;
	if (ALLOWED_FLATS_PER_RAISE[bets] == undefined)
		return false;
	return ctx.getFlatCallCount() < ALLOWED_FLATS_PER_RAISE[bets];
}

function isClosingActionPreflop(ctx) {
	let player = ctx.getActivePlayer();

	if (ctx.getBetCount() == 1)
		return player == ctx.getPlayerIndexBigBlind();

	let maxactive = 0;
	let state = ctx.getPotState();
	let otherplayers = []
	for (p = 0; p < ctx.getNumberOfPlayers(); p++)
		if (!state.hasPlayerFolded(p) && p != player) {
			otherplayers.push(p);
			maxactive = Math.max(maxactive, state.getChipsActive(p));
		}

	for (p of otherplayers)
		if (!state.isPlayerAllIn(p) && state.getChipsActive(p) < maxactive)
			return false;

	return true;
}

function hasNextStreetBetting(ctx) {
	let live = ctx.getPotState().countPlayersLive();
	if (POSTFLOP_FORCE_CHECKDOWN_AFTER[live] == undefined)
		return false;
	return ctx.getStreet() < POSTFLOP_FORCE_CHECKDOWN_AFTER[live];
}

function isColdCall(ctx) {
	if (ctx.getBetCount() <= 2)
		return false;
	for (action of ctx.getActionSequence())
		if (action.getPlayer() == ctx.getActivePlayer())
			return false;
	return true;
}
