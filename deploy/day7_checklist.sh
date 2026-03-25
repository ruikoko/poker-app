# Dia 7 — Checklist de verificação end-to-end
#
# Corre cada secção por ordem.
# Cada passo tem um critério de sucesso explícito.
# "✓" = passou. "✗" = não passou, investigar antes de continuar.

VPS_IP="SEU_IP"          # substituir
APP_URL="http://${VPS_IP}"

# ══════════════════════════════════════════════════════════════
# 1. VERIFICAR QUE A APP ESTÁ A CORRER
# ══════════════════════════════════════════════════════════════

# Backend
curl -s "${APP_URL}/health"
# Esperado: {"status":"ok","db":"connected"}

# Serviços no VPS (correr no VPS via SSH)
sudo systemctl status pokerapp --no-pager
sudo systemctl status nginx    --no-pager
# Esperado: Active: active (running)

# ══════════════════════════════════════════════════════════════
# 2. FLUXO NO BROWSER (manual)
# ══════════════════════════════════════════════════════════════
#
# 2.1  Abrir http://SEU_IP no browser
#      ✓ Redireccionado para /login
#
# 2.2  Login com as credenciais criadas
#      ✓ Entra no Dashboard
#
# 2.3  Dashboard mostra tabela de salas
#      (vazia se ainda não importaste — normal)
#
# 2.4  Navegar para P&L
#      ✓ Página carrega sem erro
#
# 2.5  Navegar para Mãos e Vilões
#      ✓ Páginas carregam sem erro
#
# 2.6  Testar logout
#      ✓ Redireccionado para /login
#      ✓ Aceder a /pnl sem login → volta para /login

# ══════════════════════════════════════════════════════════════
# 3. PRIMEIRO UTILIZADOR (se ainda não criado)
# ══════════════════════════════════════════════════════════════

curl -s -X POST "${APP_URL}/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"tu@exemplo.com","password":"password_forte"}'
# Esperado: {"ok":true,"email":"tu@exemplo.com"}
#
# Depois do primeiro utilizador estar criado,
# podes comentar o router de register em app/main.py
# para não deixar o endpoint aberto.

# ══════════════════════════════════════════════════════════════
# 4. BACKUP — CORRER E TESTAR RESTORE
# ══════════════════════════════════════════════════════════════

# No VPS:

# 4.1 Correr backup manualmente (primeira vez)
DB_PASSWORD=$(grep '^DB_PASSWORD=' /var/www/pokerapp/backend/.env | cut -d= -f2-)
DB_PASSWORD="${DB_PASSWORD}" bash /var/www/pokerapp/deploy/backup.sh

# Verificar que o ficheiro existe
ls -lh /var/backups/pokerapp/
# Esperado: pokerdb_YYYYMMDD_HHMMSS.sql.gz  com tamanho > 0

# 4.2 Testar restore
bash /var/www/pokerapp/deploy/test_restore.sh
# Esperado:
#   ✓ Backup verificado e restaurável.
#   Registos por tabela (podem ser 0 se ainda não importaste)

# ══════════════════════════════════════════════════════════════
# 5. CARGA INICIAL DOS 1.777 TORNEIOS
# ══════════════════════════════════════════════════════════════
#
# Corre na máquina onde os ficheiros estão (não no VPS).
# Os ficheiros ZIP/TXT devem estar numa pasta local.

bash deploy/load_initial_data.sh \
  --url "http://${VPS_IP}" \
  --email "tu@exemplo.com" \
  --password "password_forte" \
  --dir "/caminho/local/para/os/ficheiros"

# Registar aqui o output:
#   Ficheiros processados : ___
#   Torneios encontrados  : ___
#   Inseridos             : ___
#   Duplicados ignorados  : ___
#   Erros de parse        : ___
#   Ficheiros com falha   : ___

# 5.1 Verificar na BD (no VPS)
DB_PASSWORD=$(grep '^DB_PASSWORD=' /var/www/pokerapp/backend/.env | cut -d= -f2-)
PGPASSWORD="${DB_PASSWORD}" psql -U pokerapp -d pokerdb -h localhost << 'SQL'
SELECT
    site,
    currency,
    COUNT(*)          AS total,
    SUM(result)       AS profit,
    MIN(date)         AS primeiro,
    MAX(date)         AS ultimo
FROM tournaments
GROUP BY site, currency
ORDER BY site;
SQL

# 5.2 Verificar via API
curl -s "${APP_URL}/api/tournaments/summary" \
  -b <(curl -sc /tmp/ck -X POST "${APP_URL}/api/auth/login" \
        -H "Content-Type: application/json" \
        -d '{"email":"tu@exemplo.com","password":"password_forte"}' > /dev/null; cat /tmp/ck)
# Alternativa mais simples: verificar no browser em Dashboard

# ══════════════════════════════════════════════════════════════
# 6. VERIFICAR LOGS DE IMPORT
# ══════════════════════════════════════════════════════════════

# Na BD (no VPS)
DB_PASSWORD=$(grep '^DB_PASSWORD=' /var/www/pokerapp/backend/.env | cut -d= -f2-)
PGPASSWORD="${DB_PASSWORD}" psql -U pokerapp -d pokerdb -h localhost << 'SQL'
SELECT
    id,
    site,
    filename,
    status,
    records_found,
    records_ok      AS inseridos,
    records_skipped AS duplicados,
    records_error   AS erros,
    imported_at
FROM import_logs
ORDER BY imported_at DESC
LIMIT 20;
SQL

# ══════════════════════════════════════════════════════════════
# 7. CRITÉRIO DE "SEMANA CONCLUÍDA"
# ══════════════════════════════════════════════════════════════
#
# ✓ curl /health devolve {"status":"ok","db":"connected"}
# ✓ Login funciona no browser por IP
# ✓ Dashboard mostra dados reais por sala
# ✓ P&L filtra e pagina correctamente
# ✓ Import de ficheiro real funcionou sem crash
# ✓ backup.sh correu com sucesso e gerou ficheiro
# ✓ test_restore.sh confirmou que o backup é restaurável
# ✓ Máquina de jogo só precisa de browser + URL para usar a app

# ══════════════════════════════════════════════════════════════
# 8. PASSOS SEGUINTES (fora desta semana)
# ══════════════════════════════════════════════════════════════
#
# - Domínio + HTTPS (certbot):
#     sudo certbot --nginx -d exemplo.com
#     Editar .env: ENV=production, ALLOWED_ORIGIN=https://exemplo.com
#     sudo systemctl restart pokerapp
#
# - Fechar endpoint /register depois do primeiro utilizador criado
#
# - Import de PokerStars e WPN (parsers no Dia 8+)
#
# - Gráficos no P&L (Chart.js, linha cumulativa)
#
# - Import de hand histories para secção Mãos
