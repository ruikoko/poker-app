# appimport — import por pasta local → Poker App

Um "um toque" para importar **GG hand history**, **GG tournament summaries**,
**SS do Intuitive Tables** e **SS manuais do replayer** a partir de uma pasta
local — sem upload manual na UI. Corre no PC do Rui (o mesmo que joga), **só a
pedido** (duplo-clique depois da sessão), nunca em background.

Mesmo estilo do `apphm3`: script Python standalone + `.bat` de duplo-clique,
credenciais/caminho fora do git (`config_local.py`).

> **HM3** fica de fora (tem o seu próprio `.bat` em `tools/apphm3/`).
> **Discord / lobby** ficam de fora (são sync de rede, não ficheiros).

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
     it\        ← põe aqui as imagens de SS do Intuitive Tables
     manual\    ← põe aqui as imagens de SS manuais do replayer
     done\      ← os enviados com sucesso são MOVIDOS para cá (por tipo)
   ```

## Uso (sempre que quiseres importar)
1. Põe os ficheiros na **subpasta do tipo certo** (o routing é pela subpasta —
   determinístico, sem adivinhar). **Mantém o nome original** dos ficheiros (as
   SS do IT/manual tiram o `captured_at`/TM do nome — o agente nunca renomeia no
   envio).
2. Duplo-clique no `Import.bat`. Ele faz login, envia **só o que está nas
   subpastas** (= ainda não enviado) e a app trata do resto (Vision, matching).
3. Lê o resumo no fim (enviados/falhas por tipo) e carrega numa tecla.

## Incremental + idempotente
- **Ficheiro na subpasta = ainda por enviar.**
- Enviado com **sucesso** → **movido** para `done\<tipo>\` (o original fica lá,
  intacto; mover ≠ apagar).
- Envio **falhado** → **fica** na subpasta → tenta outra vez no próximo
  duplo-clique. Re-enviar é seguro mesmo que algo escape: a app deduplica
  (HH por `hand_id`, SS de mesa por `file_hash`, TS por upsert).

## Fonte "lobby" (opcional) — pasta de Capturas do Windows
Para importar SS de **lobby de torneio** sem as separar dos outros screenshots:
1. Em `config_local.py` define **`LOBBY_DIR`** = a pasta de Capturas de Ecrã
   (ex.: `C:\Users\User\Pictures\Screenshots`). Para desligar, comenta a linha.
2. O agente lê essa pasta **directamente** (NÃO move ficheiros, NÃO é subpasta)
   e envia os **novos** (dedup por nome via `lobby_sent.txt` na pasta-mãe — o
   nome do Windows traz data+hora, é único).
3. O **backend decide se é lobby**: corre a Vision de lobby; se a imagem não for
   um lobby de torneio (um print qualquer), é **ignorada** (nada gravado). Se for
   lobby → entra em `tournament_payouts` pela mesma pipeline do sync do Discord.

> O `captured_at` enviado é a hora de modificação do ficheiro (= quando a SS foi
> tirada), usada como âncora do torneio. Custo: 1 leitura Vision por screenshot
> novo da pasta (uma vez — fica no manifesto).

## Endpoints usados (os MESMOS do upload manual da UI / sync)
| Fonte | Endpoint | O que faz a app |
|---|---|---|
| `gg_hh` | `POST /api/import` | parse HH GG → `hands` |
| `gg_ts` | `POST /api/tournament-summaries/import` | parse TS GG → `tournament_summaries` |
| `it` | `POST /api/table-ss/upload` | Vision (Claude) → `players_left` + match |
| `manual` | `POST /api/screenshots` | Vision (Claude) → enriquecimento/placeholder |
| `lobby` (LOBBY_DIR) | `POST /api/lobbys/upload` | gate "é lobby?" → `tournament_payouts` |

Auth = cookie de sessão via `POST /api/auth/login` (igual ao apphm3).
