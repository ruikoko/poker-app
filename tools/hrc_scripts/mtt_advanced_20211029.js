/*
 * Advanced MTT script suitable for deeper stacks
 * 
 * Only SB can complete/limp
 * 
 * Preflop:
 * - Opening / 3-bet / squeeze sizes in big blinds
 * - Separate sizings for SB / BB
 * - Sizing for 4-bets and 5-bets in relation to the pot IP & OOP
 * - Configurable number of flats against opens/3bets/etc
 * - Option to disable cold calls against 3-bets+
 * - Option to always allow flat calls if they close the action
 * - Adding all-in if SPR is below a set value
 * - All-in threshold like UI
 * 
 * Postflop:
 * - Option to disable donk betting
 * - Option to allow donk betting only if a player showed previous aggression
 * - Option to force a checkdown for multiway pots after a set street
 * - Option for additional pot-% sizings for all flop bets
 * - Option for additional pot-% sizings only for flop c-bets
 * - Adding all-in if SPR is below a set value
 * 
 * Notes: 
 * The default config allows 1 flat against opens, plus a flat by 
 * the big blind because this closes the action. Allowing 2 flats instead
 * will allow some 4-way pots (opener + 2 regular flats + bb).
 * 
 */

let ALLIN = 9999;

// =====================================================================
// Start of Preflop configuration
// =====================================================================

//Preflop open sizing in big blinds
let SIZES_OPEN_OTHERS = [2.3];
let SIZES_OPEN_BU = [2.3];
let SIZES_OPEN_SB = [3.5];
let SIZES_OPEN_BB = [3.5];

//general 3-bet sizing in big blinds
let SIZES_3BET_IP = [6.9];
let SIZES_3BET_BB_VS_SB = [9.0];
let SIZES_3BET_BB_VS_OTHER = [9.2];
let SIZES_3BET_SB_VS_BB = [9.2];
let SIZES_3BET_SB_VS_OTHER = [8.1];

//special sizing for squeezes in big blinds
let SIZES_3BET_SQUEEZE_IP = [9.2];
let SIZES_3BET_SQUEEZE_SB = [10.35];
let SIZES_3BET_SQUEEZE_BB = [11.5];
let SQUEEZE_INCREASE_PER_CALL = 2.0; //added to squeeze size for multiple callers

//general 4-bet rules, sized in relation to pot
let SIZES_POT_4BET_IP = [0.9, ALLIN];
let SIZES_POT_4BET_OOP = [1.2, ALLIN];

//general 5-bet rules, sized in relation to pot
let SIZES_POT_5BET_IP = [0.9, ALLIN];
let SIZES_POT_5BET_OOP = [1.2, ALLIN];

//All-In threshold, works like the UI version
let PREFLOP_ALLIN_THRESHOLD = 0.37;

//Add all-in as an option if SPR is below this value
let PREFLOP_ADD_ALLIN_SPR = 7;

//Flatting rules in format
//betcount : allowedflats
let ALLOWED_FLATS_PER_RAISE = {
	2: 1, //opens: 1 flat
	3: 1, //3-bets: 1 flat
	4: 1, //4-bets: 1 flat
	5: 0, //etc
	6: 0
};

//Whether to allow cold calls of 3+ bets
let ALLOW_COLD_CALLS = false;
//Additionally allow any flat that is closing the action
let ALLOW_FLATS_CLOSING_ACTION = true;


// =====================================================================
// Start of Postflop configuration
// =====================================================================


//Primary geometric betting hint, this works likle the UI setting
let POSTFLOP_PRIMARY_HINT = 0.75;

//Additional options for flop sizings
let POSTFLOP_ADD_FLOP_BET_POT = [0.33]; //Additional pot-bet for all flop bets, e.g. set to 0.33 for a 1/3rd pot bet
let POSTFLOP_ADD_FLOP_CBET_POT = []; //Additional pot-bet for the flop cbettor only

//Some additional Postflop Settings
let POSTFLOP_ADD_ALLIN_SPR = 5; //Add all-in as an option if SPR is below this value
let POSTFLOP_ALLOW_DONK = false; //Whether to allow all donk bets
let POSTFLOP_ALLOW_DONK_PREV_AGGRESSION = true; //Allow donks for previous aggressors

//This defines the last street of "regular" betting, starting a forced check-down on next street
//The relevant player count is the number of non-allin, non-folded players at the end of the current street
//e.g. 4 : TURN will check down the pot if there are still 4 live players by the end of the turn
let POSTFLOP_FORCE_CHECKDOWN_AFTER = {
	2: RIVER, //2-way pots
	3: RIVER, //3-way, etc..
	4: TURN,
	5: FLOP
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

	if (ctx.getStackPotRatio() <= PREFLOP_ADD_ALLIN_SPR)
		sizings.push(ctx.sizingAllIn());

	return applyAllinThreshold(ctx, sizings);
}

function applyAllinThreshold(ctx, sizings) {
	let sizeallin = ctx.sizingAllIn();
	let activechips = ctx.getPotState().getChipsActive(ctx.getActivePlayer());
	let thresholdchips = activechips +
		(sizeallin - activechips) * PREFLOP_ALLIN_THRESHOLD;
	return sizings.map(s => s >= thresholdchips ? sizeallin : s);
}

function getSizingsOpening(ctx) {
	let player = ctx.getActivePlayer();

	if (player == ctx.getPlayerIndexButton()) //BU
		return SIZES_OPEN_BU.map(s => ctx.sizingBigBlinds(s));
	if (player == ctx.getPlayerIndexSmallBlind()) //SB
		return SIZES_OPEN_SB.map(s => ctx.sizingBigBlinds(s));
	if (player == ctx.getPlayerIndexBigBlind()) //BB
		return SIZES_OPEN_BB.map(s => ctx.sizingBigBlinds(s));

	return SIZES_OPEN_OTHERS.map(s => ctx.sizingBigBlinds(s));
}

function getSizings3Bets(ctx) {
	let player = ctx.getActivePlayer();
	let raiser = ctx.getLastRaiseAction().getPlayer();
	let callers = ctx.getFlatCallCount();

	if (callers > 0)
		return getSizingsSqueeze(ctx, player, callers);
	if (player == ctx.getPlayerIndexSmallBlind()) { //Special rules for SB
		if (raiser == ctx.getPlayerIndexBigBlind())
			return SIZES_3BET_SB_VS_BB.map(s => ctx.sizingBigBlinds(s)); //sb vs bb iso
		return SIZES_3BET_SB_VS_OTHER.map(s => ctx.sizingBigBlinds(s)); //other sb 3bets
	}
	if (player == ctx.getPlayerIndexBigBlind()) { //Special rules for BB
		if (raiser == ctx.getPlayerIndexSmallBlind())
			return SIZES_3BET_BB_VS_SB.map(s => ctx.sizingBigBlinds(s)); //bb vs sb rfi
		return SIZES_3BET_BB_VS_OTHER.map(s => ctx.sizingBigBlinds(s)); //other bb 3bets
	}

	return SIZES_3BET_IP.map(s => ctx.sizingBigBlinds(s)); //3bets for the other players
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

//Tests if a call by the current player would be closing the action
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

//Tests for 3+bets whether the current player had a previous action on the current street
function isColdCall(ctx) {
	if (ctx.getBetCount() <= 2)
		return false;
	for (action of ctx.getActionSequence())
		if (action.getPlayer() == ctx.getActivePlayer())
			return false;
	return true;
}


