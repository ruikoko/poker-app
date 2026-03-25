#!/usr/bin/env bash
# deploy/load_initial_data.sh
#
# Carrega os ficheiros de torneios existentes via API.
# Corre na máquina onde os ficheiros estão (não no VPS).
# Requer: curl, jq
#
# Uso:
#   bash deploy/load_initial_data.sh \
#     --url http://SEU_IP \
#     --email tu@exemplo.com \
#     --password a_tua_password \
#     --dir /caminho/para/os/ficheiros
#
# Os ficheiros podem ser .zip ou .txt.
# Estrutura esperada:
#   ficheiros/
#     winamax_2026.zip     ← detectado como Winamax
#     ggpoker_jan.zip      ← detectado como GGPoker
#     etc.

set -euo pipefail

# ── Argumentos ────────────────────────────────────────────────────────────────
URL=""
EMAIL=""
PASSWORD=""
FILES_DIR=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --url)      URL="$2";      shift 2 ;;
        --email)    EMAIL="$2";    shift 2 ;;
        --password) PASSWORD="$2"; shift 2 ;;
        --dir)      FILES_DIR="$2"; shift 2 ;;
        *) echo "Argumento desconhecido: $1"; exit 1 ;;
    esac
done

if [ -z "$URL" ] || [ -z "$EMAIL" ] || [ -z "$PASSWORD" ] || [ -z "$FILES_DIR" ]; then
    echo "Uso: $0 --url http://IP --email EMAIL --password PASS --dir /path/to/files"
    exit 1
fi

COOKIE_JAR=$(mktemp)
trap "rm -f $COOKIE_JAR" EXIT

# ── Login ─────────────────────────────────────────────────────────────────────
echo "▸ Login em ${URL}…"
LOGIN_RESP=$(curl -s -X POST "${URL}/api/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\"}" \
    -c "$COOKIE_JAR")

echo "$LOGIN_RESP" | grep -q '"ok":true' || {
    echo "ERRO: Login falhou — ${LOGIN_RESP}"
    exit 1
}
echo "  ✓ Autenticado"
echo ""

# ── Upload de ficheiros ───────────────────────────────────────────────────────
TOTAL_FILES=0
TOTAL_FOUND=0
TOTAL_INSERTED=0
TOTAL_SKIPPED=0
TOTAL_ERRORS=0
FAILED_FILES=()

for filepath in "${FILES_DIR}"/*.{zip,txt,ZIP,TXT} 2>/dev/null; do
    [ -f "$filepath" ] || continue
    filename=$(basename "$filepath")
    TOTAL_FILES=$((TOTAL_FILES + 1))

    echo "▸ A enviar: ${filename}…"

    RESP=$(curl -s -X POST "${URL}/api/import" \
        -b "$COOKIE_JAR" \
        -F "file=@${filepath}" \
        --max-time 120)

    # Verificar se é JSON válido
    if ! echo "$RESP" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
        echo "  ✗ Resposta inválida: ${RESP:0:200}"
        FAILED_FILES+=("$filename")
        continue
    fi

    STATUS=$(echo "$RESP"   | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','?'))")
    FOUND=$(echo "$RESP"    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('records_found',0))")
    INSERTED=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('inserted',0))")
    SKIPPED=$(echo "$RESP"  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('skipped',0))")
    ERRORS=$(echo "$RESP"   | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('errors',0))")
    SITE=$(echo "$RESP"     | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('site','?'))")

    echo "  Sala: ${SITE} | status: ${STATUS} | encontrados: ${FOUND} | inseridos: ${INSERTED} | duplicados: ${SKIPPED} | erros: ${ERRORS}"

    if [ "$ERRORS" -gt 0 ]; then
        ERR_LOG=$(echo "$RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for e in d.get('error_log',[])[:5]:
    print('    !', e)
")
        echo "$ERR_LOG"
    fi

    TOTAL_FOUND=$((TOTAL_FOUND + FOUND))
    TOTAL_INSERTED=$((TOTAL_INSERTED + INSERTED))
    TOTAL_SKIPPED=$((TOTAL_SKIPPED + SKIPPED))
    TOTAL_ERRORS=$((TOTAL_ERRORS + ERRORS))

    [ "$STATUS" = "error" ] && FAILED_FILES+=("$filename")

    echo ""
done

# ── Resumo ────────────────────────────────────────────────────────────────────
echo "═══════════════════════════════════════"
echo "  Carga inicial concluída"
echo "═══════════════════════════════════════"
echo ""
echo "  Ficheiros processados : ${TOTAL_FILES}"
echo "  Torneios encontrados  : ${TOTAL_FOUND}"
echo "  Inseridos             : ${TOTAL_INSERTED}"
echo "  Duplicados ignorados  : ${TOTAL_SKIPPED}"
echo "  Erros de parse        : ${TOTAL_ERRORS}"

if [ ${#FAILED_FILES[@]} -gt 0 ]; then
    echo ""
    echo "  ✗ Ficheiros com falha:"
    for f in "${FAILED_FILES[@]}"; do
        echo "    - ${f}"
    done
fi

echo ""
echo "  Ver logs completos em:"
echo "    ${URL}/api/import/logs  (requer login)"
echo "═══════════════════════════════════════"
