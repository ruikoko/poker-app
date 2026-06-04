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
