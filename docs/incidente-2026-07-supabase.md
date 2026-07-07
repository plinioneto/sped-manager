# Incidente — perda de dados no Supabase (julho/2026)

## Resumo

Em 06/07/2026 percebeu-se que as tabelas do SPED Manager (`notas_fiscais`, `gold_kpis_mensais`, `produtos`, etc.) haviam desaparecido do projeto Supabase `gzhcbrfbphqzhpvrsraa`. Investigação mostrou que o projeto estava sendo **compartilhado com uma aplicação de terceiros** (sistema de logística/consultoria, schema em PascalCase típico de Prisma — `Cliente`, `Embarque`, `Consultor`, `Gestor`, `RefreshToken`, etc.). Um deploy/migração dessa outra aplicação recriou o schema `public` do zero, apagando todas as tabelas do SPED Manager, e trocou a senha do Postgres no processo.

Os dados brutos (EFD `.txt` e XML) permaneceram intactos no Cloudflare R2 (camada bronze), então nenhuma informação foi perdida de forma definitiva — só era preciso reconstruir as camadas silver/gold.

## Linha do tempo da investigação

1. `.env` apontava para `db.gzhcbrfbphqzhpvrsraa.supabase.co`, mas a conexão falhava com `FATAL: password authentication failed` — indicava que a senha havia mudado, não apenas que as tabelas estavam vazias.
2. Descartada a hipótese de downgrade acidental do Alembic (as tabelas com nomes antigos do rename `c7d8e9f0a1b2` também não existiam).
3. Confirmado no dashboard do Supabase: a referência do projeto batia (`gzhcbrfbphqzhpvrsraa`), mas as tabelas visíveis eram de outro schema completamente diferente (Prisma).
4. Confirmado que o bucket R2 `sped-manager` ainda tinha os arquivos brutos de EFD e XML.
5. Decisão: criar um projeto Supabase novo e dedicado só ao SPED Manager, em vez de tentar reaver o projeto antigo (que pertence/é compartilhado por outra equipe).

## Causa raiz

Reuso indevido do mesmo projeto Supabase por duas aplicações sem relação entre si. Sem isolamento de projeto, qualquer migração destrutiva de uma aplicação afeta a outra.

## Bugs encontrados durante a recuperação

Dois bugs pré-existentes no repositório dificultaram a reconstrução e foram corrigidos nesta mesma janela de trabalho:

### 1. `app/utils/db.py` sobrescrevia `DATABASE_URL` do `.env` com `.streamlit/secrets.toml`

O bloco que populava `os.environ` a partir de `st.secrets` (destinado ao deploy no Streamlit Cloud, onde não há `.env` persistente) rodava incondicionalmente, mesmo fora do Streamlit Cloud. O simples acesso a `st.secrets` faz o Streamlit carregar `secrets.toml` e, como efeito colateral, sobrescrever `os.environ` inteiro — inclusive chaves que o `.env` já tinha carregado corretamente. Como `secrets.toml` ainda apontava para o projeto Supabase antigo/comprometido, qualquer script que importasse `app.utils.db` (praticamente todos) acabava reconectando no banco errado, mesmo com o `.env` atualizado.

Já havia sido corrigido no `alembic/env.py` em commit anterior (`fix(deploy): remove st.secrets de alembic/env.py`), mas não em `db.py`. Como o Streamlit não será mais usado (decisão confirmada nesta conversa), o bloco foi removido de `app/utils/db.py` em vez de corrigido — `.streamlit/secrets.toml` não precisa mais ser mantido sincronizado.

### 2. `scripts/backfill_padronizacao.py` excluía produtos com `origem_padronizacao IS NULL`

O filtro `~Produto.origem_padronizacao.in_(["manual", "manual_sem_cat"])` usa lógica de três valores do SQL: para linhas com `origem_padronizacao IS NULL`, `NOT (NULL IN (...))` avalia para `NULL`, não `TRUE`, e a linha é excluída do resultado. Isso faz o script relatar "0 produtos a processar" exatamente para produtos recém-importados via `--skip-padronizacao` (o cenário descrito no próprio `CLAUDE.md`, Passo 1) — o caso de uso mais comum do script.

Corrigido para incluir explicitamente `origem_padronizacao IS NULL` na condição de proteção às classificações manuais.

## Recuperação executada

1. Projeto Supabase novo criado (`db.igcijtotftagasgwpuyu.supabase.co`); `.env` atualizado.
2. `alembic upgrade 8f8fc05b0864` + `alembic stamp head` — a migration inicial usa `Base.metadata.create_all()` (reflete os models atuais, já com os nomes/schema finais), então recria o schema correto de uma vez; as migrations intermediárias (`model_review_v2`, rename, float→numeric) ficaram órfãs para banco novo e foram puladas via stamp.
   - **Atenção**: esse encadeamento de migrations não é replicável do zero em um banco novo sem esse workaround. Vale revisar/consolidar as migrations num único ponto de partida limpo (squash) em algum momento.
3. `scripts/seed_supabase.py` — repovoou hierarquia de categorias (18 departamentos / 118 grupos / 720 categorias), fabricantes/marcas (67 fabricantes, 289 marcas) e tenants (GS, Posto Jaguar, Franmak) a partir dos backups locais (`categorias.db`, `sped_manager.db`).
4. `scripts/importar_efd.py --pasta "D:/Data Science/Projeto SPED/data" --skip-padronizacao` — reimportou os 8 arquivos EFD (GS Jan–Jul/2025 + Posto Jaguar out/2025) direto dos arquivos locais/R2. 0 erros.
5. `scripts/backfill_padronizacao.py --todos` (após o fix do item 2 acima) — 4.332 produtos processados, 90% de taxa de classificação, 0 erros.
6. `gold_kpis_mensais` conferido: 7 meses para o tenant GS (id 1) + 1 mês para Posto Jaguar (id 2) — mesmo estado que existia antes do incidente.

## Pendências

- **Franmak** (tenant cadastrado, só dados XML — entrada e NFC-e) ainda não foi reimportada; não estava coberta pelo Passo 1 original.
- **A A Miranda Comercial**: pasta de EFD existe localmente mas não há tenant cadastrado para o CNPJ `05370363000132` — verificar se deveria ser onboardada.
- Avaliar squash das migrations do Alembic para eliminar a dependência do workaround (`upgrade <rev> + stamp head`) em reconstruções futuras.
- Garantir que o projeto Supabase antigo (`gzhcbrfbphqzhpvrsraa`) não seja mais referenciado em nenhuma configuração do SPED Manager.
