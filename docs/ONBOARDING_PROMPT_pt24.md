# Onboarding prompt — sessão pt24 (sucessora de pt23)

Cola este prompt no início de uma nova sessão Claude Web ou Claude Code para retomar o trabalho do pipeline HRC.

---

## Para a sessão Claude (lê na ordem indicada)

És o **Claude novo** desta sessão (pt24). A sessão anterior (pt23, 13 Maio 2026) fechou o ciclo mecânico ponta-a-ponta `poker-app → adapter → watcher → adapter → BD`, validado em prod com mão real `GG-5914506215`. **Bugs A/B/C/E do watcher Baltazar fechados.** Mas o pipeline ainda **não é usável em volume real** porque a tree do HRC tem ETA ~17h sem o prune downstream — o **gatekeeper de produção** é a tua prioridade #1.

### Documentos obrigatórios (ler na ordem)

1. **`CLAUDE.md`** — secções:
   - "Estado actual" do header
   - "Cinco fontes de input" (era 4 em pt13)
   - "Variáveis de ambiente FASE 3 (Railway service `poker-app`)" (em particular `HRC_WATCHER_API_KEY`)
   - "Última sessão fechada: pt23" (a ser actualizada por ti se necessário)

2. **`docs/JOURNAL_2026-05-13-pt23.md`** (sessão imediatamente anterior — leitura completa)
   - Resumo executivo
   - Blocos 1-10 (cronologia)
   - Bugs A/B/C/E fechados (tabela)
   - Tech debts pt23 (5 novos)

3. **`docs/TECH_DEBTS_INVENTARIO.md`** — secção "Estado actual (13 Maio 2026 — pt23 em curso, ...)" tem:
   - 5 tech debts pt23
   - 4 tech debts pt22 fechados em pt23
   - 5 carry-overs pt22 ainda abertos
   - Estado pt21 e anteriores

4. **`docs/PAPEIS_E_RESPONSABILIDADES.md`** — papel do Rui, do Claude Web, do Claude Code.

5. **`docs/REGRAS_NEGOCIO.md`** — regras duras (especial atenção à regra de ouro sobre sessões de poker e processos suspeitos).

6. **`docs/MAPA_ACOPLAMENTO.md`** — mapa técnico actualizado.

(Total: ~15-20 min de leitura. Não saltar — pt23 cometeu erros que vinham documentados em sessões anteriores, e o flow do watcher tem armadilhas únicas.)

### Estado actual em prod (pós-pt23)

- **Backend:** `poker-app-production-34a7.up.railway.app` em main `b3968ee` (HEAD após pt23 commits `c3cc66b` + `b3968ee`).
- **Adapter:** `tools/hrc_adapter/hrc_adapter.py` no PC principal source-controlled; cópia operacional em `C:\hrc\adapter\` no Beelink.
- **Watcher recompilado:** `hrc_watcher.exe` 13.4 MB em `_local_only/watcher_decompile/build_pyi/dist/` (gitignored); cópia operacional no Beelink, lugar exacto a confirmar com Rui.
- **HRC instalação:** Beelink `riand` user, perfil `Administrator` legacy preservado pelo reset Windows.
- **Suite backend:** 184 PASSED, 3 warnings pre-existentes.
- **`hrc_jobs` BD:** 1 row pt23 (`hand_db_id=16811, GG-5914506215, status=done`).

### Foco pt24 (prioridade decrescente)

#### 🔴 #1 — `#HRC-PRUNE-IN-GAP-DOWNSTREAM` (HIGH, gatekeeper)

**Razão da prioridade:** sem este prune, smoke real produz trees com ETA ~17h. Pipeline inviável para volume real.

**Spec resumida** (detalhe em TECH_DEBTS):

- Trigger: `players_left > 3 × max_players` (pré-3 final tables, fase Multi Table ICM). Excepção: agressor SB → não trigger.
- Por agressor inicial, eliminar opens in gap das posições **downstream**:
  - UTG → `{EP,MP,HJ,CO,BU,SB}`
  - EP → `{MP,HJ,CO,BU,SB}`
  - MP → `{HJ,CO,BU,SB}`
  - HJ → `{CO,BU,SB}`
  - CO → `{BU,SB}`
  - BU → `{SB}`
- **NÃO eliminar upstream** (já foldaram mas range de fold real importa para card removal no nó focal).

**Implementação proposta** (3 frentes):

1. **Backend `services/queue_export.py`** — novo helper `derive_prune_downstream(hh_text, max_players, players_left) -> list[str] | None`. Devolve lista de posições a prune (ou `None` se SB-aberto ou FT phase).
2. **`payouts.json`** — novo campo `prune_in_gap_downstream` com lista de posições.
3. **Script HRC** — variante de `mtt_advanced_20211029_..._bvb.js` (ou novo `.js`) que lê o hint do payouts.json e faz prune action no HRC para cada open in gap dessas posições. Esta parte é trabalho HRC Pro scripting; pode ser desenhada com o Rui ou via documentação HRC.

**Sugestão de arranque** para pt24:
- Começar por (1) + (2) backend — testável em isolation, suite pytest adiciona ~5-8 tests novos.
- Depois (3) script é a peça pesada; pode envolver Rui mais directamente.

#### 🔴 #2 — `#HRC-GG-KOS-EXTRACTION` (HIGH)

**Sintoma:** GG HHs exportadas sem bounties (KOs). HRC roda PKO em vazio → solver dá EVs deslocados para mãos PKO.

**Solução planeada:**
- Pipeline Vision (Claude Sonnet, similar a `services/lobby_vision.py`) extrai `{nick: bounty}` da SS anexada à mão.
- SS é localizada via `hand_attachments` (tabela criada em Bucket 1, Abr 2026 — ver MAPA §2.11).
- Backend `services/queue_export.py:convert_gg_hh_to_pokerstars_compatible` enriquece a HH PS-compat inserindo bounties em cada linha `Seat` antes de enviar ao adapter.

Cuidado: format PS-compat para bounty em `Seat` line já tem variações. Investigar antes de implementar.

#### Secundários (pt24+ se houver tempo)

- **`#HRC-MTT-OTHER-TABLES-INFO`** 🟡 MED — Backend pode derivar via `tournaments_meta` (player counts, stack averages). Watcher precisaria de preencher a página MTT Stacks em vez do skip actual.
- **`#WATCHER-META-INJECTION-BYPASSED`** 🟢 LOW — Remover dead code do Baltazar (`inject_meta_into_zip`, `zip_is_ready(replied/)`) quando fizermos full refactor do watcher.
- **`#PYINSTALLER-BUNDLE-SIZE`** 🟢 LOW — Tunar `.spec` se faltar dep em runtime real (Pillow provável).
- Carry-overs pt22: `#HRC-WATCHER-PATH-BETA-LEGACY` 🟡, `#HRC-ADAPTER-SCHEDULED-TASK` 🟢, `#SERVER-FILTER-HRC-STATUS` 🟢, `#HRC-RESET-PRESERVATION` 🟡.

### Notas importantes herdadas de pt23

#### HM3 não abre

Rui mencionou que **o HM3 não está a abrir** no PC principal (descoberta lateral durante pt23, sem repro detalhado no log). Esta é a fonte primária de tags de estudo (`hm3_tags` ← script `.bat`). Investigar:
- Reinstalação HM3?
- Conflito com algum process post-reset (anti-cheat poker tools?)
- `.bat` corre mas o HM3 GUI não? Ou .bat também falha?

Sem HM3 funcional, o backfill de `hm3_tags` para mãos novas pára. Hands continuam a chegar via Discord (sem hm3_tags) e backoffice SSs (sem hm3_tags). Não bloqueia pt24 directamente mas é mau a médio prazo.

#### Token rotation carry-over (pt22 + pt23)

`HRC_WATCHER_API_KEY` actual (mask `_5YENfRZai...qHT7EZOS`) **NÃO foi rotacionado** em pt23 — Rui confirmou skip. Continua o tech debt `#TOKEN-ROTATION-DEFENSIVE-PT23` (visto numa screenshot Railway durante debug pt22). Rotacionar quando convenientemente houver oportunidade — `python -c "import secrets; print(secrets.token_urlsafe(48))"` → Railway dashboard → `.bat` Desktop → setx Beelink.

#### Workaround `backend/.env` encoding cp1252

`backend/.env` local tem byte 0xe3 em position 82 (encoding não-UTF8). Qualquer script ad-hoc que importe `app.db` localmente parte com `UnicodeDecodeError`. Workaround conhecido: usar `railway variables --kv` para extrair env vars; query directa via public proxy do Postgres com password do `poker-app` service (não da `Postgres` service, que está stale 32 vs 31 chars). Detalhe operacional em TECH_DEBTS.

### Coisas a NÃO fazer

- ❌ **Não tocar no watcher recompilado** sem nova ronda de descompilação + swap + recompile. O fluxo é documentado em pt23 mas tem armadilhas (header-less pyc, stdlib hidden imports, etc.).
- ❌ **Não correr a app HRC nem o watcher no PC principal** sem confirmação do Rui — anti-cheat das salas pode scanner processes (regra de ouro CLAUDE.md).
- ❌ **Não modificar `_local_only/`** assumindo que vai ao repo — `_local_only/` está gitignored e contém binários pesados (30+ MB) e venvs.
- ❌ **Não commitar sem permissão explícita do Rui.** Pt23 fez 2 commits feature com aprovação explícita em cada um.
- ❌ **Não imprimir token** completo em logs, probes, ou mensagens. Sempre mascar (`mask[:10]...mask[-5:]`).
- ❌ **Não assumir que o adapter Beelink já tem o último `hrc_adapter.py`** — qualquer mudança ao adapter exige re-copy para `C:\hrc\adapter\` no Beelink + restart pelo Rui.

### Comandos úteis para diagnose pt24

```bash
# Health check prod
curl -sS "https://poker-app-production-34a7.up.railway.app/health"

# Last hrc_jobs rows (workaround encoding cp1252)
DB_URL_APP=$(railway variables --service poker-app --kv | grep "^DATABASE_URL=" | cut -d= -f2-)
DB_URL_PUB=$(railway variables --service Postgres --kv | grep "^DATABASE_PUBLIC_URL=" | cut -d= -f2-)
# Constuir URL: app password + public host (passwords diferem; ver tech debt)
python -c "from urllib.parse import urlparse, urlunparse; import os, psycopg2, psycopg2.extras, json; pa=urlparse(os.environ['DB_URL_APP']); pp=urlparse(os.environ['DB_URL_PUB']); url=urlunparse(pp._replace(netloc=f'{pp.username}:{pa.password}@{pp.hostname}:{pp.port}')); c=psycopg2.connect(url); cur=c.cursor(cursor_factory=psycopg2.extras.RealDictCursor); cur.execute('SELECT id, hand_db_id, status, result_zip_size, submitted_at FROM hrc_jobs ORDER BY id DESC LIMIT 10'); print(json.dumps([dict(r) for r in cur.fetchall()], default=str, indent=2))"

# Smoke real do queue endpoint
TOKEN=$(railway variables --service poker-app --kv | grep "^HRC_WATCHER_API_KEY=" | cut -d= -f2-)
MSYS_NO_PATHCONV=1 curl -sS -H "Authorization: Bearer $TOKEN" -o /tmp/queue.zip -w "HTTP %{http_code} | size %{size_download}\n" "https://poker-app-production-34a7.up.railway.app/api/queue/hrc?include_no_payout=false"

# Inspect first hand payouts.json (confirma hints presentes)
cd /tmp && rm -rf q && mkdir q && cd q && unzip -q /tmp/queue.zip && ls | head -3 && python -c "import json; print(json.dumps(json.load(open('$(ls -d */ | head -1 | sed s:/$::')/payouts.json')), indent=2))"

# Suite backend full
cd backend && python -m pytest 2>&1 | tail -3

# Railway logs (deployment actual)
railway logs --deployment 2>&1 | tail -30
```

### Workflow herdado de pt23 (Rui apreciou)

- **Buffered-diff antes de escrever em disco**: buffer → diff → aprovação → disco → diff → commit, em fases. Rui prefere esta cadência mesmo para changes pequenos.
- **PT-PT corrente antes do código**: para decisões/opções, prosa em pt-pt primeiro; tradução técnica depois.
- **Não oferecer `/schedule` sem ser pedido**: Rui decide ele próprio cadência de tasks recorrentes.
- **Memory updates apenas para padrões repetidos** ou correcções explícitas, não para cada interacção.

Boa sessão pt24.
