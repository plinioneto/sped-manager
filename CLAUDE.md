# SPED Manager

## Contexto

Sistema de gestão fiscal para supermercados baseado em arquivos EFD (SPED Fiscal) e XML NFC-e/NF-e.
Multi-tenant (uma instância, N clientes). Streamlit legado em transição para FastAPI + React + Tremor.

## Stack

| Camada | Tecnologia | Status |
|--------|-----------|--------|
| Backend API | FastAPI (`api/`) | ✅ estrutura base criada |
| Frontend | React + Tremor | ⏳ a criar |
| Auth | JWT bcrypt (`api/auth.py`) | ✅ implementado |
| Banco | Supabase PostgreSQL (prod) / SQLite (dev) | ✅ ativo |
| Armazenamento raw | Cloudflare R2 (`app/utils/r2.py`) | ✅ ativo |
| Interface legada | Streamlit (`app/pages/`) | ⚠ em transição |
| ORM | SQLAlchemy + Alembic | ✅ ativo |
| Python | 3.11+ | — |

**O que migra sem tocar:** `app/models/`, `app/repositories/`, `app/services/`, `app/parser/`, `app/utils/`
**O que é reescrito:** `app/pages/` (camada UI substituída pelo React)

---

## Estrutura de pastas

```
api/                    FastAPI: main.py, auth.py, deps.py, routers/
app/
  models/               SQLAlchemy ORM
  repositories/         acesso ao banco (sempre filtram por tenant_id)
  services/             lógica de negócio
  parser/               silver.py (EFD), xml_parser.py (NFC-e/NF-e), renomeador.py
  utils/                db.py, r2.py, formatters.py, theme.py
  components/           sidebar.py, filtro_hierarquia.py
  pages/                telas Streamlit (legadas)
scripts/                importar_efd.py, importar_xmls_pasta.py,
                        backfill_padronizacao.py, seed_fabricantes_marcas.py
docs/                   arquitetura-dados.md, dicionario-de-dados.md, ...
alembic/                migrations
```

---

## Modelos e tabelas

### Por tenant (filtrar sempre por tenant_id)

| Model | Tabela | Descrição |
|-------|--------|-----------|
| Tenant | `lojas` | Empresa/supermercado; CNPJ 14 dígitos sem máscara |
| DocumentoFiscal | `notas_fiscais` | C100 + NF-e/NFC-e XML; chave única: tenant_id + chv_nfe |
| ItemFiscal | `itens_nota_fiscal` | C170; chave única: tenant_id + chv_nfe + num_item |
| IcmsC190 | `resumo_fiscal` | C190 agrupado por CST/CFOP/alíq |
| Participante | `fornecedores` | 0150 + emitentes XML |
| Produto | `produtos` | 0200 + padronização + FK para Marca/Categoria |
| ArquivoImportado | `arquivos_importados` | histórico de importações EFD e XML |
| InventarioH005/H010 | `inventario_h005/h010` | cabeçalho e itens de inventário |
| EstoqueK200 | `estoque_k200` | saldo de estoque |
| GoldKpisMensais | `gold_kpis_mensais` | KPIs pré-calculados por tenant+mês |

### Globais (sem tenant_id)

| Model | Tabela | Descrição |
|-------|--------|-----------|
| GrupoEmpresarial | `grupos_empresariais` | agrupa tenants do mesmo dono |
| Fabricante | `fabricantes` | 45 seedados; aliases JSON |
| Marca | `marcas` | 225 seedadas; FK → Fabricante |
| Departamento/Grupo/Categoria | `departamentos_produto`, `grupos_produto`, `categorias_produto` | hierarquia 18 > 118 > 720 |
| CatalogoProduto | `catalogo_produtos` | herança de classificação por EAN entre tenants |
| TokenDesconhecido | `tokens_desconhecidos` | tokens não reconhecidos pelo pipeline |

---

## Regras críticas de código

- **tenant_id em toda query** — sem exceção; repositories herdam de BaseRepository
- **CNPJ sem máscara** no banco (14 dígitos); formatar só na exibição com `formatar_cnpj()`
- **Encoding latin-1** nos arquivos EFD
- **Arquivos nomeados** `CNPJ_YYYYMMDD_YYYYMMDD.txt` (via `renomeador.py`)
- **Auth Streamlit:** `session_state` com tenant_id; guard no topo de cada página:
  ```python
  if not st.session_state.get("tenant_id"):
      st.switch_page("main.py")
  ```
- **Auth FastAPI:** JWT Bearer — `Depends(get_tenant)` em toda rota protegida
- **Sessões:** sempre usar `with get_db() as db:` (context manager) — nunca `db.close()` manual
- **Imports de models:** sempre via `import app.models` (registra todos no Base)
- **Upsert** em todos os registros silver (nunca insert cego)
- **Services** recebem `session + tenant_id`; repositories herdam de `BaseRepository`

---

## Arquitetura de dados

Ver [`docs/arquitetura-dados.md`](docs/arquitetura-dados.md) para o documento completo.

**Resumo das camadas:**
- **Bronze (R2):** arquivos brutos permanentes — `efd/{cnpj}/{nome}.txt`, `xml/{cnpj}/{chv}.xml`
- **Silver (Supabase):** tabelas estruturais leves (~1,2 GB com 100 clientes em 3 anos) — ficam para sempre
- **Gold (Supabase):** agregações pré-calculadas consumidas pelo FastAPI/React — `gold_kpis_mensais` e futuras
- **`itens_nota_fiscal` NFC-e saídas** não é persistida (~300 GB em escala) — XML fica no R2

---

## Estado atual

### Pipeline de importação

| Etapa | Status | Observações |
|-------|--------|-------------|
| Renomeação | ✅ | `CNPJ_YYYYMMDD_YYYYMMDD.txt` via `renomeador.py` |
| Bronze R2 | ✅ | arquivo bruto enviado ao R2; `efd_raw` eliminada |
| Silver C100 | ✅ | todos os campos → `notas_fiscais` |
| Silver C170 | ✅ | todos os campos → `itens_nota_fiscal` |
| Silver 0200 | ✅ | todos os campos → `produtos` |
| Silver C190 | ✅ | upsert por CST/CFOP/alíq → `resumo_fiscal` |
| Silver H005/H010 | ✅ | inventário |
| Silver K200 | ✅ | saldo de estoque |
| Silver 0150 | ✅ | participantes → `fornecedores` |
| XML NFC-e/NF-e | ✅ | `xml_parser.py`; dedup por chv_nfe; sobe ao R2 (`xml/{cnpj}/{chv}.xml`) antes de persistir, em paralelo (`upload_lote`); itens de NFC-e saída (mod=65) não vão para `itens_nota_fiscal` — só entrada |
| Gold KPIs | ✅ | `gold_kpis_service.py`; XML recalcula por mês tocado (`processar` direto, `processar_lote` via `meses_tocados` no chamador) |

### API FastAPI (`api/`)

| Rota | Status |
|------|--------|
| `POST /auth/token` | ✅ login CNPJ + senha → JWT |
| `POST /auth/senha` | ✅ define senha (primeira vez) |
| `GET /auth/me` | ✅ dados do tenant autenticado |
| `GET /kpis/mensais` | ✅ todos os meses do tenant |
| `GET /kpis/mensais/{ano}/{mes}` | ✅ mês específico |
| `/compras/*`, `/fiscal/*`, `/produtos/*` | ⏳ a criar |
| `POST /importar/efd`, `/importar/xml` | ⏳ a criar |

### Páginas Streamlit (legado)

| Página | Status |
|--------|--------|
| 00_inicio.py | ✅ dashboard executivo |
| 01_gestao_vendas.py | ✅ vendas (limitado sem XML NFC-e) |
| 02_compras.py | ✅ notas entrada, fornecedor, produto |
| 03_gestao_fiscal.py | ✅ ICMS, ST, PIS/COFINS, diagnóstico |
| 04_inventario.py | ✅ estoque virtual, H005/H010, K200 |
| 05_produtos.py | ✅ cadastro, padronização, inteligência |
| 06_dados.py | ✅ upload EFD/XML + histórico |
| 08_admin_revisao.py | ✅ painel admin (revisão, marcas, clientes, grupos) |
| 07_configuracoes.py | ⏳ pendente |

---

## 🎯 Próximos passos — MVP

> Seguir esta ordem evita retrabalho. Atualizado em 2026-06-22.

### Passo 1 — Dados completos no banco ✅
- [x] Importar Mar–Jul/2025: `python scripts/importar_efd.py --pasta "D:/Data Science/Projeto SPED/data/GS" --skip-padronizacao`
- [x] Backfill após importação: `python scripts/backfill_padronizacao.py --todos`
- [x] Confirmar `gold_kpis_mensais` populado para os 7 meses (Jan–Jul/2025, tenant_id=1)
- [x] Reconstruído em projeto Supabase novo após incidente de perda de dados — ver [`docs/incidente-2026-07-supabase.md`](docs/incidente-2026-07-supabase.md)
- [x] Reimportar XML da Franmak (entrada + NFC-e) — 2026-07-08: 248.152 documentos (1.578 entrada + 246.574 NFC-e saída), escopo 2025–2026. Itens de NFC-e saída não persistidos em `itens_nota_fiscal` por decisão de arquitetura (só entrada); upload ao R2 paralelizado (`upload_lote`, ThreadPoolExecutor) — sequencial levaria dias em ~250 mil arquivos
- [ ] Decidir se "A A Miranda Comercial" (CNPJ 05370363000132) deve virar tenant — EFD local existe mas não há cadastro

### Passo 2 — Corrigir pipeline XML ✅
- [x] Adicionar `upload_bytes()` no `xml_parser.py` antes de processar
- [x] Recalcular gold ao final do processamento (`calcular_kpis_mes`, por mês tocado)

### Passo 3 — Rotas FastAPI restantes
- [ ] `api/routers/compras.py` — GET /compras/mensais, /compras/fornecedores
- [ ] `api/routers/fiscal.py` — GET /fiscal/mensal, /fiscal/cfop
- [ ] `api/routers/produtos.py` — GET /produtos, /produtos/{cod_item}
- [ ] `api/routers/importar.py` — POST /importar/efd, /importar/xml

### Passo 4 — Tabelas gold complementares
- [ ] `gold_compras_fornecedor` — migration + service + rota
- [ ] `gold_fiscal_cfop` — migration + service + rota
- [ ] `gold_estoque_atual` — migration + service + rota

### Passo 5 — Deploy da API
- [ ] Deploy FastAPI no Railway ou Render
- [ ] Variáveis de ambiente configuradas (ver seção abaixo)
- [ ] URL pública testada contra Supabase

### Passo 6 — Frontend React + Tremor
- [ ] Setup: Vite + React + Tremor + React Query
- [ ] Tela de login (CNPJ + senha → JWT)
- [ ] Dashboard: cards KPI + evolução mensal
- [ ] Páginas de compras e fiscal
- [ ] Upload de EFD/XML pela interface
- [ ] Deploy no Vercel

### Passo 7 — Desligar Streamlit
- [ ] Paridade funcional verificada
- [ ] Streamlit desligado (ou mantido só para admin interno)

---

## Backlog pós-MVP

### Qualidade
- [ ] **Categorizador no banco** — tabelas `regras_abreviacao` e `regras_categorizacao` editáveis pelo admin; elimina ciclo "edita Python → deploy"
- [ ] **Classificação por IA/LLM como fallback** — produtos com `revisao_necessaria=True` (pipeline de regras não cobriu) caem numa chamada de LLM antes de ir pra fila de revisão manual; reduziria o volume da fila e aumentaria a cobertura além dos ~70,6% atuais
- [ ] **Recalibrar como o score de confiança é calculado** — hoje `categorizador.py` usa constantes fixas por regra (0.98/0.97/0.95/0.90) e Jaccard como fallback (`app/services/produto_padronizacao/categorizador.py:891-981`), sem calibração contra acerto real; motivou o corte por score em `catalogo_repo.py` (2026-07-07) — vale revisar se os números realmente refletem confiança antes de depender mais deles
- [ ] **Dicionário de sabor/variante** — hoje só existe `_ATRIBUTOS` (ZERO, LIGHT, TRADICIONAL...); sabor específico por categoria (morango, uva, laranja...) não é extraído como campo próprio, fica misturado no resíduo da descrição padronizada. Diferente de categoria (mundo fechado, 720 categorias) e marca (~centenas), sabor é mundo aberto — nunca vai "terminar" de mapear. Popular só os ~50–100 mais frequentes via fila; o resto fica pro fallback de IA/LLM (item acima) quando existir, não insistir via dicionário manual
- [ ] **Auditar outras marcas com nome canônico divergente do banco** — achado em 2026-07-08: `identificador.py` tinha `"COCA COLA"` (sem hífen) como chave canônica, mas o banco tem `"COCA-COLA"` (com hífen, grafia correta) cadastrado; como `backfill_padronizacao.py` faz `Marca.nome == resultado.marca`, a marca nunca linkava (`marca_id` ficava `None` em **todo** produto Coca-Cola do sistema, não só um). Corrigido pontualmente, mas pode haver outras marcas do dicionário fixo (`MARCAS_CONHECIDAS` em `identificador.py`) com o mesmo problema — vale comparar as ~90 chaves do dicionário fixo contra `SELECT nome FROM marcas` pra achar divergências de grafia
- [ ] **Revisar match de categoria por token único (`_melhor_match`)** — corrigido em 2026-07-08 pra exigir que o token seja a primeira palavra da descrição (evitava ex: "HAV KIDS FLORES" batendo grupo Hortifruti/Flores), mas a proteção é heurística (posição, não semântica) — vale medir quantos produtos legítimos perderam classificação automática por isso (ex: itens que citam o ingrediente no meio da descrição) e considerar sinal adicional (marca reconhecida, unidade tipo KG/UN) em vez de só posição
- [ ] **Dividir `08_admin_revisao.py`** — 1.400+ linhas; separar em módulos por domínio
- [ ] **Testes de unidade** — parser silver + `processar_descricao`; 20–30 testes dão segurança para refatorar
- [ ] **Definir tipo de cliente foco** — fiscal (contador) ou gestão (dono de loja)
- [ ] **Revisão de scripts/** — auditar e remover scripts obsoletos; manter apenas o necessário. Lista atual:
  - `importar_efd.py` — ✅ pipeline principal, manter
  - `backfill_padronizacao.py` — ✅ utilitário recorrente, manter (bug do filtro `NULL` corrigido em 2026-07-06, ver incidente)
  - `seed_fabricantes_marcas.py` — ✅ seed idempotente, manter
  - `seed_supabase.py` — ✅ bootstrap completo (categorias + fabricantes/marcas + tenants); confirmado útil na reconstrução pós-incidente de 2026-07, manter
  - `importar_xmls_pasta.py` — ⚠ avaliar se ainda necessário com `/importar/xml`
  - `importar_xmls_bulk.py` — ⚠ avaliar duplicidade com `importar_xmls_pasta.py`
  - `backfill_catalogo_ean.py` — ✅ manter, mas só como utilitário isolado; `backfill_padronizacao.py` já sincroniza `catalogo_produtos` sozinho desde 2026-07-08 (evita o erro de esquecer o segundo passo)
  - `seed_aliases_cervejas.py` — ⚠ provavelmente absorvido por `seed_fabricantes_marcas.py`
  - `check_cobertura.py` / `check_cobertura2.py` — ⚠ scripts de diagnóstico duplicados; unificar ou remover
  - `check_categorias_db.py` — ⚠ diagnóstico pontual; avaliar remoção
  - `apagar_ano.py` — ⚠ operação destrutiva; avaliar se tem uso legítimo ou deve ser removido
  - `liberar_espaco_supabase.py` — ⚠ operação destrutiva; avaliar necessidade
  - `_truncate_silver.py` — ⚠ prefixo `_` indica abandono; remover
  - **Criar** `recalcular_gold_kpis.py` — recalcula gold para todos os tenants com base nas notas_fiscais (evita recálculo manual com tenant_id avulso)
- [ ] **Squash das migrations do Alembic** — `8f8fc05b0864_initial_schema.py` usa `Base.metadata.create_all()` (reflete os models atuais), o que quebra a cadeia completa em um banco novo do zero (migrations intermediárias tentam alterar tabelas com nomes que já nasceram diferentes). Hoje contorna-se com `alembic upgrade 8f8fc05b0864 && alembic stamp head`; o ideal é squashar tudo numa migration inicial única e correta. Ver [`docs/incidente-2026-07-supabase.md`](docs/incidente-2026-07-supabase.md)
- [ ] **Confirmar que nada mais referencia o projeto Supabase antigo** (`gzhcbrfbphqzhpvrsraa`) — checar deploys (Railway/Render), outros `.env` locais e o `.claude/worktrees/` antes de considerar o incidente 100% encerrado

### Escala (pós 50+ clientes)
- [ ] **Dados anônimos para indústrias** — modelo IRI/Nielsen; requer ~50–100 lojas + contrato de uso secundário
- [ ] **Modelo supervisionado de categorização** — TF-IDF + Naive Bayes após ~500 revisões manuais; aumenta cobertura de ~70% para ~90%+
- [ ] **Embeddings para produtos similares** — detecta duplicatas entre tenants; custo alto, só com volume

### Documentação técnica (`docs/`)

| Arquivo | Status |
|---------|--------|
| `docs/arquitetura-dados.md` | ✅ |
| `docs/dicionario-de-dados.md` | ✅ |
| `docs/pipeline-de-dados.md` | ⏳ |
| `docs/pipeline-padronizacao.md` | ⏳ |
| `docs/guia-de-desenvolvimento.md` | ✅ |

---

## Variáveis de ambiente (`.env`)

| Variável | Descrição |
|----------|-----------|
| `DATABASE_URL` | PostgreSQL Supabase ou `sqlite:///./sped_manager.db`. **Preferir connection pooling** (`postgresql://postgres.{project-ref}:{senha}@aws-{n}-{regiao}.pooler.supabase.com:5432/postgres`) em vez da conexão direta (`db.{project-ref}.supabase.co`) — o hostname direto teve falha de DNS persistente em 2026-07-08 (não era da rede local: outros domínios resolviam normal). String exata do pooler fica no painel Supabase em Settings → Database → Connection pooling (a região/número `aws-N` não dá pra adivinhar) |
| `JWT_SECRET` | Chave secreta JWT (obrigatório) |
| `JWT_TTL_HOURS` | Validade do token em horas (padrão: 24) |
| `R2_ENDPOINT` | Endpoint Cloudflare R2 |
| `R2_ACCESS_KEY` | Access key do bucket |
| `R2_SECRET_KEY` | Secret key do bucket |
| `R2_BUCKET` | Nome do bucket (padrão: sped-manager) |
| `ADMIN_PASSWORD` | Senha do painel admin Streamlit (obrigatório) |
| `CORS_ORIGINS` | Origens permitidas no FastAPI (padrão: http://localhost:5173) |

---

## Pipeline de padronização de produtos

Pipeline em `app/services/produto_padronizacao/`:
1. `limpeza.py` — uppercase, remove acentos e stopwords promocionais
2. `dicionarios.py` — expansão de ~120 abreviações + contextuais (DES, TP…)
3. `unidades.py` — extração de peso/volume via regex
4. `identificador.py` — detecção de marca/fabricante: match exato + fuzzy RapidFuzz (threshold=90)
5. `pipeline.py` — extração de atributos (ZERO, LIGHT…); montagem canônica: base + atributos + embalagem + volume
6. `categorizador.py` — VOCAB_CATEGORIA → VOCAB_TIPO_PRODUTO → VOCAB_HORTIFRUTI → Jaccard fallback

Cobertura automática: **~70%** (medido em 2026-07-08 após correções de negação/composto/hortifruti, 22.078 produtos, 3 tenants; caiu de ~74% — o fix tira confiança falsa de casos ambíguos, jogando mais itens pra revisão manual em vez de categorizar errado). Produtos com `origem_padronizacao='manual'` nunca são sobrescritos pelo backfill.

Scripts:
- `scripts/backfill_padronizacao.py --todos` — reprocessa tudo exceto manuais
- `scripts/backfill_padronizacao.py --force` — sobrescreve inclusive manuais
- `scripts/seed_fabricantes_marcas.py` — popula fabricantes/marcas no banco

### Fila de adições

Use esta seção para acumular entradas antes de pedir "aplica a fila de padronização".

**Abreviações** — `abrev` → `expansão` (→ `dicionarios.py`)
**Categorias** — `keyword` → `Departamento > Grupo > Categoria` (→ `categorizador.py`)
**Combinações não adjacentes** — `{TOKEN_A, TOKEN_B}` → `Depto > Grupo > Cat` (→ `_VOCAB_COMBINACAO`)
**Marcas** — `Nome | Fabricante | aliases` (→ `identificador.py`)
**Fabricantes** — `Nome | aliases`

#### ✏️ Fila — preencha abaixo

##### Abreviações
##### Categorias
##### Combinações não adjacentes
##### Marcas
##### Fabricantes

---

### ✅ Histórico de adições aplicadas

| Data | Tipo | Entrada |
|------|------|---------|
| 2026-04-09 | Abreviação | `grf`, `gf`, `gfa` → garrafa |
| 2026-04-09 | Abreviação | `guar` → guarana |
| 2026-04-09 | Abreviação | `parbo` → parbolizado |
| 2026-04-09 | Combinação | `{DESODORANTE, ROLLON}` → Perfumaria > Desodorantes e Colônias > Desodorante Rollon |
| 2026-04-09 | Combinação | `{DESODORANTE, CREME}` → Perfumaria > Desodorantes e Colônias > Desodorante Creme |
| 2026-04-09 | Combinação | `{OLEO, CAPILAR}` → Perfumaria > Produtos Capilares > Cremes p/ Hidratação |
| 2026-04-09 | Combinação | `{SAL, GROSSO}` → Commodities > Sal > Sal Grosso |
| 2026-04-09 | Marca | KUAT \| COCA-COLA FEMSA |
| 2026-04-09 | Abreviação | `conf` → confeito |
| 2026-04-09 | Fabricante | FINI |
| 2026-04-09 | Fabricante | CERVEJARIA CIDADE IMPERIAL |
| 2026-04-09 | Fabricante | CERVEJARIA BRUDER |
| 2026-04-09 | Fabricante | HIJOS DE RIVERA |
| 2026-04-09 | Marca | FINI \| FINI |
| 2026-04-09 | Marca | THEREZOPOLIS \| COCA-COLA FEMSA \| THEREZOP |
| 2026-04-09 | Marca | IMPERIO \| CERVEJARIA CIDADE IMPERIAL |
| 2026-04-09 | Marca | PURO MALTE PILSEN \| CERVEJARIA CIDADE IMPERIAL \| PURO MALTE |
| 2026-04-09 | Marca | BG \| CERVEJARIA BRUDER \| BAIXA GASTRONOMIA |
| 2026-04-09 | Marca | ESTRELLA GALICIA \| HIJOS DE RIVERA \| ESTRELLA |
| 2026-04-02 | Abreviação | `amac` → amaciante |
| 2026-04-02 | Abreviação | `acai` → açaí |
| 2026-04-02 | Abreviação | `ap barbear` → aparelho de barbear |
| 2026-04-02 | Abreviação | `ap bar` → aparelho de barbear |
| 2026-04-02 | Abreviação | `ap prest` → aparelho de barbear |
| 2026-04-02 | Abreviação | `odoriz` → odorizador |
| 2026-04-02 | Categoria | `acai` → Perecíveis do Autoserviço > Congelados > Sorvetes/Açaí |
| 2026-04-02 | Categoria | `agua sanitaria` → Limpeza > Limpeza para Roupas > Água Sanitária |
| 2026-04-02 | Categoria | `aparelho de barbear` → Perfumaria > Barbearia > Aparelhos Descartáveis |
| 2026-04-02 | Categoria | `odoriz` → Limpeza > Limpeza de Casa > Odorizador de Ambiente |
| 2026-04-02 | Marca | GILLETTE \| P&G \| PRESTOBARBA, PRESTO BARBA |
| 2026-04-02 | Abreviação | `aperit` → aperitivo |
| 2026-04-02 | Abreviação | `ativ cachos` → ativador de cachos |
| 2026-04-02 | Categoria | `aperitivo` → Perecíveis do Autoserviço > Empório Granel > Aperitivos em Geral |
| 2026-04-02 | Categoria | `apontador` → Bazar Geral > Artigos para Papelaria e Armarinho > Apontadores em Geral |
| 2026-04-02 | Categoria | `ativador de cachos` → Perfumaria > Produtos Capilares > Creme para Pentear |
| 2026-04-02 | Categoria | `aveia` → Mercearia Doce > Matinais > Cereais |
| 2026-04-03 | Abreviação | `sand hav` → sandalia havaiana |
| 2026-04-03 | Abreviação | `beb lactea` → bebida lactea |
| 2026-04-03 | Abreviação | `gelat` → gelatina |
| 2026-04-03 | Abreviação | `sorv` → sorvete |
| 2026-04-03 | Abreviação | `ref po` → refresco em po |
| 2026-04-03 | Categoria | `elma chips` / `batata elma chips` → Mercearia Doce > Salgadinhos > Batata Frita |
| 2026-04-03 | Categoria | `batata pre frita` / `pre frita` → Perecíveis do Autoserviço > Congelados > Batata Congelada |
| 2026-04-03 | Categoria | `chicle` → Mercearia Doce > Guloseimas > Goma de Mascar |
| 2026-04-03 | Categoria | `bolinho` → Mercearia Doce > Biscoito Doce > Bolinhos |
| 2026-04-03 | Categoria | `bananada` / `goiabada` / `doce de fruta` → Mercearia Doce > Sobremesas > Doces de Frutas |
| 2026-04-03 | Categoria | `suco pronto` / `nectar` → Bebidas > Sucos > Suco Pronto/Néctar |
| 2026-04-03 | Categoria | `petit suisse` → Laticínios > Iogurtes > Iogurtes Infantis |
| 2026-04-03 | Categoria | `sandalia havaiana` / `sandalia` / `chinelo` / `havaiana` → Têxtil > Calçados > Sandália e Chinelo |
| 2026-04-03 | Fabricante | SOVENA, VICTOR GUEDES, FLAMBOYANT, ARCOR, DOCILE, FINI, BARILLA, RICLAN, PERFETTI VAN MELLE, PIF PAF ALIMENTOS, TIAL |
| 2026-04-03 | Marca | ANDORINHA \| SOVENA; GALLO \| VICTOR GUEDES; FLAMBOYANT \| FLAMBOYANT; ARCOR \| ARCOR; DOCILE \| DOCILE; FINI \| FINI; FREEGELLS \| RICLAN; AZEDINHA \| RICLAN; MENTOS \| PERFETTI VAN MELLE; BARILLA \| BARILLA; SANTA AMALIA \| CAMIL; DEL VALLE \| COCA-COLA CO; TIAL \| TIAL; PIF PAF \| PIF PAF ALIMENTOS; AYMORE \| ARCOR |
| 2026-04-06 | Combinação | `COCO+RALADO` → Mercearia Doce > Culinária Doce > Coco Ralado |
| 2026-04-06 | Combinação | `BANANA+PASSA` → Mercearia Doce > Frutas Secas > Uva Passa |
| 2026-04-06 | Combinação | `ALHO+PO/GRANULADO/DESIDRATADO` → Mercearia Salgada > Temperos e Molhos > Caldo Tablete e Pó |
| 2026-04-06 | Combinação | `CEBOLA+FLOCOS/DESIDRATADA/PO` → Mercearia Salgada > Temperos e Molhos > Caldo Tablete e Pó |
| 2026-04-06 | Combinação | `TOMATE+SECO` → Mercearia Salgada > Conservas e Enlatados > Outras Conservas |
| 2026-04-06 | Combinação | `BATATA+CHIPS` → Mercearia Doce > Salgadinho > Batata Frita |
| 2026-04-06 | Combinação | `BATATA+SNACK` → Mercearia Doce > Salgadinho > Salgadinhos Sabores |
| 2026-04-06 | Combinação | `LEITE+COCO` → Mercearia Doce > Culinária Doce > Leite de Coco |
| 2026-04-06 | Combinação | `OLEO+COCO` → Mercearia Salgada > Óleo > Óleo de Coco |
| 2026-04-06 | Combinação | `FARINHA+MANDIOCA` → Commodities > Farináceos > Farinha de Mandioca |
| 2026-04-06 | Combinação | `FARINHA+TRIGO` → Commodities > Farinha de Trigo > - |
| 2026-04-06 | Combinação | `ACUCAR+MASCAVO/REFINADO/CRISTAL/DEMERARA` → Commodities > Açúcar > subtipo |
| 2026-04-06 | Abreviação | `whiskey`/`whisk` → whisky; `sard` → sardinha; `plast` → plastico; `beb` → bebida; `amant` → amanteigado; `bisc` → biscoito; `deseng` → desengordurante; `preserv` → preservativo; `empan` → empanado; `trat` → tratamento; `aero` → aerosol; `masc` → mascara; `pent` → pentear |
| 2026-04-06 | Categoria | `mingau` → Mercearia Doce > Matinais > Cereais; `bacia` → Bazar Geral > Utilidades da Cozinha; `club social` → Mercearia Doce > Biscoito Salgado > Água e Sal; `biscoito amanteigado` → Mercearia Doce > Biscoito Doce > Biscoito Amenteigado; `preservativo` → Perfumaria > Farmácia > Preservativos; `banha` → Perecíveis > Friambreria > Banhas e Gorduras; `salpet` → Mercearia Doce > Biscoito Salgado > Salpet; `cominho`/`canela`/`oregano`/`paprica`/`pimenta` → Mercearia Salgada > Temperos; `caneta`/`marcador` → Bazar Geral > Papelaria; `pacoca` → Mercearia Doce > Guloseimas > Doces de Amendoim; `peneira` → Bazar Geral > Utilidades da Cozinha; `luva` → Bazar Geral > Utensílios para Limpeza; `essencia`/`anilina`/`corante alimenticio` → Mercearia Doce > Culinária Doce > Complementos |
| 2026-04-06 | Combinação | `PESSEGO+CALDA`; `PO+DESCOLORANTE`; `AMEIXA+SECA`; `SEQUILHO+LEITE`; `BISCOITO+AGUA/MAIZENA/RECHEADO/CRACKER/AMANTEIGADO`; `BANANA+CHIPS`; `BARRA+CEREAL`; `BICARBONATO+SODIO`; `BANHA+SUINA`; `GORDURA+SUINA`; `SABAO+COCO`; `BALDE+PLASTICO`; `CREME+TRATAMENTO`; `DESODORANTE+AEROSOL/SPRAY`; `SEMENTE+GIRASSOL/CHIA/LINHACA/GERGELIM` |
| 2026-04-07 | Abreviação | `capil` → capilar |
| 2026-04-07 | Categoria | `vela`/`velas` → Bazar Geral > Utilidades Descartáveis > Velas; `copo` → Bazar Geral > Utilidades da Cozinha > Copo Individual; `tapete` → Têxtil > Cama, Mesa, Banho; `adocante` → Mercearia Doce Light > Adoçantes; `conhaque` → Bebidas > Destilados; `torrada` → Padaria Industrial; `cloro` → Limpeza para Roupas > Alvejantes; `acetona` → Perfumaria > Estética > Removedores; `soda caustica` → Limpeza de Banheiro > Limpeza Pesada; `bucha banho` → Perfumaria > Higiene Corporal > Esponja de Banho; `gel fixador`/`gel capilar` → Perfumaria > Produtos Capilares > Gel Fixador; `mamadeira` → Perfumaria > Seção Infantil; `gel` → Perfumaria > Produtos Capilares; `file de peito` → Perecíveis > Congelados; `caderno` → Bazar Geral > Papelaria; `agua oxigenada` → Perfumaria > Farmácia; `shoyu` → Mercearia Salgada > Temperos > Molho de Soja; `lamina` → Perfumaria > Barbearia > Lâminas; `mexerica`/`tangerina` → Hortifruti > Frutas; `cera` → Limpeza de Pisos; `bucha` → Perfumaria > Higiene Corporal; `escova` → Perfumaria > Higiene Corporal; `sacola`/`bobina`/`palito` → Bazar Geral > Utilidades Descartáveis; `drink` → Bebidas > Destilados; `filtro` → Mercearia Doce > Matinais; `torresmo` → Açougue > Suíno; `reparador` → Perfumaria > Produtos Capilares; `toalha` → Têxtil; `erva` → Bebidas > Matinais; `flanela`/`espuma` → Bazar Geral > Utensílios para Limpeza; `tesoura` → Bazar Geral > Papelaria; `colher` → Bazar Geral > Utilidades da Cozinha; `graxa`/`cadeado`/`extensao`/`mangueira` → Bazar Geral > Ferramentas; `saca rolha` → Bazar Geral > Utilidades da Cozinha; `bobina` → Uso e Consumo > Bobinas Térmicas; `benjamin` → Bazar Geral > Ferramentas > Material Elétrico; `sopao` → Mercearia Salgada > Massas e Sopas > Sopas |
| 2026-04-07 | Combinação | `PEIXE+POSTAS/FILE` → Congelados > Peixes; `PEIXE+INTEIRO` → Açougue > Peixes; `CACAU+PO` → Culinária Doce > Chocolates em Pó; `AZEITE+VIRGEM` → Azeites > Extra Virgem; `VINAGRE+MACA/ARROZ`; `CHOCOLATE+BARRA`; `NOZ+MOSCADA`; `CERVEJA+LATA/LATAO`; `CERVEJA+LONG/NECK`; `MACARRAO+SEMOLA/OVOS`; `MASSA+PASTEL`; `CREME+CEBOLA` → Sopas; `CALDO+KNORR/MAGGI`; `MOLHO+TOMATE/PIMENTA`; `CREME+LEITE`; `DOCE+LEITE`; `TEMPERO+SAZON`; `LEITE+PO`; `REPARADOR+PONTAS`; `FEIJAO+CARIOCA/PRETO/BRANCO/CORDA/JALO`; `ABRIDOR+LATA/VINHO`; `AFIADOR+FACA`; `ABSORVENTE+ABAS`; `ALICATE+CUTICULA`; `CORTADOR+UNHAS`; `AGUA+COCO`; `CAFE+SOLUVEL` |
| 2026-04-07 | Marca | BEATS \| Ambev |
| 2026-07-08 | Marca | Nome canônico de `COCA COLA` corrigido para `COCA-COLA` (com hífen) em `identificador.py` — bate com o cadastro em `marcas`; sem isso `marca_id` ficava `None` em todo produto Coca-Cola |
| 2026-07-08 | Categoria | `COCA COLA`, `PEPSI COLA` → Bebidas > Refrigerante > Refrigerante Cola (bigrama, evita colisão com o unigrama ambíguo "COLA") |
| 2026-07-08 | Categoria | `COLA MASSA` → Bazar Geral > Ferramentas e Acessórios > Colas e Adesivos (bigrama; removido o unigrama solto `COLA` que classificava Coca-Cola/Pepsi/Tropical Cola como cola de colar) |
| 2026-07-08 | Categoria | `AZEITE OLIVA`, `OLEO SOJA`, `OLEO CANOLA`, `OLEO GIRASSOL`, `OLEO COCO`, `LEITE COCO`, `CREME LEITE`, `LEITE CONDENSADO` → adicionados a `_TIPOS_PRODUTO` como compostos (`pipeline.py`), reconhecidos mesmo com "DE" no meio ("AZEITE DE OLIVA") |

---

## Como manter este arquivo

Após cada commit, responda:
```
1. Adicionei ou mudei um model?            → atualizar "Modelos e tabelas"
2. Concluí ou iniciei um passo do MVP?     → atualizar "🎯 Próximos passos"
3. Tomei uma decisão de arquitetura?       → atualizar docs/arquitetura-dados.md
```
