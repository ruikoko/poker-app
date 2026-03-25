# poker-app

> ⚠️ **REGRA ABSOLUTA — LER ANTES DE QUALQUER COISA**
>
> **Esta aplicação NÃO deve ser desenvolvida, testada ou executada na máquina usada para jogar poker.**
>
> - A máquina de jogo é **browser + URL**. Nada mais.
> - Deploy, administração, imports, testes e runtime vivem **fora** da máquina de jogo — no VPS.
> - Qualquer servidor local, script de background ou processo Python na máquina de jogo é uma violação desta regra.

Backend FastAPI + PostgreSQL. Deploy em Ubuntu VPS.

---

## 1. VPS — Setup inicial (Ubuntu 22.04+)

```bash
# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar dependências
sudo apt install -y python3 python3-pip python3-venv postgresql nginx certbot python3-certbot-nginx

# Verificar PostgreSQL
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

---

## 2. PostgreSQL — Criar base de dados e utilizador

```bash
sudo -u postgres psql <<EOF
CREATE USER pokerapp WITH PASSWORD 'CHANGE_ME';
CREATE DATABASE pokerdb OWNER pokerapp;
GRANT ALL PRIVILEGES ON DATABASE pokerdb TO pokerapp;
EOF

# Aplicar schema
psql -U pokerapp -d pokerdb -h localhost -f backend/schema.sql
```

---

## 3. Backend — Instalar e configurar

```bash
cd /var/www/poker-app/backend   # ou o caminho que escolheres

# Ambiente virtual
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Variáveis de ambiente
cp .env.example .env
# Editar .env com os valores reais:
#   DB_PASSWORD, SESSION_SECRET, ALLOWED_ORIGIN
nano .env

# Gerar SESSION_SECRET:
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## 4. Correr o backend

```bash
# Desenvolvimento / teste
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Verificar
curl http://localhost:8000/health
```

---

## 5. Systemd service (produção)

Criar `/etc/systemd/system/pokerapp.service`:

```ini
[Unit]
Description=Poker App API
After=network.target postgresql.service

[Service]
User=www-data
WorkingDirectory=/var/www/poker-app/backend
Environment="PATH=/var/www/poker-app/backend/venv/bin"
ExecStart=/var/www/poker-app/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable pokerapp
sudo systemctl start pokerapp
sudo systemctl status pokerapp
```

---

## 6. Nginx (quando estiver pronto)

```nginx
server {
    listen 80;
    server_name SEU_DOMINIO.com;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        root /var/www/poker-app/frontend/dist;
        try_files $uri $uri/ /index.html;
    }
}
```

```bash
# HTTPS com Let's Encrypt
sudo certbot --nginx -d SEU_DOMINIO.com
```

---

## 7. Backup PostgreSQL (cron diário)

```bash
# Adicionar a crontab do root ou www-data
crontab -e

# Linha a adicionar (backup às 3h da manhã):
0 3 * * * pg_dump -U pokerapp -d pokerdb -h localhost | gzip > /var/backups/pokerdb_$(date +\%Y\%m\%d).sql.gz

# Manter apenas os últimos 30 dias
0 4 * * * find /var/backups/ -name "pokerdb_*.sql.gz" -mtime +30 -delete
```

---

## 8. Primeiro utilizador

```bash
# Via API (uma vez)
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"tu@exemplo.com","password":"password_forte_aqui"}'

# Depois de criar o primeiro utilizador,
# podes desactivar o endpoint /register em produção
# comentando o router em app/main.py se quiseres.
```

---

## Endpoints disponíveis no Dia 1

| Método | URL | Auth | Descrição |
|--------|-----|------|-----------|
| GET | `/health` | Não | Estado da API e ligação à BD |
| GET | `/` | Não | Info da versão |
| POST | `/api/auth/register` | Não | Criar primeiro utilizador |
| POST | `/api/auth/login` | Não | Login → cookie HttpOnly |
| POST | `/api/auth/logout` | Sim | Logout → apaga cookie |
| GET | `/api/auth/me` | Sim | Info do utilizador actual |

---

## Estrutura do projecto

```
poker-app/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app, CORS, routers
│   │   ├── db.py            # Ligação PostgreSQL, helpers query/execute
│   │   ├── auth.py          # Hash passwords, session tokens, dependency
│   │   └── routers/
│   │       ├── health.py    # GET /health
│   │       └── auth.py      # POST /login, /logout, /register, GET /me
│   ├── schema.sql           # DDL completo — tabelas e índices
│   ├── requirements.txt
│   └── .env.example
├── frontend/                # Dia 2+
└── README.md
```
