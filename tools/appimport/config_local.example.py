"""Template para `config_local.py`. Copia este ficheiro como `config_local.py`
e preenche com os teus valores. O `config_local.py` é ignorado pelo git
(ver .gitignore) — nunca commitar.
"""

# Pasta-mãe do import por pasta. O agente cria automaticamente as subpastas
# gg_hh / gg_ts / it / manual (+ done/) aqui dentro na 1ª corrida. Põe os
# ficheiros a importar na subpasta do tipo certo.
PARENT_DIR = r"C:\Users\User\Desktop\poker_import"

# Credenciais da poker app (https://poker-app-production-34a7.up.railway.app) —
# as MESMAS do apphm3.
LOGIN_EMAIL = "rui@example.com"
LOGIN_PASS = "PREENCHER_AQUI"

# (OPCIONAL) Fonte "lobby": pasta de Capturas de Ecrã do Windows, lida
# DIRECTAMENTE (sem mover ficheiros), misturada com outros screenshots. O backend
# decide o que é lobby (não-lobby é ignorado). Comenta/remove para desligar.
# Default típico Windows: a pasta "Capturas de ecrã" dentro de Imagens.
LOBBY_DIR = r"C:\Users\User\Pictures\Screenshots"

# (OPCIONAL) Só processa lobbys com captura (mtime) >= esta data. Evita gastar
# Vision na história toda na 1ª corrida e mantém o scope (o Rui só estuda 2026+).
LOBBY_SINCE = "2026-05-30"

# (OPCIONAL) Fonte "gold": pasta EXTERNA das GOLD IMAGES (a descarga completa da
# mão pelo botão do replayer GG). TODAS as imagens (.png/.jpg) são enviadas para
# /api/screenshots — SEM filtro de mês. Em sucesso o ficheiro é MOVIDO para
# PARENT_DIR/done/gold (sai da pasta de origem). O backend dedupa por file_hash.
# Comenta/remove para desligar.
# ⚠️ USA UMA SUBPASTA DEDICADA, não a raiz de Documents: o read é NÃO-RECURSIVO e
#    envia TODAS as imagens que estiverem nesta pasta — apontar à raiz de Documents
#    arriscava enviar imagens que nada têm a ver com poker. Recomendado: Documents\Gold.
GOLD_DIR = r"C:\Users\User\Documents\Gold"

# (OPCIONAL) JANELA DE DATAS das IMAGENS — aplica-se a it / manual / lobby /
# LOBBY_DIR (NÃO a gg_hh/gg_ts, que entram sempre por inteiro). Conceito
# DIA-DE-JOGO 12:00→12:00 Lisboa: IMPORT_DESDE="2026-06-08" + IMPORT_ATE="2026-06-11"
# cobre os dias-de-jogo de 8 a 11 inclusive. Deixa None (ou comenta) p/ não filtrar.
# A "data" de cada imagem: it = timestamp do NOME; manual/lobby/LOBBY_DIR = mtime.
# Na LOBBY_DIR o piso efectivo é o mais restritivo de LOBBY_SINCE e IMPORT_DESDE.
# As flags --desde / --ate (e os prompts do RunAll) ganham a estes valores.
IMPORT_DESDE = None
IMPORT_ATE = None
