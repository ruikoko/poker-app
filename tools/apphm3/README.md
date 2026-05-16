# apphm3 — bridge HM3 ↔ Poker App

Scripts standalone que correm no PC do Rui (o que tem o HM3 instalado). Lêem
mãos tagadas da BD SQLite do HM3 e enviam para a API da poker app via HTTP.

Substituem a pasta antiga em `Desktop\AppHM3\` (não-versionada). Agora vivem
no repo com credenciais + caminho local fora do código versionado
(`config_local.py`).

## Ficheiros

| Ficheiro | Função |
|---|---|
| `hm3_export.py` | Exporta mãos tagadas do HM3 → POST `/api/hm3/import` |
| `hm3_scan_tags.py` | Lista tags definidas no HM3 + contagens por site |
| `HM3_Import.bat` | Duplo-clique p/ correr `hm3_export.py` com prompt de dias |
| `HM3_Scan_Tags.bat` | Duplo-clique p/ correr `hm3_scan_tags.py` |
| `config_local.example.py` | Template — copiar p/ `config_local.py` e preencher |
| `config_local.py` | **GITIGNORED** — caminho HM3 + credenciais reais (criar local) |

## Pré-requisitos

- **Python 3.10+** instalado e no PATH.
- **Módulo `requests`**: `pip install requests`.
- **HM3 instalado** com BD em path acessível (default Windows:
  `C:\Users\<user>\Documents\Holdem Manager 3\Databases\MyHM3Database.hmdb`).
  HM3 pode estar aberto enquanto se corre — o SQLite é lido em modo read-only.

## Setup local (1ª vez)

1. **Clonar/pull do repo** se ainda não tiveres:
   ```
   git clone <repo> poker-app-actual
   cd poker-app-actual\tools\apphm3
   ```

2. **Criar `config_local.py`** a partir do template:
   ```
   copy config_local.example.py config_local.py
   ```
   Abrir `config_local.py` num editor e preencher:
   - `HM3_DB` — caminho completo da BD `.hmdb` do HM3.
   - `LOGIN_EMAIL` — email da poker app.
   - `LOGIN_PASS` — password da poker app.

   ⚠️ **Nunca commitar `config_local.py`** (já está no `.gitignore`).

3. **Instalar dependência Python** (uma vez):
   ```
   pip install requests
   ```

## Uso diário

### Importar mãos tagadas

Duplo-clique em `HM3_Import.bat`. Pergunta "últimos quantos dias?":
- Enter sem nada → tudo (todas as mãos tagadas que ainda não estão na app).
- `7` → últimos 7 dias.

Ou pela linha de comandos directa, com mais opções:
```
python hm3_export.py                     # tudo
python hm3_export.py --days 7
python hm3_export.py --tag "nota++"
python hm3_export.py --tag "nota++" --days 3
python hm3_export.py --dry-run           # só mostra resumo, não envia
python hm3_export.py --save-csv export.csv
```

### Listar tags definidas no HM3

Duplo-clique em `HM3_Scan_Tags.bat`. Mostra todas as tags do HM3 com
contagens por site (PS / Winamax / WPN / GG).

## Como criar atalho rápido no Desktop

1. Botão direito no Desktop → Novo → Atalho.
2. Localização do item: caminho completo para `HM3_Import.bat` (drag-and-drop
   funciona).
3. Nome: "HM3 → Poker App".

A partir daí, duplo-clique no atalho corre o import sem teres de abrir o
Explorer.

## Segurança

- **NUNCA** commitar `config_local.py`. O `.gitignore` já bloqueia, mas
  confirma com `git status` antes de qualquer commit.
- Se mudaste a password recentemente: re-correr `pip install requests` não é
  necessário, basta editar `config_local.py`.
