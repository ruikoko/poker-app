"""Cura do core — coroa de jogadores ELIMINADOS (verde-KO). GG only, PKO/KO.

DEFEITO (armadilha verde-KO, ver CLAUDE.md; caso arieloo/mirroring GG-6114944767 pt95;
caso GG-6140169166 Hero $170.63←KamikazzE97): quando um jogador é eliminado, a coroa
PRÓPRIA dele some e METADE do bounty aparece a VERDE na coroa de quem o elimina. A leitura
por-seat da Vision atribui ao seat eliminado a coroa do seat VIZINHO → bounty errado (veneno).

INVARIANTE (não pode quebrar): um seat ELIMINADO (sinal da HH — all-in e perdeu) NUNCA
recebe a coroa por-seat da Vision. A anulação depende SÓ da HH — nunca do prompt ler o verde.

CHOKEPOINT: `resolve_seat_bounty()` — TODOS os caminhos AUTOMÁTICOS que escrevem bounty
por-seat no ingest/backfill passam por aqui (enrich gold/position_v3, table-ss, gold-carry).
Endpoints MANUAIS (/set-bounties, /set-anon-map) ficam de fora (aí é o Rui a mandar).

MUST     — eliminado sem verde derivável → bounty NULL + review='eliminated_no_green'.
SHOULD   — 1 eliminado + 1 verde → bounty = verde (instantâneo; convenção #KO-CROWN-INSTANT-FIX,
           o resto do código faz ÷instant_fraction=×2 → total). Guarda o INSTANTÂNEO (o verde).
FALLBACK — multiway (vários eliminados ou vários verdes, sem ligar 1:1) → NULL + 'eliminated_ambiguous'.
VIVO-$0  — jogador VIVO (HH) em torneio KO (base do TS > 0) com coroa lida $0 → NUNCA gravar o $0
           silencioso → NULL + 'live_crown_read_zero'. NÃO se deriva da base (o vivo pode ter KOs
           acumulados → a base subvaloriza; ex. GG-6132925926 Hero 2 KOs = coroa $100 ≠ base÷2 $50).
           Só dispara com base conhecida (GG + TS); sem base = passthrough. Valor em falta é honesto.
VANILLA  — jogador VIVO num torneio SEM bounty (GG + TS presente + buy_in_bounty nulo/0) → não há
           coroa possível no ecrã → coroa FORÇADA a NULL (#SPURIOUS-CROWN-NON-KO; ex. GG-6138905902
           Daily Hyper $60: $50/$20 inventados pela Vision do table-SS). Raiz: `_seats_to_vision_data`
           copia `bounty_usd` da Vision sem gate; o funil anula na origem.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger("eliminated_bounty")

# Marca de review no seat (apa/pn) quando o bounty do eliminado fica por preencher.
BOUNTY_REVIEW_KEY = "bounty_review"
REVIEW_NO_GREEN = "eliminated_no_green"       # bustou, sem verde legível → por rever
REVIEW_AMBIGUOUS = "eliminated_ambiguous"     # multiway → não se liga verde↔eliminado
REVIEW_LIVE_ZERO = "live_crown_read_zero"     # KO (base TS>0) + VIVO (HH) + coroa lida $0 → por rever

# Proveniência do bounty no seat (apa/pn). O CRIVO VERDADEIRO da cura: um seat
# HH-bustado com coroa >0 SÓ é aceitável se a proveniência for 'green_ko' (derivado
# do verde pelo chokepoint). Coroa >0 num bustado SEM esta marca = origem-Vision =
# contaminação (o "forte" da heurística é só um proxy visível deste crivo).
BOUNTY_SOURCE_KEY = "bounty_source"
SOURCE_GREEN_KO = "green_ko"                  # derivado do verde-KO na coroa do eliminador
# CANON DOS BOUNTIES (docs/CANON_BOUNTIES.md, LEI): a COROA é o bounty — é a única unidade.
# Ao eliminar, o VERDE na coroa de quem elimina = a coroa da vítima ÷ 2 (regras 2-3) → a coroa
# do eliminado que se grava = verde × 2 (regra 4). Provado pela imagem (GG-6132507189, Ward E).
# "instantâneo"/"total"/conversões = vocabulário BANIDO pelo CANON; a unidade é a coroa, ponto.
GREEN_TO_CROWN_FACTOR = 2.0

# ── SELO do bounty (invariante do Rui, 18 Jul) ────────────────────────────────
# "O que o Rui valida fica selado — NENHUM processo automático escreve por cima."
# Um valor selado é intocável para os caminhos AUTOMÁTICOS (re-apply table-SS,
# re-deanon, backfills, scrub). Só a mão do Rui (endpoints manuais) o muda.
SOURCE_MANUAL = "manual"                       # carimbo do Rui (/set-bounties, editor Saúde GG)
SOURCE_DERIVED_GREEN_KO = "derived_green_ko"   # fluxo Etapa-2 (Vision ao verde, carimbado)
SOURCE_CROSS_CAPTURE = "cross_capture"         # LEI DO CRUZAMENTO — coroa preenchida da fonte
# irmã (Gold/outra SS), CRIVADA pela física (floor + não-desce) e carimbada em LOTE pelo Rui.
SOURCE_CROSS_CONFLICT = "cross_conflict"        # conflito resolvido por (B): crescimento óbvio
# (mais recente = max e ≥ coroa fresca base÷2) → fica o mais recente, pela física do CANON.
SOURCE_CROSS_EXCLUSION = "cross_exclusion"      # conflito resolvido por EXCLUSÃO DE PARTES: a
# leitura < KO inicial (base÷2) é impossível → morre; fica o `stored` são (≥ base÷2 + na grelha).
# Fontes que SELAM um seat. `green_ko` já era de-facto selado (`_preserves_green_ko`);
# generaliza-se para todas + o flag `bounty_confirmed` (exceção manual pré-existente).
SEALED_BOUNTY_SOURCES = frozenset(
    {SOURCE_MANUAL, SOURCE_GREEN_KO, SOURCE_DERIVED_GREEN_KO,
     SOURCE_CROSS_CAPTURE, SOURCE_CROSS_CONFLICT, SOURCE_CROSS_EXCLUSION})
BOUNTY_CONFIRMED_KEY = "bounty_confirmed"

# ── CARIMBO com testemunho (regra dos DOIS CARIMBOS, Rui 21 Jul) ──────────────
# `bounty_stamp` regista COMO o Rui carimbou: 'placa' (leu a imagem/digitou) vs
# 'aceitacao' (aceitou a sugestão da máquina). SÓ para carimbos NOVOS — um seat
# selado SEM stamp é legado e trata-se como intocável (a regra PARA TRÁS sai de
# graça: ausência = protegido). Por agora o stamp é só REGISTO; a regra
# "aceitação cede a leitura corrigida" é um passo futuro, não construído.
BOUNTY_STAMP_KEY = "bounty_stamp"
STAMP_PLACA = "placa"
STAMP_ACEITACAO = "aceitacao"
VALID_STAMPS = frozenset({STAMP_PLACA, STAMP_ACEITACAO})


def is_bounty_sealed(seat) -> bool:
    """True se a coroa deste seat foi VALIDADA (carimbo do Rui / cura curada /
    confirmada) → nenhum processo automático a pisa. Cobre `bounty_source` selado
    E o flag `bounty_confirmed` (exceção manual antiga). Fonte única do invariante —
    todos os caminhos automáticos de escrita de coroas consultam esta função."""
    if not isinstance(seat, dict):
        return False
    return (seat.get(BOUNTY_SOURCE_KEY) in SEALED_BOUNTY_SOURCES
            or bool(seat.get(BOUNTY_CONFIRMED_KEY)))


def merge_sealed_crowns_apa(prev_apa, fresh_apa) -> int:
    """Transportador de coroas do apa (irmão por-hash do `_merge_sealed_crowns`
    do players_list) — corre nas RECONSTRUÇÕES do apa (`/set-anon-map` — o lápis
    do nome — e `reenrich_scrambled_gold`) entre o re-parse do raw e o enrich.

    CAUSA que fecha (conceito SELO, 21 Jul): o raw não traz campos de coroa; o
    apa re-parseado nascia "amnésico" → (a) o guard único do enrich
    (`is_bounty_sealed`) via os SELADOS como não-selados e deixava a Vision
    reescrevê-los; (b) os NÃO-selados de um seat cuja grafia não casa no
    players_list caíam no default $0 do ingest. Uma reconstrução NÃO é uma
    leitura nova — não pode esquecer valores ("editar um nome não apaga a coroa
    de ninguém", regra do Rui).

    Transporta os campos de coroa (valor + source + confirmed + stamp) de TODOS
    os seats, por CHAVE (hash GG / "Hero") — imune a grafia. Nos selados limpa
    também os reviews herdados (o selo fecha o "por rever"). Muta `fresh_apa`;
    devolve o nº de seats SELADOS transportados (os que o guard vai defender)."""
    if not isinstance(prev_apa, dict) or not isinstance(fresh_apa, dict):
        return 0
    n_sealed = 0
    for key, prev in prev_apa.items():
        if key == "_meta" or not isinstance(prev, dict):
            continue
        tgt = fresh_apa.get(key)
        if not isinstance(tgt, dict):
            continue
        if "bounty_value_usd" in prev:
            tgt["bounty_value_usd"] = prev.get("bounty_value_usd")
        if prev.get(BOUNTY_SOURCE_KEY) is not None:
            tgt[BOUNTY_SOURCE_KEY] = prev.get(BOUNTY_SOURCE_KEY)
        if prev.get(BOUNTY_CONFIRMED_KEY):
            tgt[BOUNTY_CONFIRMED_KEY] = True
        if prev.get(BOUNTY_STAMP_KEY) is not None:
            tgt[BOUNTY_STAMP_KEY] = prev.get(BOUNTY_STAMP_KEY)
        if is_bounty_sealed(prev):
            tgt.pop("crown_review", None)
            tgt.pop(BOUNTY_REVIEW_KEY, None)
            n_sealed += 1
    return n_sealed

# ── Sinal de ELIMINADO (autoritativo — HH) ───────────────────────────────────
# Linha de acção: "<key>: bets 47,944 and is all-in" (key = hash GG ou "Hero").
# Restrito a UMA linha ([^:\n], [^\n]*) senão [^:]+ engole newlines (bug apanhado 9 Jul).
_ALLIN_RE = re.compile(r"^([^:\n]+):[^\n]*\band is all-in\b", re.M)
# Colecta do pote: "<key> collected 180,816 from pot" (sem ':').
_COLLECT_RE = re.compile(r"^([^\n:]+?) collected [\d,]+", re.M)

# ── ALL-IN por POST FORÇADO (conta, não frase) ────────────────────────────────
# O GG NÃO escreve "and is all-in" quando o stack inteiro se esgota a postar
# ante+cega (o short-stack fica all-in no post da cega, sem linha de acção). Ambos
# os detetores de bust ancoravam na frase → 61 lugares / 50 mãos invisíveis (100%
# deste mecanismo). O sinal que NÃO falha é aritmético: soma do que foi FORÇADO a
# pôr (ante + cegas) >= stack de entrada = all-in. Some-se ao all-in por frase.
_SEAT_STACK_RE = re.compile(r"^Seat \d+: (\S+) \(([\d,]+) in chips\)", re.M)
_POST_RE = re.compile(r"^(\S+): posts (?:the ante|small blind|big blind) ([\d,]+)", re.M)

# ── SOBREVIVEU POR COBRIR (régua do resto-em-BB) ─────────────────────────────
# FONTE ÚNICA do conceito "este jogador morreu?" (#BUST-NO-COVERAGE-GUARD,
# #LEI-FIX-NA-CAUSA). Quem vai all-in com MAIS fichas do que o adversário perde o
# pote mas recebe o excedente de volta ("Uncalled bet (X) returned to <key>") e
# CONTINUA NA MESA. Sem esta régua, "all-in + não coletou" declara-o morto — 1227
# lugares em 1227 mãos GG 2026 (23% dos vereditos), 43 coroas já anuladas sem motivo.
# A régua estava provada e validada pelo Rui na imagem (3/3), mas vivia SÓ no detetor
# do painel (`crown_recovery`), não no que escreve na base. Aqui é que manda.
_BB_RE = re.compile(r"Level\d+\((?:[\d,]+)/([\d,]+)")
_UNCALLED_RE = re.compile(r"Uncalled bet \(([\d,]+)\) returned to (\S+)")
# Resto >= 1 BB = VIVO. Abaixo disso (ou coberto, resto 0) = bust real.
ALIVE_MIN_BB = 1.0


def _hh_int(s) -> int:
    try:
        return int(str(s).replace(",", "").strip())
    except (ValueError, TypeError, AttributeError):
        return 0


def forced_allin_keys(raw: Optional[str]) -> set:
    """Chaves-HH ALL-IN por POST FORÇADO: a soma do que foram OBRIGADOS a pôr
    (ante + cegas) >= o stack com que ENTRARAM na mão → ficaram sem fichas ao
    postar, sem que o GG escreva 'all-in'. É CONTA, não leitura de texto.

    GUARDA (a mais importante): quem postou mas SOBROU stack (posts < stack) NÃO
    entra — perder um pote não é bustar; só é bust quem ficou sem fichas. A conta
    do stack é o que separa as duas coisas."""
    if not raw:
        return set()
    stacks = {m.group(1): _hh_int(m.group(2)) for m in _SEAT_STACK_RE.finditer(raw)}
    posts: dict = {}
    for m in _POST_RE.finditer(raw):
        posts[m.group(1)] = posts.get(m.group(1), 0) + _hh_int(m.group(2))
    return {h for h, st in stacks.items() if st > 0 and posts.get(h, 0) >= st}


def bb_from_hh(raw: Optional[str]):
    """Big blind do header da mão ("Level1(500/1,000(150))" → 1000). None se ilegível."""
    m = _BB_RE.search(raw or "")
    return _hh_int(m.group(1)) if m else None


def returned_by_key(raw: Optional[str]) -> dict:
    """{chave-HH: fichas devolvidas} — quem recebeu 'Uncalled bet returned' cobriu o
    adversário e ficou com esse resto na mesa."""
    return {m.group(2): _hh_int(m.group(1)) for m in _UNCALLED_RE.finditer(raw or "")}


def allin_outcomes(raw: Optional[str]) -> tuple:
    """FONTE ÚNICA de "quem morreu nesta mão?". Devolve `(mortos, vivos_que_perderam)`,
    chaves-da-HH (hash GG / 'Hero'). Autoritativo (HH), independente da Vision.

    Um jogador entra na conta se esteve ALL-IN — frase "and is all-in" OU post forçado
    (ante+cega >= stack, `forced_allin_keys`) — E NÃO coletou nenhum pote.

    Desses, separa-os pela RÉGUA DO RESTO-EM-BB:
    - resto devolvido >= 1 BB (`ALIVE_MIN_BB`) → **VIVO**: cobria o adversário, perdeu o
      pote mas ficou com o excedente. Coroa NULL aqui é leitura falhada (re-ler a placa),
      NUNCA um caso verde-KO.
    - resto < 1 BB (ou 0, coberto) → **MORTO** de verdade.
    - BB ilegível no header → trata-se como MORTO (conservador; comportamento histórico).

    Todos os caminhos — escrita automática de coroas e painéis — usam esta função.
    Ter a régua em duas cópias foi o que produziu o `#BUST-NO-COVERAGE-GUARD`."""
    if not raw:
        return set(), set()
    allin = {m.group(1).strip() for m in _ALLIN_RE.finditer(raw)}
    allin |= forced_allin_keys(raw)                # + all-in por post forçado (conta)
    collected = {m.group(1).strip() for m in _COLLECT_RE.finditer(raw)}
    perdeu = {k for k in allin if k not in collected}
    bb = bb_from_hh(raw)
    if not bb:
        return perdeu, set()                       # sem BB → não se afere sobra; tudo morto
    returned = returned_by_key(raw)
    mortos, vivos = set(), set()
    for k in perdeu:
        resto_bb = returned.get(k, 0) / bb
        (vivos if resto_bb >= ALIVE_MIN_BB else mortos).add(k)
    return mortos, vivos


def busted_keys_from_hh(raw: Optional[str]) -> set:
    """Chaves-da-HH ELIMINADAS nesta mão (só os MORTOS de verdade). Fina camada sobre
    `allin_outcomes` — quem cobriu e sobreviveu fica de fora, como manda a régua do
    resto-em-BB. Todos os call-sites herdam a guarda por aqui, sem alterações."""
    return allin_outcomes(raw)[0]


def busted_real_names(raw: Optional[str], apa: Optional[dict]) -> set:
    """Nomes REAIS dos seats eliminados (mapeia as chaves-HH via apa: real_name || chave)."""
    keys = busted_keys_from_hh(raw)
    if not keys:
        return set()
    key2name = {k: (v.get("real_name") or k)
                for k, v in (apa or {}).items()
                if k != "_meta" and isinstance(v, dict)}
    return {key2name.get(k, k) for k in keys}


# ── Verde-KO (Vision — SHOULD; nunca gate do invariante) ──────────────────────
# Linha do prompt novo: "GREEN_KO: <winner_name> | <value>" (o valor verde na coroa de
# quem elimina = METADE da coroa da vítima → coroa da vítima = verde × 2, ver
# GREEN_TO_CROWN_FACTOR e resolve_seat_bounty).
def parse_green_kos(vision_data: Optional[dict]) -> list:
    """Lista de {winner, value} dos verdes-KO que a Vision emitiu. [] se ausente."""
    out = []
    for g in (vision_data or {}).get("green_kos") or []:
        try:
            val = float(g.get("value"))
        except (TypeError, ValueError):
            continue
        if val > 0:
            out.append({"winner": (g.get("winner") or "").strip(), "value": val})
    return out


def resolve_seat_bounty(
    name: str,
    vision_crown,
    *,
    busted_names: set,
    green_kos: Optional[list] = None,
    bounty_base=None,
    has_ts_no_bounty: bool = False,
) -> tuple:
    """CHOKEPOINT do bounty por-seat. Devolve (value, review_reason, source).

    - Seat NÃO eliminado (VIVO):
        · GUARDA VANILLA (decisão Rui, #SPURIOUS-CROWN-NON-KO): torneio com TS a dizer SEM
          bounty (`has_ts_no_bounty`) → um vivo NÃO pode ter coroa (não há bounty no ecrã)
          → (None, None, None). Mata coroas espúrias/$0 inventadas pela Vision em vanilla.
        · GUARDA VIVO-$0 (decisão Rui): torneio KO (base TS `bounty_base` > 0) + coroa
          lida $0/ausente → NUNCA gravar o $0 silencioso → (None, REVIEW_LIVE_ZERO, None).
          NÃO se deriva da base (o vivo pode ter KOs acumulados → a base subvaloriza;
          ex. GG-6132925926: Hero com 2 KOs = coroa $100, "fresco=base=$50" gravaria errado).
          Valor em falta é honesto; valor inventado é veneno.
        · Sem base e sem TS (formato desconhecido) OU coroa >0 num KO → coroa da Vision
          tal-e-qual (value, None, None); caminho normal INALTERADO (#KO-CROWN-INSTANT-FIX).
    - Seat ELIMINADO (HH) → NUNCA a coroa por-seat da Vision. Se houver exatamente 1
      eliminado E 1 verde → (verde × 2, None, 'green_ko') [coroa da vítima = verde×2,
      GREEN_TO_CROWN_FACTOR; proveniência marcada = crivo].
      Senão (0 verdes, >1 verde, >1 eliminado) → (None, review, None).

    `source` é a marca de proveniência (SOURCE_GREEN_KO só quando derivado do verde);
    o caller grava-a em `bounty_source` do seat. Um bustado com coroa >0 sem esta marca
    é contaminação de origem-Vision (crivo verdadeiro = 0 pós-cura).
    """
    if name not in busted_names:
        # GUARDA VANILLA — TS presente E sem bounty → não há coroa possível → força NULL
        # (mata coroas espúrias/$0 que a Vision inventa num torneio sem bounty).
        if has_ts_no_bounty:
            return None, None, None
        # GUARDA VIVO-$0 — só dispara quando SABEMOS que é KO (base do TS > 0). Sem base
        # E sem TS (formato desconhecido) = passthrough (não se decide às cegas).
        if bounty_base and float(bounty_base) > 0:
            try:
                c = float(vision_crown) if vision_crown is not None else 0.0
            except (TypeError, ValueError):
                c = 0.0
            if c <= 0:
                return None, REVIEW_LIVE_ZERO, None
        return vision_crown, None, None
    greens = green_kos or []
    # Caso limpo (SHOULD): 1 eliminado nesta mão + 1 verde → liga-se sem ambiguidade.
    # FÍSICA DO VERDE (Rui, 20 Jul): o verde na coroa do matador = METADE da coroa da
    # vítima → a coroa da casa (instantâneo) do eliminado = verde × 2 (GREEN_TO_CROWN_FACTOR).
    if len(busted_names) == 1 and len(greens) == 1:
        return round(greens[0]["value"] * GREEN_TO_CROWN_FACTOR, 2), None, SOURCE_GREEN_KO
    if not greens:
        return None, REVIEW_NO_GREEN, None
    return None, REVIEW_AMBIGUOUS, None


def _apply_seat_bounty(seat: dict, val, review, source) -> None:
    """CIRÚRGICO — só toca os 3 campos do bounty; nome/stack/posição/cartas intactos."""
    seat["bounty_value_usd"] = val                 # None (NULL) ou a coroa (verde×2)
    if review:
        seat[BOUNTY_REVIEW_KEY] = review
    else:
        seat.pop(BOUNTY_REVIEW_KEY, None)
    if source:
        seat[BOUNTY_SOURCE_KEY] = source
    else:
        seat.pop(BOUNTY_SOURCE_KEY, None)


def is_tagged(hand: Optional[dict]) -> bool:
    """SÓ-TAGADAS (APA §B.6): mão de estudo = hm3_tags OU discord_tags não-vazias.
    Espelho de name_propagation._is_tagged (fonte única do conceito)."""
    if not hand:
        return False
    return bool(hand.get("hm3_tags")) or bool(hand.get("discord_tags"))


def scrub_eliminated_bounties(apa: Optional[dict], pn: Optional[dict],
                             raw: Optional[str], vision_data: Optional[dict] = None,
                             *, tagged: bool = True, bounty_base=None,
                             has_ts_no_bounty: bool = False) -> int:
    """FUNIL ÚNICO da cura verde-KO. Chamado 1× em cada caminho AUTOMÁTICO que escreve
    bounty por-seat (enrich gold/position_v3, orphan-enrich, table-ss, backfills gold-carry
    e capture, reread). Aplica a guarda aos seats HH-bustados (verde-KO) E aos seats VIVOS:
    - `bounty_base` (buy_in_bounty do TS) > 0 = torneio KO → vivo com coroa $0 → guarda
      vivo-$0 (NULL + REVIEW_LIVE_ZERO);
    - `has_ts_no_bounty` (TS presente e sem bounty = vanilla) → vivo NÃO pode ter coroa →
      força NULL (guarda vanilla, #SPURIOUS-CROWN-NON-KO).
    Em AMBOS apa e pn.players_list. Devolve nº de seats-nome tocados (audit). Muta in-place.

    5 garantias:
    (0) SÓ-TAGADAS: `tagged=False` → NÃO scruba (return 0). O scope do core (APA §B.6) fica
        BAKED-IN no funil; o call-site passa `tagged=is_tagged(hand)`.
    (1) MUST independente do verde: sem `vision_data`/verde (backfills só-apa) → o bustado
        fica NULL + 'por rever' (a anulação vem SÓ do raw/HH).
    (2) raw obrigatório: sem `raw` NÃO se pode computar bust em segurança → NÃO scruba e
        LOGA warning (nunca deixa passar cru em silêncio; o call-site tem de garantir raw).
    (3) CIRÚRGICO: só bounty_value_usd/bounty_review/bounty_source.
    (4) apa↔pn consistente: busted/greens computados UMA vez, aplicados igual aos dois.
    """
    if not tagged:
        return 0
    if not isinstance(apa, dict):
        return 0
    if not raw:
        # Guarantee 2: um call-site sem raw é um buraco — sinaliza, não scruba às cegas.
        logger.warning("scrub_eliminated_bounties: raw ausente — bust não computável; "
                       "call-site tem de fornecer o raw (HH). Skip seguro (sem scrub).")
        return 0
    busted = busted_real_names(raw, apa)            # HH-autoritativo; {} se não há bust
    # guarda dos VIVOS activa quando KO conhecido (base>0) OU vanilla conhecido (TS sem bounty)
    live_guard = bool((bounty_base and float(bounty_base) > 0) or has_ts_no_bounty)
    if not busted and not live_guard:
        return 0
    greens = parse_green_kos(vision_data)           # best-effort; [] se ausente/sem prompt
    touched = 0

    def _handle(seat, name, is_busted):
        """Aplica o chokepoint a um seat (apa ou pn). Devolve 1 se tocou, 0 senão."""
        val, review, source = resolve_seat_bounty(
            name, seat.get("bounty_value_usd"), busted_names=busted,
            green_kos=greens, bounty_base=bounty_base, has_ts_no_bounty=has_ts_no_bounty)
        # SELO (invariante do Rui): um seat validado NÃO é pisado por este funil
        # automático. Excepção única — um green_ko FRESCO refresca um seat selado
        # SÓ por green_ko (comportamento antigo da cura); um selo manual/derived/
        # confirmed é intocável (cobre também o bug do pop-source no ramo vivo).
        if is_bounty_sealed(seat):
            only_green = (seat.get(BOUNTY_SOURCE_KEY) == SOURCE_GREEN_KO
                          and not seat.get(BOUNTY_CONFIRMED_KEY))
            if not (only_green and source == SOURCE_GREEN_KO):
                return 0
        if not is_busted:
            # idempotência: só toca se muda algo (passthrough KO-com-coroa e vanilla-já-limpo
            # não fazem churn; vanilla-com-coroa e vivo-$0 mudam → aplicam).
            cur = (seat.get("bounty_value_usd"), seat.get(BOUNTY_REVIEW_KEY),
                   seat.get(BOUNTY_SOURCE_KEY))
            if (val, review, source) == cur:
                return 0
            _apply_seat_bounty(seat, val, review, source)
            return 1
        _apply_seat_bounty(seat, val, review, source)
        return 1

    for key, entry in apa.items():                  # 1) apa (chave=hash/nick/Hero)
        if key == "_meta" or not isinstance(entry, dict):
            continue
        name = entry.get("real_name") or key
        is_busted = name in busted
        if not is_busted and not live_guard:
            continue                                # vivo e formato desconhecido → nada a fazer
        touched += _handle(entry, name, is_busted)
    for p in (pn or {}).get("players_list") or []:  # 2) pn.players_list (nome='name')
        if not isinstance(p, dict):
            continue
        nm = p.get("name")
        is_busted = nm in busted
        if not is_busted and not live_guard:
            continue
        _handle(p, nm, is_busted)                   # mesmo resultado → apa↔pn coerentes
    return touched


def scrub_and_persist(hand_db_id: int, vision_data: Optional[dict] = None,
                      incoming_folder_tag=None) -> int:
    """Wrapper DB-aware do funil, chamado nos PONTOS DE FINALIZAÇÃO (pós-persist de cada
    caminho automático). Lê apa/pn/raw/tags FRESCOS da mão, aplica o scrub (só-tagadas) e
    reescreve SE mudou. Idempotente → a ordem A/B não importa; correr 2× = mesmo resultado.

    - `tagged = is_tagged(mão) OU incoming_folder_tag` → cobre o 'tagada-depois' (a captura
      que traz a folder-tag torna a mão tagada NESTE momento → o scrub corre já).
    - `vision_data` (com green_kos) só é passado onde há Vision FRESCA (reread, enrich gold)
      → green-fill; senão MUST-only (bustado → NULL + 'por rever').
    - FAIL-SAFE do raw (garantia 2): sem raw NÃO scruba e NÃO escreve — nunca grava uma
      coroa que não consegue verificar (o scrub já devolve 0; aqui não há UPDATE).
    """
    import json as _json
    from app.db import query, get_conn
    # buy_in_bounty do TS (GG) → torneio KO? (guarda vivo-$0). LEFT JOIN: None se não há TS
    # ou não-GG → guarda vivo-$0 NÃO dispara (passthrough), como manda a decisão.
    rows = query("SELECT h.id, h.hand_id, h.raw, h.all_players_actions AS apa, h.player_names AS pn, "
                 "       h.hm3_tags, h.discord_tags, h.site, "
                 "       ts.buy_in_bounty AS bounty_base, "
                 "       (ts.tournament_number IS NOT NULL) AS has_ts "
                 "  FROM hands h "
                 "  LEFT JOIN tournament_summaries ts "
                 "    ON ts.site='GGPoker' AND ts.tournament_number = h.tournament_number "
                 " WHERE h.id = %s", (hand_db_id,))
    if not rows:
        return 0
    r = rows[0]
    tagged = is_tagged(r) or bool(incoming_folder_tag)
    if not tagged:
        return 0                                   # SÓ-TAGADAS: skip total (não escreve)
    if not r.get("raw"):
        return 0                                   # fail-safe: sem raw não se verifica bust
    apa = r["apa"] if isinstance(r["apa"], dict) else _json.loads(r["apa"] or "{}")
    pn = r["pn"] if isinstance(r["pn"], dict) else _json.loads(r["pn"] or "{}")
    base = r.get("bounty_base")
    # vanilla = GG + TS presente + sem bounty → guarda vanilla (coroa forçada a NULL).
    has_ts_no_bounty = (r.get("site") == "GGPoker" and bool(r.get("has_ts"))
                        and not (base and float(base) > 0))
    # RASTO DO SELO (crown_seal_log): este funil é o único caminho AUTOMÁTICO que sela
    # (`green_ko`, derivado do verde). Fotografa-se o ANTES por seat para o rasto saber o
    # valor anterior — os manuais fazem o mesmo nas suas rotas.
    _before = {p.get("name"): (p.get("bounty_value_usd"), p.get(BOUNTY_SOURCE_KEY))
               for p in (pn.get("players_list") or []) if isinstance(p, dict) and p.get("name")}
    n = scrub_eliminated_bounties(apa, pn, r["raw"], vision_data, tagged=True,
                                  bounty_base=base, has_ts_no_bounty=has_ts_no_bounty)
    if n:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE hands SET all_players_actions = %s, player_names = %s "
                            "WHERE id = %s",
                            (_json.dumps(apa), _json.dumps(pn), hand_db_id))
            conn.commit()
        finally:
            conn.close()
        from app.services.crown_seal_log import (
            ORIGIN_SCRUB_GREEN_KO, log_seals, seal_row)
        _rows = []
        for p in (pn.get("players_list") or []):
            if not isinstance(p, dict) or not is_bounty_sealed(p):
                continue                                   # só SELOS entram no rasto
            _old_v, _old_s = _before.get(p.get("name"), (None, None))
            if _old_s == p.get(BOUNTY_SOURCE_KEY) and _old_v == p.get("bounty_value_usd"):
                continue                                   # já estava assim → não é escrita nova
            _rows.append(seal_row(r["hand_id"], p.get("name"), _old_v,
                                  p.get("bounty_value_usd"), old_source=_old_s,
                                  new_source=p.get(BOUNTY_SOURCE_KEY)))
        log_seals(_rows, origin=ORIGIN_SCRUB_GREEN_KO, actor="automatico")
    return n
