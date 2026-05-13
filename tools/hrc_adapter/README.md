# hrc_adapter — adapter Beelink ↔ poker-app

Adapter Python que cose a API REST do poker-app com o `hrc_watcher.exe` no
Beelink. Loop contínuo em background.

## O que faz

- A cada 60 s, faz `GET /api/queue/hrc` ao backend e descomprime mãos novas
  para `C:\Users\Administrator\Documents\Teste completo\<hand_id>\`.
- Vigia `Teste completo\done\*.zip` para zips terminados pelo watcher →
  faz `POST /api/queue/hrc/results` com `status=done` e o zip.
- Vigia `Teste completo\<hand_id>\.failed` (e variante
  `<hand_id>.failed\`) para marcadores de falha → POST com `status=failed`
  e motivo lido do marker.
- Mantém `C:\hrc\adapter\state.json` como registo local idempotente.
- Loga em `C:\hrc\adapter\logs\hrc_adapter.log` com rotação diária e
  retenção de 14 dias.

## Pré-requisitos

- **Python 3.14** instalado no Beelink (`py -3.14 --version`).
- **Watcher já a correr** (perfil `Administrator`) com pasta canónica
  `C:\Users\Administrator\Documents\Teste completo\` + subpastas
  `done\arquivo\replied\`.
- **Token `HRC_WATCHER_API_KEY`** — gerado no Railway (service `poker-app`,
  env var). Pede ao Web se não o tens.

## Setup (1ª vez)

1. Copia `hrc_adapter.py`, `requirements.txt` e este README para
   `C:\hrc\adapter\` no Beelink.

2. Cria virtual env e instala dependências:

   ```powershell
   cd C:\hrc\adapter
   py -3.14 -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Define o token como variável de utilizador (HKCU):

   ```powershell
   setx HRC_WATCHER_API_KEY "<cola_aqui_o_token>"
   ```

   **Importante:** `setx` só fica visível em **novas** sessões PowerShell.
   Fecha esta e abre outra antes do próximo passo.

## Arrancar (interactive, 1ª corrida)

Numa **nova** sessão PowerShell:

```powershell
cd C:\hrc\adapter
.\venv\Scripts\activate
python hrc_adapter.py
```

Imprime banner com paths e entra em loop. `Ctrl+C` para parar limpo (faz
save do state antes de sair).

## Migrar para Scheduled Task (produção)

Depois de validares o smoke interactivo:

1. Abre Task Scheduler (`taskschd.msc`).
2. **Create Task** → tab **General**:
   - Nome: `HRC Adapter`
   - "Run only when user is logged on"
3. **Triggers** → New → "At log on" (utilizador `riand`).
4. **Actions** → New:
   - Program: `C:\hrc\adapter\venv\Scripts\python.exe`
   - Arguments: `C:\hrc\adapter\hrc_adapter.py`
   - Start in: `C:\hrc\adapter`
5. **Conditions** → desactiva "Start the task only if the computer is on
   AC power".
6. **Settings**:
   - "If the task fails, restart every: 1 minute"
   - "Attempt to restart up to: 3 times"
7. OK + autentica.

Para parar: Task Scheduler → HRC Adapter → End.

## Logs e debug

- **Logs gerais**: `C:\hrc\adapter\logs\hrc_adapter.log` (rotação diária,
  14 dias de retenção).
- **Manifests dos pulls**: `C:\hrc\adapter\logs\manifests\manifest_<ts>.json`
  — guardados separados, úteis para auditar o que o backend devolveu.
- **State local**: `C:\hrc\adapter\state.json` — registo do que já
  passou. Apagar = forçar re-processamento de tudo o que o backend
  devolver no próximo pull.

## Variáveis de ambiente

| Var | Default | Notas |
|---|---|---|
| `HRC_WATCHER_API_KEY` | (obrigatório) | Token Railway. Adapter não arranca sem isto. |
| `HRC_ADAPTER_API_BASE` | `https://poker-app-production-34a7.up.railway.app` | Só mudar para testar contra outro backend. |
| `HRC_ADAPTER_QUEUE_DIR` | `C:\Users\Administrator\Documents\Teste completo` | Só mudar se mudar o setup do watcher. |
| `HRC_POLL_INTERVAL_S` | `60` | Intervalo entre pulls. Baixar para `15` em debug. |

## Reset / cleanup

- **Soft reset** (re-tentar 1 mão que ficou em failed): editar
  `state.json` à mão e apagar essa entrada. Salvar. Próximo pull
  re-descomprime se o backend ainda a devolver.
- **Hard reset**: parar adapter → apagar `state.json` → arrancar. Apaga
  também a pasta de qualquer mão pendente em `Teste completo\<hand_id>\`
  para evitar duplo.

## Troubleshooting

- **"env HRC_WATCHER_API_KEY ausente"** no arranque: abriste uma sessão
  PowerShell **nova** depois do `setx`? `setx` só é visível em sessões
  abertas **após** ele.
- **`pull: 401`** repetido: token errado. Confere o valor no Railway →
  service `poker-app` → variables.
- **`pull: zip corrupto`** recorrente: provável network glitch. Testa:
  `curl https://poker-app-production-34a7.up.railway.app/health` deve
  dar `200`.
- **Pastas a acumular em `Teste completo\arquivo\`**: normal. Watcher
  arquiva mãos processadas com sucesso; adapter não toca. Limpa
  manualmente quando achares.
- **Mãos que continuam a aparecer no pull mesmo após `status=done`**:
  esperado por agora — backend ainda não filtra `GET /api/queue/hrc` por
  `hrc_jobs.status`. O `state.json` local trata o dedup. Tech debt
  servidor para sessão futura.
