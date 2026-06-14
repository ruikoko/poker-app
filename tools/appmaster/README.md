# appmaster — import mestre num clique

Orquestra os 3 tools de import numa só corrida, com um **menu curto de janelas**
pré-preenchidas. **Não muda a lógica de nenhuma pipeline** — só as encadeia.

> Corre no PC do Rui (o mesmo que joga), **só a pedido** (duplo-clique depois da
> sessão), nunca em background. Mesma restrição GG dos outros tools: **só com as
> salas fechadas**.

## O que faz (por esta ordem)

1. **appimport** — GG `gg_hh`/`gg_ts` + `it` (Intuitive Tables) + `manual` + a
   subpasta `lobby`, **e** a pasta externa `LOBBY_DIR`. Usa o `LOBBY_SINCE` do
   menu **só nesta corrida** (o `config_local.py` do appimport fica intacto).
2. **apphm3** — exporta as mãos tagadas do HM3 dos **últimos N dias** (e,
   opcionalmente, **filtradas por tag**) do menu, **sem** o prompt interactivo
   (passa `--days N` e `--tag <tag>` directamente).
3. **Discord** — `POST /api/discord/sync-and-process` com a **janela do menu**
   (login com as mesmas credenciais dos outros tools).

Os **reconciles de lobby** disparam sozinhos a seguir aos imports de HH/TS (já é
o comportamento do backend) — não há passo extra.

## Menu (Enter = default, escrever = override)

Só os 3 pipelines que têm janela aparecem. **GG e IT não têm entrada** —
processam o que está nas pastas.

```
  HM3 — últimos N dias (ou 'all')      [90]:
  HM3 — tag (Enter = todas)            [todas]:
  Lobbys — desde (YYYY-MM-DD)          [2026-06-01]:   ← default = LOBBY_SINCE do config
  Imagens — desde (YYYY-MM-DD)         [(tudo)]:       ← janela it/manual/lobby
  Imagens — até   (YYYY-MM-DD)         [(tudo)]:
  Discord — 72h | 24h/7d/15d/30d | YYYY-MM-DD   [72h]:
```

- **HM3 dias**: um número (dias) ou `all` para todas as mãos tagadas.
- **HM3 tag**: Enter = todas as tags (sem `--tag`); escrever uma tag (ex.: `nota`)
  passa `--tag "nota"`. Match exacto e, se falhar, por "contém"; se a tag não
  existir, o `hm3_export.py` erra e **lista as tags disponíveis** (deixamos a
  mensagem aparecer).
- **Lobbys**: data `YYYY-MM-DD`; override do `LOBBY_SINCE` só desta corrida.
- **Imagens — desde / até**: **janela de datas** que filtra **só as imagens**
  (`it` pelo timestamp do nome; `manual`/`lobby` pelo mtime) — conceito
  **dia-de-jogo 15:00→15:00**, `até` inclusive. **`gg_hh`/`gg_ts` entram SEMPRE
  por inteiro** (nunca filtrados). Enter nos dois = sem janela (tudo). Default =
  `IMPORT_DESDE`/`IMPORT_ATE` do `config_local` do appimport (se definidos).
- **Discord**: uma janela pré-definida (`72h`, `24h`, `7d`, `15d`, `30d`) **ou**
  uma data `YYYY-MM-DD` (= desde essa data até agora, modo `custom`).

> **O appimport corre AO VIVO** no mestre (envia e move). A janela e o
> `LOBBY_SINCE` são injectados só nesta corrida (via `argv` + `overrides`); o
> `config_local` do appimport **não é tocado**.

No fim, um **resumo consolidado** com o estado de cada pipeline.

## Pré-requisitos

- Os tools **`appimport`** e **`apphm3`** já configurados (cada um com o seu
  `config_local.py`). O appmaster reutiliza-os tal-e-qual:
  - credenciais + URL + `LOBBY_SINCE` vêm do `config_local.py` do **appimport**;
  - a BD HM3 vem do `config_local.py` do **apphm3**.
- **Python 3.10+** e **`requests`** (já instalados para os outros tools).
- Nada novo para configurar — o appmaster **não tem `config_local` próprio**.

## Uso

Duplo-clique no **`RunAll.bat`** → responde ao menu (ou só Enter 3×) → lê o
resumo no fim.

## Mecânica (para quem mantém)

Orquestração pura, **zero alterações** a `appimport`/`apphm3`:

- **appimport** corre **in-process** e **ao vivo**: `import app_import` e chama
  `app_import.main(argv=["--ao-vivo", "--desde", D, "--ate", A], overrides={"LOBBY_SINCE": …})`.
  A janela vai por `argv` (as flags ganham à config); o `LOBBY_SINCE` vai por
  `overrides` (aplicado **depois** do `load_config`, que de outro modo o
  esmagaria). O `config_local.py` não é tocado.
- **apphm3** corre como **subprocesso** `python hm3_export.py --days N` (o script
  já aceita `--days`; o prompt interactivo vive no `HM3_Import.bat`, que aqui é
  contornado).
- **Discord** é uma chamada HTTP directa (login + `sync-and-process`) com as
  credenciais importadas do `config_local` do appimport.
