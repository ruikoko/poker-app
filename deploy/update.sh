#!/usr/bin/env bash
# deploy/update.sh
#
# Para actualizações após o deploy inicial.
# Corre no VPS como root ou com sudo.
#
# Uso:
#   sudo ./update.sh

set -euo pipefail

APP_DIR="/var/www/pokerapp"
DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$DEPLOY_DIR")"

echo "▸ Actualizar backend…"
rsync -a --exclude='.env' --exclude='venv' --exclude='__pycache__' \
    "${PROJECT_DIR}/backend/" "${APP_DIR}/backend/"
"${APP_DIR}/backend/venv/bin/pip" install -q -r "${APP_DIR}/backend/requirements.txt"

echo "▸ Aplicar schema (idempotente)…"
DB_PASSWORD=$(grep '^DB_PASSWORD=' "${APP_DIR}/backend/.env" | cut -d= -f2-)
PGPASSWORD="${DB_PASSWORD}" psql -U pokerapp -d pokerdb -h localhost \
    -f "${APP_DIR}/backend/schema.sql"

echo "▸ Build do frontend…"
rsync -a "${PROJECT_DIR}/frontend/" "${APP_DIR}/frontend/"
cd "${APP_DIR}/frontend"
npm install -q
npm run build -q

echo "▸ Permissões…"
chown -R www-data:www-data "${APP_DIR}"

echo "▸ Reiniciar backend…"
systemctl restart pokerapp
sleep 2
systemctl is-active pokerapp && echo "  ✓ Backend a correr" || \
    { echo "  ✗ Falhou — ver: journalctl -u pokerapp -n 50"; exit 1; }

echo "▸ Recarregar Nginx…"
nginx -t && systemctl reload nginx

echo "  ✓ Actualização concluída."
