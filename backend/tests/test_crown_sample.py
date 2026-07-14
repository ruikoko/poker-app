"""Amostrador de coroas Gold (#CROWN-SAMPLE-VERIFY) — helpers puros.
O engine (releitura Vision) é I/O; aqui só a lógica de divergência + parse."""
from app.routers import crown_sample as cs


def test_diff_equal_and_wobble():
    assert cs._diff(50.0, 50.0) is False
    assert cs._diff(100.0, 100.5) is False      # <=1% wobble de OCR
    assert cs._diff(100.0, 100.009) is False     # <=abs 0.01
    assert cs._diff(None, None) is False


def test_diff_real_divergences():
    assert cs._diff(50.0, 25.0) is True          # metade (chama vs coroa)
    assert cs._diff(50.0, None) is True           # sumiu na releitura
    assert cs._diff(None, 50.0) is True           # apareceu na releitura
    assert cs._diff(100.0, 130.0) is True         # >1%


def test_crowns_of_reads_players_list():
    pn = {"players_list": [
        {"name": "A", "bounty_value_usd": 50.0},
        {"name": "B", "bounty_value_usd": None},   # sem coroa → ignora
        {"name": "C", "bounty_value_usd": 12.5},
    ]}
    assert cs._crowns_of(pn) == {"A": 50.0, "C": 12.5}


def test_crowns_of_tolerates_json_string_and_empty():
    import json
    assert cs._crowns_of(json.dumps({"players_list": [{"name": "X", "bounty_value_usd": 7}]})) == {"X": 7}
    assert cs._crowns_of(None) == {}
    assert cs._crowns_of("{}") == {}
