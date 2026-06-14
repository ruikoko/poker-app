"""pt72 — pasta-como-tag: testes do sufixo de FASE (-ft) derivado da Vision.

Núcleo puro/testável (sem BD): `_ft_applies` (bancos ocupados == players_left) e
`_final_folder_tag` (base + '-ft' com fail-safe). A aplicação à mão
(`_apply_folder_tag_to_hand`) toca BD → coberta indirectamente / não aqui.
"""
from app.routers.table_ss import _ft_applies, _final_folder_tag


def _seats(n):
    return [{"nick": f"p{i}", "stack_bb": 10.0} for i in range(n)]


# ── _ft_applies ───────────────────────────────────────────────────────────────

def test_ft_true_when_seats_equal_players_left():
    vj = {"seats": _seats(5), "players_left": 5}
    assert _ft_applies(vj) is True


def test_ft_false_when_more_players_left_than_seats():
    vj = {"seats": _seats(5), "players_left": 10}
    assert _ft_applies(vj) is False


def test_ft_false_when_players_left_missing():
    assert _ft_applies({"seats": _seats(5), "players_left": None}) is False
    assert _ft_applies({"seats": _seats(5)}) is False


def test_ft_false_when_no_seats():
    assert _ft_applies({"seats": [], "players_left": 0}) is False
    assert _ft_applies({"seats": [], "players_left": 6}) is False


def test_ft_ignores_seatless_entries_in_count():
    # bancos sem nick não contam como ocupados
    seats = _seats(5) + [{"nick": "", "stack_bb": 3.0}, {"stack_bb": 1.0}]
    assert _ft_applies({"seats": seats, "players_left": 5}) is True


def test_ft_heads_up():
    assert _ft_applies({"seats": _seats(2), "players_left": 2}) is True


def test_ft_false_on_garbage():
    assert _ft_applies(None) is False
    assert _ft_applies({"players_left": True, "seats": _seats(1)}) is False  # bool != int aqui


# ── _final_folder_tag ─────────────────────────────────────────────────────────

def test_final_tag_appends_ft_at_final_table():
    vj = {"seats": _seats(6), "players_left": 6}
    assert _final_folder_tag("icm-pko", vj) == "icm-pko-ft"
    assert _final_folder_tag("pos-nko", vj) == "pos-nko-ft"


def test_final_tag_base_only_when_not_ft():
    vj = {"seats": _seats(6), "players_left": 120}
    assert _final_folder_tag("icm", vj) == "icm"
    assert _final_folder_tag("pos-pko", vj) == "pos-pko"


def test_final_tag_failsafe_uncertain_no_suffix():
    # players_left ausente → sem '-ft' (preferir sem sufixo a sufixo errado)
    assert _final_folder_tag("icm-pko", {"seats": _seats(5)}) == "icm-pko"


def test_final_tag_none_base_returns_none():
    assert _final_folder_tag(None, {"seats": _seats(5), "players_left": 5}) is None
    assert _final_folder_tag("", {"seats": _seats(5), "players_left": 5}) is None
