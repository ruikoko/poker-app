#!/usr/bin/env bash
# deploy/deploy.sh
#
# Script de deploy para Ubuntu 22.04+
# Corre UMA VEZ num VPS limpo como root ou com sudo.
# Para actualizações posteriores: ver secção UPDATE no fundo.
#
# Uso:
#   chmod +x deploy.sh
#   sudo ./deploy.sh
#
# ⚠️  NÃO CORRER NA MÁQUINA DE JOGO.
#     Este script instala servidores e processos em background.
#     Destino: VPS Ubuntu, acessível por browser + URL.

set -euo pipefail

APP_DIR="/var/www/pokerapp"
DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$DEPLOY_DIR")"

echo "═══════════════════════════════════════"
echo "  Poker App — Deploy inicial"
echo "  Destino: ${APP_DIR}"
echo "═══════════════════════════════════════"
echo ""

# ── 1. Sistema ────────────────────────────────────────────────────────────────
echo "▸ 1/8 Actualizar sistema…"
apt-get update -q
apt-get install -y -q \
    python3 python3-pip python3-venv \
    postgresql postgresql-contrib \
    nginx \
    certbot python3-certbot-nginx \
    curl git

# ── 2. PostgreSQL ─────────────────────────────────────────────────────────────
echo "▸ 2/8 Configurar PostgreSQL…"
systemctl enable postgresql
systemctl start postgresql

# Ler password do .env se existir
ENV_FILE="${PROJECT_DIR}/backend/.env"
if [ -f "$ENV_FILE" ]; then
    DB_PASSWORD=$(grep '^DB_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)
else
    echo "ERRO: ${ENV_FILE} não encontrado. Copia .env.example para .env e preenche."
    exit 1
fi

sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='pokerapp'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER pokerapp WITH PASSWORD '${DB_PASSWORD}';"

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='pokerdb'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE pokerdb OWNER pokerapp;"

sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE pokerdb TO pokerapp;"

# Aplicar schema
echo "▸ Aplicar schema…"
PGPASSWORD="${DB_PASSWORD}" psql -U pokerapp -d pokerdb -h localhost \
    -f "${PROJECT_DIR}/backend/schema.sql"

# ── 3. Copiar ficheiros ───────────────────────────────────────────────────────
echo "▸ 3/8 Copiar ficheiros para ${APP_DIR}…"
mkdir -p "${APP_DIR}/backend" "${APP_DIR}/frontend"
rsync -a --exclude='.env' --exclude='venv' --exclude='__pycache__' \
    "${PROJECT_DIR}/backend/" "${APP_DIR}/backend/"

# .env já deve estar preenchido pelo utilizador
if [ ! -f "${APP_DIR}/backend/.env" ]; then
    cp "${PROJECT_DIR}/backend/.env" "${APP_DIR}/backend/.env" 2>/dev/null || \
        { echo "ERRO: preenche ${APP_DIR}/backend/.env antes de continuar"; exit 1; }
fi

# ── 4. Python venv ────────────────────────────────────────────────────────────
echo "▸ 4/8 Instalar dependências Python…"
python3 -m venv "${APP_DIR}/backend/venv"
"${APP_DIR}/backend/venv/bin/pip" install -q --upgrade pip
"${APP_DIR}/backend/venv/bin/pip" install -q -r "${APP_DIR}/backend/requirements.txt"

# ── 5. Frontend ───────────────────────────────────────────────────────────────
echo "▸ 5/8 Build do frontend…"
if ! command -v node &>/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y -q nodejs
fi

rsync -a "${PROJECT_DIR}/frontend/" "${APP_DIR}/frontend/"
cd "${APP_DIR}/frontend"
npm install -q
npm run build -q

# ── 6. Permissões ─────────────────────────────────────────────────────────────
echo "▸ 6/8 Permissões…"
chown -R www-data:www-data "${APP_DIR}"
chmod 600 "${APP_DIR}/backend/.env"

# ── 7. Systemd ────────────────────────────────────────────────────────────────
echo "▸ 7/8 Instalar serviço systemd…"
cp "${DEPLOY_DIR}/pokerapp.service" /etc/systemd/system/pokerapp.service
systemctl daemon-reload
systemctl enable pokerapp
systemctl restart pokerapp
sleep 2
systemctl is-active pokerapp && echo "  ✓ Backend a correr" || \
    { echo "  ✗ Backend falhou — ver: journalctl -u pokerapp -n 50"; exit 1; }

# ── 8. Nginx ──────────────────────────────────────────────────────────────────
echo "▸ 8/8 Configurar Nginx…"
cp "${DEPLOY_DIR}/nginx.conf" /etc/nginx/sites-available/pokerapp
ln -sf /etc/nginx/sites-available/pokerapp /etc/nginx/sites-enabled/pokerapp
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx
systemctl reload nginx

# ── Backup ────────────────────────────────────────────────────────────────────
echo "▸ Instalar cron de backup…"
mkdir -p /var/backups/pokerapp
cp "${DEPLOY_DIR}/backup.sh" "${APP_DIR}/deploy/backup.sh"
chmod +x "${APP_DIR}/deploy/backup.sh"

# Backup diário às 3h da manhã
CRON_LINE="0 3 * * * DB_PASSWORD='${DB_PASSWORD}' ${APP_DIR}/deploy/backup.sh >> /var/log/pokerapp_backup.log 2>&1"
(crontab -l 2>/dev/null | grep -v 'pokerapp_backup\|backup.sh'; echo "$CRON_LINE") | crontab -

echo ""
echo "═══════════════════════════════════════"
echo "  Deploy concluído."
echo ""
SERVER_IP=$(hostname -I | awk '{print $1}')
echo "  App:     http://${SERVER_IP}"
echo "  Backend: http://${SERVER_IP}/health"
echo ""
echo "  Para HTTPS quando tiveres domínio:"
echo "    1. Editar /etc/nginx/sites-available/pokerapp"
echo "       server_name exemplo.com;"
echo "    2. sudo certbot --nginx -d exemplo.com"
echo "    3. Editar ${APP_DIR}/backend/.env"
echo "       ENV=production"
echo "       ALLOWED_ORIGIN=https://exemplo.com"
echo "    4. sudo systemctl restart pokerapp nginx"
echo "═══════════════════════════════════════"
