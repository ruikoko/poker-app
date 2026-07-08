"""#DESANON-SITTING-OUT-NPLUS1 — guarda universal de consistência de desanon.
Regressão do caso real GG-6083771298 (Afonso Neto sentado-sem-cartas, N+1). Ver
DESANON_ANATOMIA §3.2.4."""
from app.services.table_ss_deanon import assert_deanon_consistency

H1, H2, H3, H4 = "1a2b3c4d", "2b3c4d5e", "3c4d5e6f", "4d5e6f70"

# HH de 5 lugares: 4 hashes anón + Hero (5 Seat lines).
_RAW = (
    "Poker Hand #x\nTable '1' 6-max Seat #1 is the button\n"
    f"Seat 1: {H1} (1000 in chips)\n"
    f"Seat 2: {H2} (1000 in chips)\n"
    f"Seat 3: {H3} (1000 in chips)\n"    # SB = CORDEIRODEDEUS
    f"Seat 4: {H4} (1000 in chips)\n"
    "Seat 5: Hero (1000 in chips)\n"
)
_ANON = {H1: "A", H2: "B", H3: "CORDEIRODEDEUS", H4: "D"}


def _healthy_apa():
    return {
        "_meta": {"bb": 100},
        H1: {"real_name": "A"}, H2: {"real_name": "B"},
        H3: {"real_name": "CORDEIRODEDEUS"}, H4: {"real_name": "D"},
        "Hero": {"is_hero": True, "real_name": "Lauro Dermio"},
    }


def test_healthy_hand_ok():
    lvl, viols = assert_deanon_consistency(_RAW, _healthy_apa(), _ANON)
    assert lvl == "ok" and viols == []


# Raw REAL tem secção *** SUMMARY *** que REPETE "Seat N: …" (folded/showed). O
# seat_count tem de contar seats DISTINTOS, não linhas — senão conta 5+5=10 e o C0
# bloqueia toda a mão com resumo (regressão apanhada no reimport, Cano 3).
_RAW_WITH_SUMMARY = _RAW + (
    "*** HOLE CARDS ***\n"
    f"{H1}: folds\n"
    "Hero: raises 200 to 300\n"
    "*** SUMMARY ***\n"
    "Total pot 500 | Rake 0\n"
    f"Seat 1: {H1} folded before Flop\n"
    f"Seat 2: {H2} folded before Flop\n"
    f"Seat 3: {H3} (small blind) folded before Flop\n"
    f"Seat 4: {H4} (big blind) showed [As 3c] and won (500)\n"
    "Seat 5: Hero (button) folded before Flop\n"
)


def test_healthy_hand_with_summary_section_ok():
    # 5 seats no cabeçalho + 5 repetidos no SUMMARY = 10 linhas 'Seat N:', mas 5 DISTINTOS.
    # Antes do fix: seat_count=10 != apa5 → 'block' (count:apa5_ne_hh10). Com o fix: 'ok'.
    lvl, viols = assert_deanon_consistency(_RAW_WITH_SUMMARY, _healthy_apa(), _ANON)
    assert lvl == "ok", f"guarda bloqueou uma mão sã com SUMMARY: {viols}"
    assert viols == []


def test_gg_6083771298_afonso_n_plus_1_blocks():
    # §3.2.4: Afonso Neto INJETADO, SB (CORDEIRODEDEUS) PERDIDO, seat colapsado 5→4.
    corrupt = {
        "_meta": {"bb": 100},
        H1: {"real_name": "A"}, H2: {"real_name": "B"},
        H4: {"real_name": "Afonso Neto"},              # injetado (não pertence à mão)
        "Hero": {"is_hero": True, "real_name": "Lauro Dermio"},
    }
    lvl, viols = assert_deanon_consistency(_RAW, corrupt, _ANON)
    assert lvl == "block"
    j = ";".join(viols)
    assert "count:apa4_ne_hh5" in j              # contagem colapsada
    assert "Afonso Neto" in j                    # nome injetado
    assert "CORDEIRODEDEUS" in j                 # SB perdido


def test_duplicate_name_blocks():
    apa = _healthy_apa()
    apa[H4]["real_name"] = "A"                   # 2 seats com o mesmo nome
    lvl, viols = assert_deanon_consistency(_RAW, apa, {**_ANON, H4: "A"})
    assert lvl == "block" and any("dup_name:A" in v for v in viols)


def test_img_ne_hh_blocks_by_order():
    # a Vision leu 6 (N+1) mas a HH tem 5; caminho por ORDEM/STACK → bloqueia
    lvl, viols = assert_deanon_consistency(
        _RAW, _healthy_apa(), _ANON, vision_seat_count=6, by_order=True)
    assert lvl == "block" and any("img6_ne_hh5" in v for v in viols)


def test_img_ne_hh_position_v3_exempt():
    # mesmo N+1, mas position_v3 (por RÓTULO) → isento do C3 (larga o extra), passa
    lvl, viols = assert_deanon_consistency(
        _RAW, _healthy_apa(), _ANON, vision_seat_count=6, by_order=False)
    assert lvl == "ok"


def test_unmapped_seat_is_alarm_not_block():
    # um hash sem nome no anon_map → branco honesto (alarme, não veneno)
    apa = _healthy_apa()
    apa[H4] = {"real_name": ""}                  # por mapear (mantém o hash)
    lvl, viols = assert_deanon_consistency(_RAW, apa, {H1: "A", H2: "B", H3: "CORDEIRODEDEUS"})
    assert lvl == "alarm" and any("unmapped" in v for v in viols)


def test_name_keyed_legacy_healthy_ok():
    # apa LEGADO name-keyed (chave = nome; sem real_name) — o leitor usa real_name || chave
    legacy = {"_meta": {}, "A": {}, "B": {}, "CORDEIRODEDEUS": {}, "D": {},
              "Hero": {"is_hero": True, "real_name": "Lauro Dermio"}}
    lvl, viols = assert_deanon_consistency(_RAW, legacy, _ANON)
    assert lvl == "ok"
