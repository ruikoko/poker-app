"""RÉGUA ÚNICA «quantos jogadores restam no torneio à hora desta mão?»
(`services/players_left`, 23 Jul, #LEI-FIX-NA-CAUSA).

Régua: captura da PRÓPRIA mão → senão print de lobby MAIS PRÓXIMO NO TEMPO →
senão (None, None) honesto. Zero-lido = desconhecido. As 2 cópias antigas
(`queue_export._resolve_players_left`, `hrc_queue.lookup_players_left`) são
camadas finas — provado aqui pela delegação."""
import datetime as dt

import app.services.players_left as PL


def T(h, m):
    return dt.datetime(2026, 7, 2, h, m)


def _q(captures=None, prints=None):
    def q(sql, params=None):
        if "table_ss_processing_log" in sql:
            return captures or []
        if "lobby_processing_log" in sql:
            return prints or []
        return []
    return q


_PRINTS_6139792066 = [   # forma real do caso ferido (mão 23:02)
    {"tournament_number": "295252423", "posted_at": T(21, 15), "players_left": 167},
    {"tournament_number": "295252423", "posted_at": T(23, 6), "players_left": 34},
    {"tournament_number": "295252423", "posted_at": T(23, 15), "players_left": 22},
]


def test_capture_of_own_hand_wins(monkeypatch):
    monkeypatch.setattr("app.db.query", _q(
        captures=[{"id": 12, "players_left": 203}],
        prints=[{"tournament_number": "T1", "posted_at": T(17, 44), "players_left": 60}]))
    out = PL.resolve_players_left_batch([{
        "id": 1, "context_table_ss_id": 12, "tournament_number": "T1",
        "played_at": T(17, 15)}])
    assert out[1] == (203, PL.SOURCE_CAPTURE)


def test_lobby_closest_not_most_recent(monkeypatch):
    """★ O coração do fix: mão 23:02 → print 23:06 (34), nunca o 23:15 (22)."""
    monkeypatch.setattr("app.db.query", _q(prints=_PRINTS_6139792066))
    out = PL.resolve_players_left_batch([{
        "id": 7, "context_table_ss_id": None,
        "tournament_number": "295252423", "played_at": T(23, 2)}])
    assert out[7] == (34, PL.SOURCE_LOBBY)


def test_zero_capture_is_unknown_falls_to_lobby(monkeypatch):
    """Captura com 0 lido (não devia vir da query, mas o guard defende): 0 é
    desconhecido → cai ao print mais próximo."""
    monkeypatch.setattr("app.db.query", _q(
        captures=[{"id": 12, "players_left": 0}],
        prints=[{"tournament_number": "T1", "posted_at": T(18, 0), "players_left": 90}]))
    out = PL.resolve_players_left_batch([{
        "id": 1, "context_table_ss_id": 12, "tournament_number": "T1",
        "played_at": T(18, 5)}])
    assert out[1] == (90, PL.SOURCE_LOBBY)


def test_no_sources_honest_none(monkeypatch):
    monkeypatch.setattr("app.db.query", _q())
    out = PL.resolve_players_left_batch([{
        "id": 1, "context_table_ss_id": None,
        "tournament_number": "T1", "played_at": T(18, 5)}])
    assert out[1] == (None, None)


def test_no_played_at_with_prints_is_unknown(monkeypatch):
    """Sem hora da mão não há «mais próximo» — adivinhar (o mais recente) era o
    defeito antigo. Vazio honesto."""
    monkeypatch.setattr("app.db.query", _q(prints=_PRINTS_6139792066))
    out = PL.resolve_players_left_batch([{
        "id": 1, "context_table_ss_id": None,
        "tournament_number": "295252423", "played_at": None}])
    assert out[1] == (None, None)


def test_batch_same_tournament_hands_get_own_values(monkeypatch):
    """Mata o achatamento por torneio do painel antigo (DISTINCT ON tn → o mesmo
    número em todas as mãos): cada mão leva o print mais próximo DELA."""
    prints = [
        {"tournament_number": "T1", "posted_at": T(18, 0), "players_left": 100},
        {"tournament_number": "T1", "posted_at": T(19, 0), "players_left": 50},
    ]
    monkeypatch.setattr("app.db.query", _q(prints=prints))
    rows = [
        {"id": 1, "context_table_ss_id": None, "tournament_number": "T1", "played_at": T(18, 5)},
        {"id": 2, "context_table_ss_id": None, "tournament_number": "T1", "played_at": T(18, 58)},
    ]
    out = PL.resolve_players_left_batch(rows)
    assert out[1] == (100, PL.SOURCE_LOBBY)
    assert out[2] == (50, PL.SOURCE_LOBBY)


def test_db_error_returns_nones(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db down")
    monkeypatch.setattr("app.db.query", boom)
    out = PL.resolve_players_left_batch([{
        "id": 1, "context_table_ss_id": 3, "tournament_number": "T1",
        "played_at": T(18, 5)}])
    assert out[1] == (None, None)


def test_posted_at_tz_mislabel_normalized(monkeypatch):
    """O posted_at do lobby vem com marca +00 enganadora (wall-clock Lisboa) —
    a régua compara em wall-clock, sem rebentar com o played_at naive."""
    prints = [{"tournament_number": "T1",
               "posted_at": T(18, 0).replace(tzinfo=dt.timezone.utc),
               "players_left": 77}]
    monkeypatch.setattr("app.db.query", _q(prints=prints))
    out = PL.resolve_players_left_batch([{
        "id": 1, "context_table_ss_id": None, "tournament_number": "T1",
        "played_at": T(18, 3)}])
    assert out[1] == (77, PL.SOURCE_LOBBY)


# ── as 2 cópias antigas são camadas finas (LEI 2/3) ──────────────────────────
def test_hrc_queue_lookup_delegates_to_single_rule(monkeypatch):
    from app.services.hrc_queue import lookup_players_left
    monkeypatch.setattr("app.db.query", _q(prints=_PRINTS_6139792066))
    out = lookup_players_left([{
        "id": 9, "context_table_ss_id": None,
        "tournament_number": "295252423", "played_at": T(23, 2)}])
    assert out[9] == (34, PL.SOURCE_LOBBY)   # mesmíssima régua (não «mais recente»)


def test_queue_export_delegates_to_single_rule(monkeypatch):
    from app.services.queue_export import _resolve_players_left
    monkeypatch.setattr("app.db.query", _q(
        captures=[{"id": 5, "players_left": 68}]))
    assert _resolve_players_left(
        {"context_table_ss_id": 5, "tournament_number": "X",
         "played_at": T(18, 16)}, None) == 68
