# Poker App - Guia de Onboarding para Operador

Bem-vindo ao projecto. Este documento serve como base de conhecimento para assumires a execução técnica da aplicação, enquanto eu (Manus) assumo o papel de coordenador e revisor da arquitectura.

## 1. Contexto e Inspiração

A aplicação nasceu da necessidade de criar um fluxo de estudo de poker altamente eficiente e focado na prática real do jogador. Inspiramo-nos em ferramentas analíticas de mercado (como PokerTracker, Holdem Manager e GTO Wizard), mas com um foco muito específico: **reduzir a fricção entre jogar, marcar uma mão com dúvida e estudá-la posteriormente**.

O problema central que resolvemos é o facto de salas como a GGPoker anonimizarem os ficheiros de Hand History (HH). Quando o jogador tem uma dúvida durante o jogo, tira um screenshot. A nossa app cruza a informação visual desse screenshot com o ficheiro HH (importado mais tarde) para reconstruir a mão perfeita: com acções matemáticas exactas (do HH) e os nomes reais dos vilões e bounties (do screenshot).

## 2. Objectivos do Projecto

O objectivo principal é manter um sistema web-based, sempre operacional, que permita:
1. **Arquivo de Torneios (MTT):** Importação em bulk de ficheiros zip contendo HHs e summaries. Estas mãos servem para registo estatístico e arquivo, não poluindo o fluxo de estudo.
2. **Fluxo de Estudo (Inbox/Mãos):** Mãos marcadas via screenshot entram num funil de estudo (`new` -> `review` -> `studying` -> `resolved`).
3. **Enriquecimento de Dados:** Fazer o *match* automático entre os screenshots (processados via LLM Vision) e as mãos do arquivo MTT, revelando os nomes reais dos jogadores e outras dinâmicas de mesa.
4. **Gestão de Vilões e P&L:** Acompanhamento de notas de jogadores e resultados financeiros por sala.

## 3. Arquitectura e Stack Tecnológica

A aplicação segue uma arquitectura cliente-servidor clássica, desenhada para ser pragmática e de fácil manutenção:

*   **Frontend:** React (Vite), JavaScript/JSX, CSS puro/Tailwind. Focado em componentes modulares e chamadas à API via um cliente centralizado (`src/api/client.js`).
*   **Backend:** Python com FastAPI. Roteamento modular (`routers/`), serviços de lógica de negócio (`services/`) e parsers específicos para cada sala de poker (`parsers/`).
*   **Base de Dados:** PostgreSQL. A tabela central é a `hands`, que se relaciona com `tournaments`, `entries` (ficheiros importados) e `villain_notes`.
*   **Integrações:** OpenAI (GPT-4o-mini/Vision) para extracção de dados de imagens; Discord para sincronização de mãos partilhadas em canais de estudo.
*   **Infraestrutura:** Deploy contínuo via GitHub para a plataforma Railway.

## 4. Estado Actual e Decisões de Design Recentes

Recentemente, reestruturámos a forma como as mãos são categorizadas para evitar que o fluxo de estudo ficasse inundado com milhares de mãos irrelevantes:

*   **Separação MTT vs Estudo:** Quando um zip de HH é importado, as mãos recebem o `study_state = 'mtt_archive'`. Elas ficam visíveis apenas na nova secção **MTT** (drill-down por torneio).
*   **Criação de Mãos de Estudo:** Apenas mãos que recebem um screenshot (ou são marcadas manualmente) entram no estado `new` e aparecem na aba **Mãos** e na **Inbox**.
*   **Match Screenshot ↔ HH:** O backend (`screenshot.py`) extrai a data, hora e TM number do nome do ficheiro do screenshot (fonte primária de verdade) e usa o Vision para extrair posições, stacks e nomes. Depois, cruza a posição do jogador no screenshot com a posição no HH para mapear os IDs anónimos da GGPoker para os nomes reais.

## 5. Desafios e Soluções Implementadas (Erros Conhecidos)

Durante o desenvolvimento, enfrentámos e resolvemos vários desafios que deves ter em mente:

1.  **Anonimização da GGPoker:** O HH da GG usa hashes (ex: `89ef4cba`) em vez de nomes. *Solução:* O parser não tenta adivinhar nomes. O mapeamento é feito estritamente por posição na mesa quando o screenshot é processado.
2.  **Alucinações do Vision:** O modelo de visão por vezes falha a ler o valor exacto das blinds ou o ante na imagem. *Solução:* Passámos a extrair esses dados de forma determinística a partir do nome do ficheiro gerado pela GGPoker (ex: `2026-03-06_06_02_PM_2,000_4,000(500)_#TM5672663145.png`).
3.  **Nomenclatura de Posições:** O Vision devolvia posições como `UTG+1`, enquanto o frontend esperava `UTG1`. *Solução:* Implementada uma função de normalização no backend antes de guardar na base de dados.

## 6. Próximos Passos (Roadmap para o Operador)

Como operador, as tuas próximas tarefas focar-se-ão em refinar a experiência do utilizador e robustecer o backend:

1.  **Refinamento da Inbox:** Garantir que a página Inbox lida perfeitamente com o novo paradigma (apenas mãos `new` aparecem; uploads de zip vão silenciosamente para o arquivo MTT sem poluir a Inbox).
2.  **Gestão de Mãos Órfãs:** Criar um mecanismo visual para screenshots que foram submetidos mas cuja HH ainda não foi importada (aguardando match).
3.  **Expansão de Parsers:** Garantir que o parser da Winamax e PokerStars segue a mesma lógica de separação de arquivo vs estudo, adaptando as expressões regulares conforme necessário.
4.  **Filtros Avançados:** Melhorar a pesquisa na aba Mãos para permitir filtrar por vilões específicos (agora que temos os nomes reais mapeados).

## 7. Regras de Colaboração

A partir de agora, o fluxo de trabalho será o seguinte:
*   O utilizador define os requisitos de negócio.
*   **Eu (Coordenador):** Analiso o pedido, defino a arquitectura, indico os ficheiros a alterar, prevejo *edge cases* e dou-te as instruções técnicas precisas.
*   **Tu (Operador):** Escreves o código, testas localmente e fazes os commits.
*   **Eu (Coordenador):** Revejo o teu trabalho (code review) e autorizo o deploy.

Lê o código existente, especialmente `backend/app/routers/screenshot.py`, `backend/app/services/hand_service.py` e `frontend/src/pages/Tournaments.jsx` para te familiarizares com os padrões actuais. Bom trabalho!
