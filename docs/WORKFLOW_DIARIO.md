# Workflow diário — Poker App

## Objectivos do utilizador

1. **Agrupar mãos de trabalho num só sítio**
2. **Estudar mãos com notas relevantes**
3. **Tirar notas nos vilões**

---

## Fase 1 — Ingestão de dados (fim de sessão)

### Ordem sugerida (pelo fluxo da app)

| # | Acção | Input | Output em BD | Onde aparece na UI |
|---|---|---|---|---|
| 1 | **Clicar "Sincronizar Agora" em Discord** | Mensagens nos canais Discord (`nota`, `icm`, `pos-pko`, etc.) | `replayer_link` → Vision → mão placeholder (`origin='discord'`, `discord_tags=[canal]`). `image` directa (Gyazo, `.png`/`.jpg`) → **não cria mão**: vira anexo a mão sibling ±90s via worker `/api/attachments/match` (Bucket 1). | Discord page + Dashboard "SSs à espera"; anexos: 📎 N na lista + secção CONTEXTO no detalhe |
| 2 | **+ Importar HHs GG do backoffice** (ZIP/TXT) | Ficheiros `.txt` / `.zip` GG | Hands com `origin='hh_import'`. `_insert_hand` detecta colisão com placeholders Discord → substitui preservando metadados. Auto-rematch HH→SS dispara. | Torneios, Estudo (se match SS↔HH), Vilões (se regra A∨B∨C) |
| 3 | **Correr script HM3 `.bat`** | BD HoldemManager 3 (WN/PS/WPN/GG) | Hands com `origin='hm3'`, `hm3_tags=[nota, ICM, PKO pos, ...]`. Auto-rematch HH→SS dispara (commit 072f57a). | Estudo (agrupado por tag HM3), HM3 page (listagem filtrável), Vilões (se tag `nota*` ou showdown) |
| 4 | **+ Importar SSs soltas** (uploads manuais) | Imagens individuais (`.png`, `.jpg`) | Entries com `entry_type='screenshot'`. Vision processa. Cria placeholder ou matcha HH existente. | Dashboard painel SSs + eventualmente Estudo/Vilões |

### Comportamento esperado da app ao receber cada input

#### Input 1 — Sincronização Discord

```
Mensagem Discord (link replayer)
        ↓
entries (source='discord', entry_type='replayer_link', raw_json com url)
        ↓
Vision processa imagem og:image
        ↓
raw_json ganha: tm, players_list, hero, vision_sb, vision_bb, board, pot, file_meta
        ↓
Pipeline cria/actualiza em `hands`:
  - Se HH GG já existe (mesmo TM): enriquece com player_names + screenshot_url → match_method='anchors_stack_elimination_v2'
  - Se não: cria PLACEHOLDER (raw vazio, origin='discord', discord_tags=[canal], hm3_tags=['GGDiscord'])
```

**Regras de destino** (avaliadas no render da UI):

| Condição | Destino UI |
|---|---|
| `discord_tags` contém `'nota'` + `match_method` populado | Vilões (modal do nick) |
| `discord_tags` outros canais + `match_method` populado | Estudo |
| Placeholder sem HH (raw vazio, `match_method='discord_placeholder_no_hh'`) | Dashboard painel "SSs à espera de HH" |

#### Input 2 — Import HHs GG (ZIP via UI)

```
Ficheiros ZIP
        ↓
Parser _parse_hand extrai cada mão → tournament_name, tournament_number, buy_in, tournament_format, hero_cards, board, result, all_players_actions
        ↓
_insert_hand insere em `hands`:
  - Se placeholder Discord existe (mesmo hand_id): SELECT alargado → DELETE placeholder → INSERT nova → UPDATE pós-INSERT com COALESCE(NULLIF(...)) preservando origin, discord_tags, entry_id, player_names, screenshot_url
  - Se não: INSERT normal com origin='hh_import'
        ↓
Auto-rematch (import_.py:340): procura SS órfãs por TM, enriquece hands novas
```

**Regras de destino:**

| Condição | Destino UI |
|---|---|
| HH GG sem SS (nicks anonimizados) | Torneios > GG > Sem SS (NÃO vai para Estudo) |
| HH GG com SS (match feito) | Estudo + Vilões (se aplicável regras) |
| HH GG com placeholder Discord reconciliado | Herda destino Discord (Vilões/Estudo conforme canal) |

#### Input 3 — Script HM3 `.bat`

```
POST /api/hm3/import com raw HH + tags HM3
        ↓
Parser extrai por sala (WN/PS/WPN/GG)
        ↓
INSERT em `hands` com origin='hm3', hm3_tags=[...]
  - ON CONFLICT UPDATE com CASE WHEN site='GGPoker' preserva all_players_actions enriquecido
        ↓
_create_hand_villains_hm3 (commit 6aefc95):
  - Non-GG: cria villains via VPIP/showdown directo
  - GG: SKIP (deixa SS pipeline tratar)
        ↓
Auto-rematch HH→SS (commit 072f57a) — procura SSs Discord pendentes
```

**Regras de destino:**

| Condição | Destino UI |
|---|---|
| `hm3_tags ~ 'nota%'` | Vilões |
| `hm3_tags` outras (ICM, PKO pos, etc.) | Estudo agrupado por tag |
| `hm3_tags` mistas | Ambas as secções filtram por suas tags |
| Site PS/WN/WPN sem SS | Estudo directo (nicks reais) |
| Site GG sem match SS | Excluído de Estudo |

#### Input 4 — Upload manual SSs

```
Drag-and-drop na UI
        ↓
entries (source='manual_upload', entry_type='screenshot')
        ↓
Vision processa → raw_json com tm, players_list, etc.
        ↓
Match por TM com hands existentes → enriquece OU fica órfã
```

---

## Fase 2 — Estudo e trabalho

### Objectivo 1 — Agrupar mãos de trabalho num só sítio

**Destino: página Estudo**

Espera-se ver:
- Filtros temporais (Hoje / 3 dias / Semana / Mês)
- Filtros por sala
- Filtros por posição
- Pesquisa livre (torneio, tag)
- **Pills visuais das tags:**
  - `#tag_HM3` em cinzento/branco (HM3 tags reais)
  - `#canal_Discord` em azul Discord (commit e77b5cf)
- Agrupamento por tag (`#nota`, `#ICM`, `#PKO pos`, etc.) com contagens
- Cada grupo expande e mostra mãos dentro

### Objectivo 2 — Estudar mãos com notas relevantes

**Destino: filtros de tag em Estudo + página HM3**

Espera-se poder:
- Filtrar por tag específica (`nota`, `nota++`, `ICM PKO`, etc.)
- Ver tempo de estudo acumulado por mão
- Marcar mão como `studied` / `resolved` / `review`
- Abrir replayer da mão (ver acções jogada a jogada)
- Editar tags manualmente (TagEditor popover)
- **Ver imagens de contexto** (Bucket 1, Abr 2026): mãos com anexos imagem mostram ícone `📎 N` na linha (`HandRow.jsx`) e secção CONTEXTO inline no detalhe (`HandDetailPage.jsx`) com thumbnails 200px clicáveis. Cobre o caso "imagem postada no Discord ±90s da mão" e "imagem postada Discord enquanto a mão veio via HM3".

### Objectivo 3 — Tirar notas nos vilões

**Destino: página Vilões**

Espera-se:
- Lista de nicks com contagem de mãos em `hand_villains`
- Clicar num nick → modal com:
  - Todas as mãos desse nick (só `hand_villains`, não VPIP global)
  - Stack médio, VPIP%, posições jogadas
  - Campo de notas livres sobre o vilão
- Filtros por sala / data / stack range

---

## Lista de verificação

### Ingestão

- [ ] **Sync Discord funcional** — bot online, puxa mensagens novas
- [ ] **Vision processa SSs** — cada SS vira hand placeholder ou enriquece HH existente
- [ ] **Import ZIP HH funciona** — drag-and-drop aceita múltiplos ficheiros
- [ ] **`_insert_hand` preserva metadados Discord** quando substitui placeholder
- [ ] **Auto-rematch dispara** após cada import (ZIP + HM3 `.bat`)
- [ ] **Script HM3 `.bat` insere com `origin='hm3'`** e `hm3_tags` populados
- [ ] **Upload manual SS funciona** — drag-and-drop aceita `.png/.jpg`

### Distribuição

- [ ] **Mãos GG anonimizadas NÃO aparecem em Estudo**
- [ ] **Mãos GG com match SS↔HH aparecem em Estudo + Vilões**
- [ ] **Mãos Discord canal `nota` aparecem em Vilões**
- [ ] **Mãos Discord outros canais aparecem em Estudo**
- [ ] **Mãos PS/WN/WPN aparecem em Estudo directo (nicks reais)**
- [ ] **SSs sem HH aparecem em Dashboard painel "SSs à espera"**
- [ ] **`hand_villains` criado quando cumpre regra A∨B∨C**

### UI / Estudo

- [ ] **Filtros temporais funcionam** (Hoje, 3 dias, Semana, Mês)
- [ ] **Filtro por sala** funciona
- [ ] **Pesquisa por torneio/tag** funciona
- [ ] **Agrupamento por tag HM3** mostra mãos correctas
- [ ] **Coluna TAGS mostra HM3 tags** (cinza/branco)
- [ ] **Coluna TAGS mostra Discord tags** (azul Discord, prefixo `#`)
- [ ] **Replayer abre correctamente** ao clicar numa mão
- [ ] **TagEditor permite adicionar/remover tags**
- [ ] **Study state muda** (new → review → studying → resolved)

### UI / Vilões

- [ ] **Lista de vilões mostra contagens**
- [ ] **Modal do vilão mostra só `hand_villains`** (não VPIP global)
- [ ] **Campo de notas livre do vilão** existe e grava
- [ ] **Filtros do modal** funcionam (sala, data, stack)

### UI / Torneios

- [ ] **HHs GG sem SS aparecem em Torneios > GG > Sem SS**
- [ ] **HHs GG com SS aparecem em Torneios > GG > Com SS**
- [ ] **Aba HM3 com Tag mostra torneios agrupados**

### UI / HM3

- [ ] **Listagem filtrável por tag / data / PKO-NPKO / pré-pós-flop**
- [ ] **Edição manual de tags** com re-avaliação automática de destinos
- [ ] **Logs do bot `.bat`** visíveis

### UI / Discord

- [ ] **Estado do bot** visível (Online/Offline)
- [ ] **Lista de canais sincronizados** com última sync
- [ ] **Gyazos/imagens órfãs** (sem match) visíveis e associáveis manualmente a mãos

### UI / Dashboard

- [ ] **Painel "SSs à espera de HH"** mostra origem + tempo em espera
- [ ] **Últimas mãos importadas** mostra últimas N com tag + sala
- [ ] **Contagens globais** (total mãos, villains únicos, etc.)

---

## Esquema visual do fluxo de dados

```
┌─────────────────────────────────────────────────────────────────┐
│                    4 FONTES DE INPUT                            │
└─────────────────────────────────────────────────────────────────┘
    │           │            │              │
    ▼           ▼            ▼              ▼
[Discord]   [Import ZIP]  [HM3 .bat]    [Upload SS]
 (bot)      (UI manual)   (script)      (drag-drop)
    │           │            │              │
    │           │            │              │
    ▼           ▼            ▼              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       entries (inbox)                            │
│  source + entry_type + raw_json + status                        │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌────────────────────────┐
              │   Vision (se SS)       │
              │   Parser (se HH text)  │
              └────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                         hands                                    │
│  origin, discord_tags, hm3_tags, tags (auto)                    │
│  player_names (Vision), all_players_actions (parser)            │
│  match_method, screenshot_url                                    │
└─────────────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
   [Estudo]         [Vilões]       [Torneios / Dashboard]
   filtros por      hand_villains  listagem + "SSs à espera"
   tag HM3/Discord  por nick
```

---

## Avaliação de prontidão

Pontos críticos para considerar a app "pronta para uso sob condições mínimas de qualidade":

1. **Ingestão fiável** — 4 fontes funcionam sem perda de dados
2. **Roteamento correcto** — cada mão aparece onde deve aparecer
3. **Estudo eficiente** — filtros + agrupamento + replayer funcionam
4. **Vilões úteis** — notas + histórico + regras A∨B∨C funcionam
5. **Zero bugs visíveis** — utilizador não encontra dados em falta / duplicados / em sítios errados

### Conhecidos pendentes (não bloqueiam uso diário)

- Painel Discord: migração para "área de transição" com 2 listas (só visual, funcional já existe)
- Suporte Winamax replayer HTML
- Logos salas como banner esbatido
- Backfill estendido às 110 mãos absorvidas no wipe (cosmético)
