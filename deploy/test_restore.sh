#!/usr/bin/env bash
# deploy/test_restore.sh
#
# Prova que o último backup é restaurável.
# Restaura para uma base de dados temporária, conta registos, apaga.
# NÃO toca na base de dados de produção.
#
# Uso: sudo -u www-data bash deploy/test_restore.sh
# Ou:  sudo bash deploy/test_restore.sh

set -euo pipefail

BACKUP_DIR="/var/backups/pokerapp"
TEST_DB="pokerdb_restore_test"
DB_USER="pokerapp"
DB_HOST="localhost"

# Ler password do .env
ENV_FILE="/var/www/pokerapp/backend/.env"
DB_PASSWORD=$(grep '^DB_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)

echo "═══════════════════════════════════════"
echo "  Teste de restore do backup"
echo "═══════════════════════════════════════"

# Encontrar backup mais recente
LATEST=$(ls -t "${BACKUP_DIR}"/pokerdb_*.sql.gz 2>/dev/null | head -1)
if [ -z "$LATEST" ]; then
    echo "ERRO: Nenhum backup encontrado em ${BACKUP_DIR}"
    echo "Corre primeiro: bash deploy/backup.sh"
    exit 1
fi

SIZE=$(du -sh "$LATEST" | cut -f1)
echo "Backup: ${LATEST} (${SIZE})"
echo ""

# Criar base de dados de teste
echo "▸ Criar base de dados de teste: ${TEST_DB}…"
sudo -u postgres psql -c "DROP DATABASE IF EXISTS ${TEST_DB};" 2>/dev/null
sudo -u postgres psql -c "CREATE DATABASE ${TEST_DB} OWNER ${DB_USER};"

# Restaurar
echo "▸ Restaurar backup…"
START=$(date +%s)
PGPASSWORD="${DB_PASSWORD}" gunzip -c "$LATEST" | \
    psql -U "$DB_USER" -h "$DB_HOST" -d "$TEST_DB" -q
END=$(date +%s)
echo "  Restauro concluído em $((END - START))s"

# Contar registos
echo ""
echo "▸ Registos restaurados:"
PGPASSWORD="${DB_PASSWORD}" psql -U "$DB_USER" -h "$DB_HOST" -d "$TEST_DB" -t << 'SQL'
SELECT
    'tournaments'   AS tabela, COUNT(*) AS registos FROM tournaments
UNION ALL SELECT
    'hands',                   COUNT(*) FROM hands
UNION ALL SELECT
    'villain_notes',           COUNT(*) FROM villain_notes
UNION ALL SELECT
    'import_logs',             COUNT(*) FROM import_logs
UNION ALL SELECT
    'users',                   COUNT(*) FROM users
ORDER BY tabela;
SQL

# Limpar
echo ""
echo "▸ Apagar base de dados de teste…"
sudo -u postgres psql -c "DROP DATABASE ${TEST_DB};"

echo ""
echo "═══════════════════════════════════════"
echo "  ✓ Backup verificado e restaurável."
echo "  Ficheiro: ${LATEST}"
echo "═══════════════════════════════════════"
