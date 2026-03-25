#!/usr/bin/env bash
# /var/www/pokerapp/deploy/backup.sh
#
# Corre via cron — ver deploy.sh para instalação
# Guarda backups em /var/backups/pokerapp/
# Mantém os últimos 30 dias
# Para restaurar: gunzip -c ficheiro.sql.gz | psql -U pokerapp -d pokerdb

set -euo pipefail

BACKUP_DIR="/var/backups/pokerapp"
DB_NAME="pokerdb"
DB_USER="pokerapp"
DB_HOST="localhost"
KEEP_DAYS=30
DATE=$(date +%Y%m%d_%H%M%S)
OUTFILE="${BACKUP_DIR}/pokerdb_${DATE}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] A fazer backup de ${DB_NAME}…"

PGPASSWORD="${DB_PASSWORD:-}" pg_dump \
    -U "$DB_USER" \
    -h "$DB_HOST" \
    -d "$DB_NAME" \
    --no-owner \
    --no-acl \
    | gzip > "$OUTFILE"

SIZE=$(du -sh "$OUTFILE" | cut -f1)
echo "[$(date)] Backup guardado: ${OUTFILE} (${SIZE})"

# Apagar backups com mais de KEEP_DAYS dias
DELETED=$(find "$BACKUP_DIR" -name "pokerdb_*.sql.gz" -mtime +${KEEP_DAYS} -print -delete | wc -l)
if [ "$DELETED" -gt 0 ]; then
    echo "[$(date)] ${DELETED} backup(s) antigo(s) apagado(s)"
fi

echo "[$(date)] Concluído."
