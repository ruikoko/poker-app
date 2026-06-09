# appimport — import por pasta local → Poker App

Um "um toque" para importar **GG hand history**, **GG tournament summaries**,
**SS do Intuitive Tables**, **SS manuais do replayer** e **SS de lobby** a partir
de uma pasta local — sem upload manual na UI. Corre no PC do Rui (o mesmo que
joga), **só a pedido** (duplo-clique depois da sessão), nunca em background.

Mesmo estilo do `apphm3`: script Python standalone + `.bat` de duplo-clique,
credenciais/caminho fora do git (`config_local.py`).

> **HM3** fica de fora (tem o seu próprio `.bat` em `tools/apphm3/`).
> O **sync do Discord `#lobbys`** fica de fora (é sync de rede, não ficheiros).

## ⚠️ MODO DE TESTE (dry-run) é o defeito
Correr o `.bat` **sem flags** = **dry-run**: imprime o plano (para cada ficheiro
`MESA|LOBBY|SKIP` + site + `captured_at` + endpoint-alvo) **sem enviar e sem
mover** nada. Confirma o plano e só depois corre **com `--ao-vivo`** para enviar
a sério. (`python app_import.py --ao-vivo`.)

## Pasta única `it` — routing por NOME (mesa vs lobby)
O Intuitive Tables passou a usar **uma só pasta** para SS de **mesa** e de
**lobby** (o nome da janela vai no ficheiro). O `it` é roteado pela **análise do
nome**, não por subpasta:
- **MESA** → o miolo tem marcador de mesa (GG: `" - Blinds "` ou `" - Table "`;
  Winamax: `(#<dígitos>)`) → `POST /api/table-ss/upload` (move → `done/it`).
- **LOBBY** → qualquer outro ficheiro com a cauda nova do IT
  (`-YYYYMMDDHHMMSS-NN`), com `captured_at` derivado desse timestamp →
  `POST /api/lobbys/upload` (move → `done/lobby`).
- **SKIP** → sem a cauda nova do IT (legado, ex. `Shot21-GGPoker-…`): **fica no
  sítio**, log `skip: formato não-IT`.

O **site** sai do 1º token do nome (mapa único, apara `.exe` — `GGnet.exe`→GGPoker,
`Winamax.exe`→Winamax; prefixos limpos passam tal e qual).

> Para lobbys há ainda duas vias legadas: a subpasta dedicada **`lobby`**
> (drop-only-these, move) e a pasta **externa `LOBBY_DIR`** — agora **2ª via
> MANUAL**, só lida com **`--lobby-dir`** (ver abaixo).

## ⚠️ Restrição GG (crítica)
O PC de jogo = PC de dev. Corre o `.bat` **só com as salas fechadas, depois da
sessão**. É um envio único e termina — não há processo a correr durante o jogo.

## Ficheiros

| Ficheiro | Função |
|---|---|
| `app_import.py` | Varre as subpastas e envia o que é novo para a app |
| `Import.bat` | Duplo-clique p/ correr `app_import.py` |
| `config_local.example.py` | Template — copiar p/ `config_local.py` e preencher |
| `config_local.py` | **GITIGNORED** — pasta-mãe + credenciais (criar local) |

## Pré-requisitos
- **Python 3.10+** no PATH (já o tens para o apphm3).
- **`requests`**: `pip install requests` (já instalado para o apphm3).
- Nada mais a instalar.

## Setup local (1ª vez)
1. Copia `config_local.example.py` → `config_local.py`.
2. Em `config_local.py` preenche:
   - **`PARENT_DIR`** = a pasta-mãe à tua escolha (ex.: `C:\Users\User\Desktop\poker_import`).
   - **`LOGIN_EMAIL` / `LOGIN_PASS`** = as mesmas credenciais do apphm3.
3. Duplo-clique no `Import.bat` uma vez. Ele **cria automaticamente** dentro da
   pasta-mãe:
   ```
   <PARENT_DIR>\
     gg_hh\     ← põe aqui os .zip/.txt de hand history GG
     gg_ts\     ← põe aqui os .zip/.txt de tournament summaries GG
     it\        ← põe aqui as imagens do Intuitive Tables (mesa E lobby; routing por nome)
     manual\    ← põe aqui as imagens de SS manuais do replayer
     lobby\     ← (legado, opcional) SS de lobby drop-only-these
     done\      ← os enviados com sucesso são MOVIDOS para cá (por tipo)
   ```

## Uso (sempre que quiseres importar)
1. Põe os ficheiros na **subpasta certa** (`gg_hh`/`gg_ts`/`manual` pela
   subpasta; `it` é a pasta única do Intuitive Tables, roteada pelo nome).
   **Mantém o nome original** dos ficheiros (o `captured_at`/TM/site vêm do nome
   — o agente nunca renomeia no envio).
2. Duplo-clique no `Import.bat` → **dry-run**: lê o plano (`MESA|LOBBY|SKIP` +
   site + `captured_at` + endpoint) sem enviar nem mover. **Confirma**.
3. Para enviar a sério, corre **com `--ao-vivo`** (`python app_import.py
   --ao-vivo`). Ele faz login, envia só o que é novo e a app trata do resto
   (Vision, matching).
4. Lê o resumo no fim (mesa/lobby/skip/falhas) e carrega numa tecla.

## Incremental + idempotente
- **Ficheiro na subpasta = ainda por enviar.**
- Enviado com **sucesso** → **movido** para `done\<tipo>\` (o original fica lá,
  intacto; mover ≠ apagar).
- Envio **falhado** → **fica** na subpasta → tenta outra vez no próximo
  duplo-clique. Re-enviar é seguro mesmo que algo escape: a app deduplica
  (HH por `hand_id`, SS de mesa por `file_hash`, TS por upsert).

## Subpasta `lobby` — porta dedicada drop-only-these (gémea do `it`)
Para importar SS de **lobby de torneio** largando-as numa subpasta (como o `it`),
em vez de varrer a pasta de Capturas inteira:
1. Põe as imagens em `<PARENT_DIR>\lobby\`. **Só** se processa o que está cá
   dentro — nada mais é varrido.
2. Cada ficheiro → `POST /api/lobbys/upload`, com `captured_at` = **hora de
   modificação do ficheiro** (mtime). Os nomes do Windows ("Captura de ecrã
   `YYYY-MM-DD HHMMSS`") **não** trazem o `YYYYMMDDHHMMSS` que a via `it`/table-SS
   lê do nome — por isso a hora vem do timestamp do ficheiro (igual à `LOBBY_DIR`).
3. O **backend decide se é lobby** (mesmo gate). Mover (preserva o original):
   - **lobby confirmado** (`is_lobby`) → movido para `done\lobby\`.
   - **não-lobby genuíno** (`json_invalid`/`site_undetected`) → foi processado →
     movido para `done\lobby\`.
   - **falha transitória** da Vision (`vision_failed`) → **NÃO** move → **retry**
     no próximo duplo-clique. Um lobby real nunca se perde por um soluço de API.

> Diferença para a `LOBBY_DIR` (abaixo): a subpasta **move** ficheiros (drop-only-
> these, igual às 4 genéricas); a `LOBBY_DIR` lê uma pasta **externa** directa, sem
> mover, com manifesto + `LOBBY_SINCE`. As duas usam o **mesmo** endpoint e gate.

## Fonte "lobby" (opcional, 2ª via MANUAL) — pasta EXTERNA `LOBBY_DIR`
> **Desde pt62 só é lida com a flag `--lobby-dir`** (deixou de correr nas
> corridas normais). Para importar SS de **lobby de torneio** sem as separar dos
> outros screenshots:
1. Em `config_local.py` define **`LOBBY_DIR`** = a pasta de Capturas de Ecrã
   (ex.: `C:\Users\User\Pictures\Screenshots`). Para desligar, comenta a linha.
2. O agente lê essa pasta **directamente** (NÃO move ficheiros, NÃO é subpasta)
   e envia os **novos** (dedup por nome via `lobby_sent.txt` na pasta-mãe — o
   nome do Windows traz data+hora, é único).
3. O **backend decide se é lobby**: corre a Vision de lobby; se a imagem não for
   um lobby de torneio (um print qualquer), é **ignorada** (nada gravado). Se for
   lobby → entra em `tournament_payouts` pela mesma pipeline do sync do Discord.
4. **`LOBBY_SINCE`** (opcional, ex. `"2026-05-30"`): só processa capturas com
   data (mtime) **>= essa data**. Evita correr Vision em meses de history na 1ª
   corrida e mantém o scope. Ficheiros mais antigos são saltados todas as corridas
   (sem Vision, sem marcar).

> O `captured_at` enviado é a hora de modificação do ficheiro (= quando a SS foi
> tirada), usada como âncora do torneio. Custo: 1 leitura Vision por screenshot
> novo da pasta (uma vez — fica no manifesto).

> **Falha transitória ≠ não-lobby.** Se a Vision falhar por soluço de API
> (`vision_failed`), o ficheiro **não** é marcado no manifesto → **retry** na
> próxima corrida. Só um não-lobby genuíno (`json_invalid`/`site_undetected`) ou
> um lobby processado é que ficam marcados. Um lobby real nunca se perde em
> silêncio por um erro transitório.

## Endpoints usados (os MESMOS do upload manual da UI / sync)
| Fonte | Endpoint | O que faz a app |
|---|---|---|
| `gg_hh` | `POST /api/import` | parse HH GG → `hands` |
| `gg_ts` | `POST /api/tournament-summaries/import` | parse TS GG → `tournament_summaries` |
| `it` (MESA) | `POST /api/table-ss/upload` | Vision (Claude) → `players_left` + match |
| `it` (LOBBY) | `POST /api/lobbys/upload` | gate "é lobby?" → `tournament_payouts` (move p/ `done\lobby\`) |
| `manual` | `POST /api/screenshots` | Vision (Claude) → enriquecimento/placeholder |
| `lobby` (subpasta) | `POST /api/lobbys/upload` | gate "é lobby?" → `tournament_payouts` (move p/ `done\lobby\`) |
| `lobby` (LOBBY_DIR externa, `--lobby-dir`) | `POST /api/lobbys/upload` | gate "é lobby?" → `tournament_payouts` (sem mover; manifesto) |

Auth = cookie de sessão via `POST /api/auth/login` (igual ao apphm3).
