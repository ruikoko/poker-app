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

// LEI v3 (15 Jul 2026): TODAS as raises preflop (open / 3-bet / squeeze / 4-bet)
// são calculadas em RUNTIME por escalão de efetiva (régua única). Os arrays de
// sizing legacy (SIZES_OPEN_*, SIZES_3BET_*/SQUEEZE_*, SIZES_POT_4BET_*) foram
// removidos — já não eram lidos. O 5-bet mantém pot-fraction (abaixo).

// 5-bet rules, sized in relation to pot (LEI v3 §D — inalterado).
let SIZES_POT_5BET_IP = [0.4, ALLIN];
let SIZES_POT_5BET_OOP = [0.5, ALLIN];

// All-In threshold, works like the UI version.
let PREFLOP_ALLIN_THRESHOLD = 1;

// LEI v3 §A — limiar da linha de all-in nos OPENS por EFETIVA (régua única):
// 25 BB geral (IP e BB-vs-limp); 30 BB só a SB (blind-vs-blind).
const STACK_BB_FOR_OPEN_ALLIN_OPTION = 25;       // IP / BB-vs-limp
const STACK_BB_FOR_OPEN_ALLIN_OPTION_BVB = 30;   // SB (blind-vs-blind)

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

// LEI v3 (15 Jul 2026) — size base do open das posições não-blind (IP).
// A Regra de Ouro sobrepõe-se: o open REAL da posição substitui esta base.
let OPEN_BASE_IP_BB = 2;

// LEI v3 §A — as BLINDS (SBvsBB / BB-vs-limp) fazem jam abaixo de 10 BB (a letra
// do quadro: "<10 jam"); as não-blind (IP) mantêm o colapso ≤9.
let BLIND_OPEN_JAM_BELOW_BB = 10;

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

	// LEI v3 — cada função de sizing (open/3bet/4bet/squeeze) já gere o seu
	// próprio all-in POR CONSTRUÇÃO (dedupe garantido). O push global do SPR
	// morreu (SPR≤7 do 4-bet enterrado — §C). 5-bet leva o all-in no seu array.

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

// ── LEI v3 — RÉGUA ÚNICA DA EFETIVA (remaining-based) ────────────────────
// eff = min(REMAINING de quem age, REMAINING do adversário do confronto).
//   open / squeeze → adversário = o MAIOR remaining vivo (por falar / entre
//     opener+callers). 3-bet/4-bet → adversário = o agressor anterior.
// Substitui as 3 medidas antigas (effectiveStackBBAtOpen/VsRaiser/parser).

function remainingBB(ctx, p) {
	return ctx.getPotState().getChipsRemaining(p) / ctx.getSizeBigBlind();
}

// vs o campo: min(actor, maior remaining vivo não-actor). Serve open e squeeze.
function effVsFieldBB(ctx, player) {
	let state = ctx.getPotState();
	let maxOpp = 0;
	for (let q = 0; q < ctx.getNumberOfPlayers(); q++) {
		if (q == player) continue;
		if (state.hasPlayerFolded(q)) continue;
		let r = remainingBB(ctx, q);
		if (r > maxOpp) maxOpp = r;
	}
	if (maxOpp <= 0) return remainingBB(ctx, player);   // sem vivos (degenerado)
	return Math.min(remainingBB(ctx, player), maxOpp);
}

function getSizingsOpening(ctx) {
	let player = ctx.getActivePlayer();
	let eff = effVsFieldBB(ctx, player);
	let ownBB = totalStackChips(ctx, player) / ctx.getSizeBigBlind();
	let shortieOwn = IS_PKO && ownBB <= PKO_SHORTIE_BB;
	let isBlind = (player == ctx.getPlayerIndexSmallBlind()
		|| player == ctx.getPlayerIndexBigBlind());

	// LEI v3 §A — colapso → SÓ JAM (exceto shortie próprio PKO). A letra do
	// quadro: IP mantém >9 = 2bb (jam ≤9); as BLINDS (tabelas SBvsBB/BB-vs-limp)
	// jam abaixo de 10 (<10).
	let jam = isBlind
		? (eff < BLIND_OPEN_JAM_BELOW_BB)
		: (eff <= OPEN_ALLIN_ONLY_EFF_BB);
	if (jam && !shortieOwn)
		return [ctx.sizingAllIn()];

	let sizings = getOpenBaseSizes(ctx, player, eff);

	// LEI v3 §A — linha de all-in por EFETIVA: IP<=25 / SB<=30 / BB(vs limp)<=25.
	let threshold = (player == ctx.getPlayerIndexSmallBlind())
		? STACK_BB_FOR_OPEN_ALLIN_OPTION_BVB   // SB (blind-vs-blind) = 30
		: STACK_BB_FOR_OPEN_ALLIN_OPTION;      // IP e BB(vs limp) = 25
	if (eff <= threshold)
		sizings = pushAllInOnce(ctx, sizings.slice());

	// Regra 3 (shortie PKO): próprio shortie OU adversário por falar all-in/<=4.
	if (shortieOwn ||
		(IS_PKO && anyYetToActOpponentShortOrAllIn(ctx, player, PKO_SHORTIE_BB)))
		sizings = pushAllInOnce(ctx, sizings.slice());

	return sizings;
}

// LEI v3 §A — size base do open (single-size):
//   Regra de Ouro: se a posição ABRIU de verdade → o size real SUBSTITUI a base.
//   Senão: IP não-blind → OPEN_BASE_IP_BB (2 BB) · SB → tabela SBvsBB por eff ·
//   BB → tabela BB-vs-limp por eff. (O colapso <=9 já foi tratado no caller.)
function getOpenBaseSizes(ctx, player, eff) {
	let real = realRaiseForNode(ctx);   // open real desta posição (bets=2) ou undefined
	if (real !== undefined)
		return [sizingBBorAllIn(ctx, real)];
	if (player == ctx.getPlayerIndexSmallBlind())
		return [ctx.sizingBigBlinds(sbOpenSizeByEff(eff))];
	if (player == ctx.getPlayerIndexBigBlind())
		return [ctx.sizingBigBlinds(bbVsLimpSizeByEff(eff))];
	return [ctx.sizingBigBlinds(OPEN_BASE_IP_BB)];
}

// LEI v3 §A — SBvsBB (fold até à SB, a SB abre). eff em BB. Só chamado com
// eff > 9 (o colapso <=9 é universal no getSizingsOpening).
function sbOpenSizeByEff(eff) {
	if (eff <= 15) return 2.2;
	if (eff <= 25) return 2.5;
	if (eff <= 35) return 3;
	if (eff <= 100) return 3.5;
	return 4;
}

// LEI v3 §A — BB sobe sobre LIMP da SB. eff em BB. Só chamado com eff > 9.
function bbVsLimpSizeByEff(eff) {
	if (eff <= 14) return 2;
	if (eff <= 20) return 2.5;
	if (eff <= 30) return 3;
	if (eff <= 100) return 3.5;
	return 4;
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

// LEI v3 §B (15 Jul 2026) — 3-bet por 4 BLOCOS (IP / SB / BB / SBvsBB) × OPEN,
// por escalão fixo de EFETIVA (régua única = min remaining 3bettor vs agressor
// anterior). [size, ALLIN] em todos os escalões; abaixo da banda = SÓ JAM.
// Bónus KO +0.5 (só 3-bet). Regra 3 (PKO + adversário vivo ≤4) acrescenta all-in.
function getSizings3Bets(ctx) {
	let player = ctx.getActivePlayer();
	let raiser = ctx.getLastRaiseAction().getPlayer();
	let callers = ctx.getFlatCallCount();

	// squeeze SÓ se houver um caller VIVO e NÃO-all-in além do opener (um shortie
	// all-in atrás é side-pot → cai no 3bet normal).
	if (callers > 0 && hasLiveNonAllInCaller(ctx, player, raiser))
		return getSizingsSqueeze(ctx, player, raiser);

	let block = threeBetBlock(ctx, player, raiser);
	let eff = effVsAggressorBB(ctx, player, raiser);          // régua única (remaining)
	let openToBB = totalChipsThisStreet(ctx, raiser) / ctx.getSizeBigBlind();

	// LEI v3 §B — BÓNUS KO: KO + opener COBRE o 3-bettor (≥ fichas totais) → +0.5.
	let koBonus = (IS_PKO && totalStackChips(ctx, raiser) >= totalStackChips(ctx, player)) ? 0.5 : 0;

	let sizings = threeBetSizingsV3(eff, block, openToBB, koBonus)
		.map(s => sizingBBorAllIn(ctx, s));

	// Regra 3 — PKO + adversário vivo ≤ PKO_SHORTIE_BB → +all-in (ISO) aditivo.
	if (IS_PKO && anyLiveOpponentAtMostBB(ctx, player, PKO_SHORTIE_BB))
		pushAllInOnce(ctx, sizings);

	return sizings;
}

// LEI v3 §B — bloco do 3-bet: SBvsBB (BB 3-beta o open da SB) / SB (cold 3-bet da
// SB vs opener não-blind) / BB (idem BB) / IP (não-blind — sempre depois do opener).
function threeBetBlock(ctx, player, raiser) {
	let sb = ctx.getPlayerIndexSmallBlind();
	let bb = ctx.getPlayerIndexBigBlind();
	if (player == bb && raiser == sb) return "SBvsBB";
	if (player == sb) return "SB";
	if (player == bb) return "BB";
	return "IP";
}

// LEI v3 §B — array de 3bet em BB (sentinela ALLIN). Abaixo da banda → [ALLIN].
function threeBetSizingsV3(eff, block, openToBB, koBonus) {
	let mult = threeBetMultV3(eff, block);
	if (mult === null)
		return [ALLIN];                       // abaixo da banda = só jam
	let size = round2((mult + (koBonus || 0)) * openToBB);
	return [size, ALLIN];
}

// LEI v3 §B — multiplicador × OPEN por escalão fixo (fronteira no escalão de baixo).
//   IP:     17-25→2.25 · 26-35→2.5 · 36-60→3 · 61-90→3.5 · 91+→4   (<17 jam)
//   SB:     18-25→3    · 26-30→3.5 · 31-80→4 · 81+→5               (<18 jam)
//   BB:     16-20→2.5  · 21-25→3   · 26-35→3.5 · 36-80→4 · 81+→5   (<16 jam)
//   SBvsBB: 16-25→2.2  · 26-35→2.5 · 36-100→3 · 101+→4             (<16 jam)
function threeBetMultV3(eff, block) {
	if (block == "IP") {
		if (eff < 17) return null;
		if (eff <= 25) return 2.25;
		if (eff <= 35) return 2.5;
		if (eff <= 60) return 3;
		if (eff <= 90) return 3.5;
		return 4;
	}
	if (block == "SB") {
		if (eff < 18) return null;
		if (eff <= 25) return 3;
		if (eff <= 30) return 3.5;
		if (eff <= 80) return 4;
		return 5;
	}
	if (block == "BB") {
		if (eff < 16) return null;
		if (eff <= 20) return 2.5;
		if (eff <= 25) return 3;
		if (eff <= 35) return 3.5;
		if (eff <= 80) return 4;
		return 5;
	}
	// SBvsBB
	if (eff < 16) return null;
	if (eff <= 25) return 2.2;
	if (eff <= 35) return 2.5;
	if (eff <= 100) return 3;
	return 4;
}

function round2(v) {
	return Math.round(v * 100) / 100;
}

// Mapeia um valor do array (BB ou sentinela ALLIN) para um sizing HRC.
function sizingBBorAllIn(ctx, s) {
	return s == ALLIN ? ctx.sizingAllIn() : ctx.sizingBigBlinds(s);
}

// LEI v3 — régua única vs o AGRESSOR anterior (3-bet/4-bet): min dos REMAINING.
function effVsAggressorBB(ctx, player, aggressor) {
	return Math.min(remainingBB(ctx, player), remainingBB(ctx, aggressor));
}

function totalStackChips(ctx, p) {
	let state = ctx.getPotState();
	return state.getChipsRemaining(p) + state.getChipsActive(p);
}

function totalChipsThisStreet(ctx, p) {
	return ctx.getPotState().getChipsActive(p);
}

// pt91 — há um oponente VIVO e NÃO-all-in além do opener? Define "squeeze a
// sério" (caller vivo a jogar) vs um 3bet com um shortie all-in atrás (side-pot).
function hasLiveNonAllInCaller(ctx, player, raiser) {
	let state = ctx.getPotState();
	for (let q = 0; q < ctx.getNumberOfPlayers(); q++) {
		if (q == player || q == raiser)
			continue;
		if (state.hasPlayerFolded(q))
			continue;
		if (state.isPlayerAllIn(q))
			continue;
		return true;
	}
	return false;
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

// LEI v3 §C (15 Jul 2026) — 4-bet por 4 BLOCOS (IP/SB/BB/SBvsBB) × 3-BET (to-amount),
// por escalão fixo de EFETIVA (régua única vs o 3-bettor). All-in SEMPRE no nó;
// abaixo do 1º escalão com valor = SÓ ALL-IN. A regra SPR≤7 morre.
function getSizings4Bets(ctx) {
	let player = ctx.getActivePlayer();
	let raiser = ctx.getLastRaiseAction().getPlayer();          // o 3-bettor
	let block = fourBetBlock(ctx, player, raiser);
	let eff = effVsAggressorBB(ctx, player, raiser);
	let prev3betToBB = totalChipsThisStreet(ctx, raiser) / ctx.getSizeBigBlind();
	return fourBetSizingsV3(eff, block, prev3betToBB).map(s => sizingBBorAllIn(ctx, s));
}

// LEI v3 §C — bloco do 4-bet: SBvsBB (a SB 4-beta o 3-bet do BB no BvB) / SB / BB
// (4-bet da blind vs 3-bettor não-blind) / IP (não-blind).
function fourBetBlock(ctx, player, raiser) {
	let sb = ctx.getPlayerIndexSmallBlind();
	let bb = ctx.getPlayerIndexBigBlind();
	if (player == sb && raiser == bb) return "SBvsBB";
	if (player == sb) return "SB";
	if (player == bb) return "BB";
	return "IP";
}

// LEI v3 §C — array de 4bet em BB. Abaixo da banda → [ALLIN]; senão [size, ALLIN].
function fourBetSizingsV3(eff, block, prev3betToBB) {
	let mult = fourBetMultV3(eff, block);
	if (mult === null)
		return [ALLIN];
	return [round2(mult * prev3betToBB), ALLIN];
}

// LEI v3 §C — multiplicador × 3-BET por escalão (fronteira no escalão de baixo).
//   IP:     26-35→2 · 36-60→2.2 · 61-90→2.5 · 91+→2.7   (<26 só allin)
//   SB:     31-80→2.3 · 81+→2.5                         (<31 só allin)
//   BB:     26-35→2.3 · 36-80→2.5 · 81+→3               (<26 só allin)
//   SBvsBB: 36-100→2.2 · 101+→2.7                       (<36 só allin)
function fourBetMultV3(eff, block) {
	if (block == "IP") {
		if (eff < 26) return null;
		if (eff <= 35) return 2;
		if (eff <= 60) return 2.2;
		if (eff <= 90) return 2.5;
		return 2.7;
	}
	if (block == "SB") {
		if (eff < 31) return null;
		if (eff <= 80) return 2.3;
		return 2.5;
	}
	if (block == "BB") {
		if (eff < 26) return null;
		if (eff <= 35) return 2.3;
		if (eff <= 80) return 2.5;
		return 3;
	}
	// SBvsBB
	if (eff < 36) return null;
	if (eff <= 100) return 2.2;
	return 2.7;
}

// 5-bet — mantém 0.4/0.5 pot (com all-in no array).
function getSizings5Bets(ctx) {
	let player = ctx.getActivePlayer();
	let inposition = ctx.isPlayerInPosition(player, ctx.getLastRaiseAction().getPlayer());

	return inposition ?
		SIZES_POT_5BET_IP.map(s => ctx.sizingPot(s)) :
		SIZES_POT_5BET_OOP.map(s => ctx.sizingPot(s));
}

// LEI v3 §E (15 Jul 2026) — SQUEEZE × OPEN por escalão de EFETIVA (régua única =
// min(squeezer, o MAIOR entre opener e callers) = effVsFieldBB no nó de squeeze).
// IP/OOP; [size, ALLIN] em todos; <20 SÓ JAM. O +1bb por caller MORRE.
function getSizingsSqueeze(ctx, player, raiser) {
	let eff = effVsFieldBB(ctx, player);      // min(squeezer, maior vivo=max(opener,callers))
	let openToBB = totalChipsThisStreet(ctx, raiser) / ctx.getSizeBigBlind();
	let isOOP = (player == ctx.getPlayerIndexSmallBlind()
		|| player == ctx.getPlayerIndexBigBlind());
	let mult = squeezeMultV3(eff, isOOP);
	if (mult === null)
		return [ctx.sizingAllIn()];
	return [ctx.sizingBigBlinds(round2(mult * openToBB)), ctx.sizingAllIn()];
}

// LEI v3 §E — multiplicador × OPEN (IP / OOP). <20 → null (jam).
//   20-25→3/3.5 · 26-35→3.5/3.7 · 36-60→3.7/4 · 61-100→4/4.5 · 101+→4.5/5
function squeezeMultV3(eff, isOOP) {
	if (eff < 20) return null;
	if (eff <= 25) return isOOP ? 3.5 : 3;
	if (eff <= 35) return isOOP ? 3.7 : 3.5;
	if (eff <= 60) return isOOP ? 4 : 3.7;
	if (eff <= 100) return isOOP ? 4.5 : 4;
	return isOOP ? 5 : 4.5;
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
