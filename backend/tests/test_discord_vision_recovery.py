"""#DISCORD-VISION-NO-RECOVERY (pt43) — guarda do predicado do step 4b de
sync_and_process: o SELECT de recuperação tem de apanhar replayer_links com
vision_done NULL E =false (antes era só IS NULL -> os =false ficavam em limbo).

Sem DB: o repo não tem harness DB (todos os testes mockam `query`), e o step 4b
está embebido numa função async pesada. A mudança real é puramente no predicado
SQL — por isso o teste assere a semântica do SQL extraído para constante."""
from app.routers.discord import _RECOVERY_REPLAYER_SQL


def test_recovery_sql_catches_null_and_false():
    sql = _RECOVERY_REPLAYER_SQL
    # Predicado alargado: apanha NULL E 'false' (não-true).
    assert "(raw_json->>'vision_done') IS DISTINCT FROM 'true'" in sql
    # Regressão-guard: já não usa a forma estreita antiga que deixava =false fora.
    assert "(raw_json->>'vision_done') IS NULL" not in sql


def test_recovery_sql_scope_unchanged():
    sql = _RECOVERY_REPLAYER_SQL
    # Continua restrito a replayer_link Discord GG com imagem já extraída.
    assert "entry_type = 'replayer_link'" in sql
    assert "source = 'discord'" in sql
    assert "site = 'GGPoker'" in sql
    assert "(raw_json->>'img_b64') IS NOT NULL" in sql
