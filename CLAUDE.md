# SPED Manager

## Contexto
Sistema de gestão fiscal para supermercados baseado em arquivos EFD (SPED Fiscal).
MVP em Streamlit com Python, evoluindo para FastAPI + React no futuro.

## Stack
- Streamlit — interface
- SQLAlchemy + SQLite (dev) / PostgreSQL (prod)
- Python 3.11+

## Estrutura de pastas
- app/pages — telas Streamlit (01_dashboard, 02_upload_sped, etc.)
- app/services — lógica de negócio
- app/repositories — acesso ao banco (sempre filtram por tenant_id)
- app/models — SQLAlchemy ORM
- app/parser — bronze.py (efd_raw) e silver.py (c100, c170, 0200)
- app/components — sidebar.py, auth.py
- app/utils — db.py, formatters.py

## Models existentes
- GrupoEmpresarial — global (sem tenant_id); agrupa tenants de um mesmo dono (nome, ativo)
- Tenant — empresa/supermercado (CNPJ sem máscara, 14 dígitos); FK nullable → GrupoEmpresarial
- Produto — cadastro 0200 (chave única: tenant_id + cod_item)
- DocumentoFiscal — C100 (chave única: tenant_id + chv_nfe)
- ItemFiscal — C170 (chave única: tenant_id + chv_doc + num_item)
- EfdRaw — bronze linha a linha
- ArquivoImportado — histórico de importações
- Fabricante — global (sem tenant_id); grupo empresarial (Unilever, BRF, Ambev...)
- Marca — global (sem tenant_id); marca comercial (Dove, Sadia, Skol...), FK → Fabricante
- Departamento / Grupo / Categoria — hierarquia global de 3 níveis para classificação de produtos

## Regras importantes
- SEMPRE filtrar por tenant_id em todas as queries
- CNPJ salvo sem máscara, formatado só na exibição com formatar_cnpj()
- Encoding latin-1 nos arquivos EFD
- Arquivos renomeados: CNPJ_YYYYMMDD_YYYYMMDD.txt
- imports de models sempre via: import app.models
- session_state guarda: tenant_id, tenant_nome, tenant_cnpj
- Guard de autenticação no topo de cada página:
  if not st.session_state.get("tenant_id"):
      st.switch_page("main.py")

## Padrões de código
- Repositories herdam de BaseRepository (tem tenant_id)
- Services recebem session + tenant_id
- Upsert em todos os registros silver
- db.close() após cada query no Streamlit

## Status das páginas
| Página | Status | Observações |
|--------|--------|-------------|
| 00_inicio.py | ✅ concluído | resumo executivo: cards (faturamento, ICMS a pagar, ticket médio, PIS+COFINS), evolução últimos 6 meses, top 5 fornecedores, gráfico de composição por departamento (via C170 saída — aparece quando há itens de saída detalhados), filtro hierarquia Depto>Grupo>Cat na sidebar, rodapé com última data e arquivo importado |
| 01_gestao_vendas.py | ✅ concluído | gestão de vendas: visão geral com evolução mensal, ritmo de vendas (heatmap dia×mês, histograma de ticket), mix comercial (CFOP/CST via C190), clientes B2B e notas; 2 filtros (período, dia da semana) |
| 02_compras.py | ✅ concluído | gestão de compras: notas entrada, itens, por fornecedor, por produto; 4 filtros independentes (período, fornecedor, nº nota, produto) aplicados em todas as seções; CNPJ normalizado no filtro |
| 03_gestao_fiscal.py | ✅ concluído | gestão fiscal: visão geral tributos, ICMS débito/crédito, ST, PIS/COFINS, diagnóstico; 5 abas, 3 filtros (período, CST, CFOP); PIS/COFINS via DocumentoFiscal |
| 04_inventario.py | ✅ concluído | 3 abas: Estoque Virtual (movimentação calculada via C170 com fallback K200/H010/zero), Inventário H005/H010, Saldo K200 |
| 05_produtos.py | ✅ concluído | 3 abas: Cadastro EFD (campos 0200 + filtros), Padronização & Categorias (descrição padronizada, marca, embalagem, scores, situação), Inteligência de Produtos (preço médio, concentração de fornecedor, carga tributária) |
| 08_admin_revisao.py | ✅ concluído | painel interno (sem sidebar); auth por senha; 5 abas: Revisão Individual, Revisão em Lote, Marcas & Fabricantes, Tokens Desconhecidos, Clientes & Upload (lista clientes com grupo, cadastro com grupo opcional, upload admin com filtro por grupo, gestão de grupos empresariais) |
| 06_dados.py | ✅ concluído | 2 abas: Upload (bronze+silver, múltiplos arquivos) e Histórico (5 métricas + tabela de arquivos importados com exclusão) |
| 07_configuracoes.py | ⏳ pendente | |

## Status dos models
| Model | Status | Observações |
|-------|--------|-------------|
| GrupoEmpresarial | ✅ | global (sem tenant_id); nome, ativo; FK ← Tenant.grupo_id |
| Tenant | ✅ | grupo_id (FK nullable → GrupoEmpresarial) |
| Produto | ✅ | campos 0200 + padronização (descricao_padrao, tipo_embalagem, peso_volume, scores) + FK para Marca, Categoria, Grupo, Departamento |
| Fabricante | ✅ | global; nome, cnpj, aliases (JSON), ativo |
| Marca | ✅ | global; nome, fabricante_id, categoria, aliases (JSON), ativo |
| Departamento | ✅ | global; 18 departamentos carregados do categorias.db |
| Grupo | ✅ | global; 118 grupos, FK → Departamento |
| Categoria | ✅ | global; 720 categorias, FK → Grupo |
| DocumentoFiscal | ✅ | campos C100 completos |
| ItemFiscal | ✅ | campos C170 completos |
| EfdRaw | ✅ | |
| ArquivoImportado | ✅ | |
| IcmsC190 | ✅ | constraint única (tenant_id, chv_doc, cst_icms, cfop, aliq_icms); aliq_icms como String |
| InventarioH005 | ✅ | cabeçalho H005; constraint (tenant_id, dt_inv, mot_inv) |
| InventarioH010 | ✅ | itens H010; dt_inv desnormalizado; constraint (tenant_id, dt_inv, cod_item, ind_prop) |
| EstoqueK200 | ✅ | saldo K200; constraint (tenant_id, dt_est, cod_item, ind_est) |
| Participante | ✅ | registro 0150; constraint (tenant_id, cod_part); nome, cnpj, endereço |
| TokenDesconhecido | ✅ | global; token único + contagem + primeiro/último visto + exemplo de descrição |

## Status do parser
| Etapa | Status | Observações |
|-------|--------|-------------|
| Renomeação | ✅ | CNPJ_YYYYMMDD_YYYYMMDD.txt |
| Bronze | ✅ | efd_raw linha a linha |
| Silver C100 | ✅ | todos os campos |
| Silver C170 | ✅ | todos os campos |
| Silver 0200 | ✅ | todos os campos |
| Silver C190 | ✅ | campos completos, upsert por CST/CFOP/aliq |
| Silver H005 | ✅ | cabeçalho inventário, upsert por dt_inv+mot_inv |
| Silver H010 | ✅ | itens inventário, propaga dt_inv do H005 pai |
| Silver K200 | ✅ | saldo de estoque, upsert por dt_est+cod_item+ind_est |
| Silver 0150 | ✅ | participantes, upsert por cod_part |

## Decisões de arquitetura
- SQLite no dev, PostgreSQL na produção — troca só o .env
- Multi-tenant via tenant_id em todos os models
- Bronze/Silver seguindo padrão do Databricks original
- Storage local em storage/arquivos/ — vira S3 na produção
- Autenticação temporária só por CNPJ — senha ainda não implementada
- Pipeline de padronização de produtos (app/services/produto_padronizacao/):
  1. limpeza.py — uppercase, remove acentos, caracteres especiais e stopwords promocionais (PROMO, OFERTA, NOVO…)
  2. dicionarios.py — expansão de abreviações (~120 termos) + abreviações contextuais (DES→desnatado/desodorante/desinfetante conforme vizinhança; TP→tetra pak só com leite/suco/chá)
  3. unidades.py — extração de peso/volume via regex
  4. identificador.py — detecção de marca/fabricante: match exato por token/bigrama (banco > dicionário fixo) + fuzzy matching RapidFuzz (threshold=90, blacklist de tokens genéricos)
  5. pipeline.py — extração de atributos (ZERO, LIGHT, INTEGRAL, EXTRA VIRGEM, SEM GLUTEN…) separados da descrição; montagem final em ordem canônica: base + atributos + embalagem + volume
  6. categorizador.py — _VOCAB_CATEGORIA (~195 entradas, score 0.98) → _VOCAB_TIPO_PRODUTO (score 0.95) → _VOCAB_HORTIFRUTI (score 0.90) → Jaccard fallback
  - Cobertura automática atual: ~70.6% dos produtos com categoria/grupo
  - Protegido: produtos com origem_padronizacao='manual'/'manual_sem_cat' nunca são sobrescritos pelo backfill
- Marcas e fabricantes globais: 45 fabricantes + 225 marcas seedadas; banco tem prioridade sobre dicionário fixo; PRESTOBARBA é alias de GILLETTE (P&G)
- Tokens desconhecidos: pipeline salva no banco (tabela `tokens_desconhecidos`) tokens ≥4 chars não reconhecidos por nenhum dicionário; acessíveis na aba "Tokens Desconhecidos" do admin, ordenados por frequência; uso esperado: alimentar novas entradas na fila do CLAUDE.md
- scripts/backfill_padronizacao.py: flags --todos (reprocessa tudo exceto manuais) e --force (sobrescreve inclusive manuais); scripts/seed_fabricantes_marcas.py: popula fabricantes/marcas

## Diagnóstico de Arquitetura (2026-05-12)

### Pontos fortes
- Padrão repository correto e consistente — `tenant_id` filtrado em toda query de leitura
- bcrypt para senhas — escolha correta
- Parser bronze/silver bem desenhado — upserts, separação de responsabilidades, tratamento de encoding
- Isolamento multi-tenant arquiteturalmente sólido
- Catálogo EAN global — herança de classificação entre tenants entrega valor real
- O pipeline de padronização é investimento justificado: habilita navegação hierárquica no produto E é a base técnica para o modelo de dados anônimos para indústrias (IRI/Nielsen)

### Problemas identificados

#### Críticos (bloqueiam produção)
1. **Migrações via try/except** — `run_migrations()` engole silenciosamente qualquer erro. No SQLite funciona porque o único erro esperado é "coluna já existe". No PostgreSQL, erros reais (permissão, tipo incompatível, lock de tabela) também seriam ignorados. Substituir por **Alembic**.
2. **Gerenciamento de sessões inconsistente** — páginas usam `next(get_session())` + `db.close()` manual em try/finally espalhados. Se uma exceção ocorrer antes do `close()`, a sessão vaza. Trocar por context manager (`with get_db() as db:`).
3. **Segurança mínima ausente** — `ADMIN_PASSWORD` tem fallback hardcoded `"admin123"`, URL do admin é adivinhável, sem rate limiting. Baixo risco enquanto local; crítico antes do deploy.

#### Qualidade e manutenibilidade
4. **Regras do categorizador em código** — cada nova entrada (abreviação, categoria, combinação) exige edição de arquivo Python + deploy. Com ~200 regras acumuladas, o custo cresce indefinidamente. Solução: mover para tabelas editáveis no banco, gerenciáveis pelo painel admin.
5. **`08_admin_revisao.py` tem 1.392 linhas** — uma página fazendo revisão individual, lote, marcas, tokens, clientes, upload e grupos. Ponto crítico de manutenção.
6. **Sem testes** — 9.000 linhas, zero testes. Qualquer refatoração do pipeline ou do parser é uma aposta cega.

#### Limitação de produto
7. **Gestão de vendas incompleta sem XML** — EFD de supermercado tem C170 (itens) apenas para entradas. Saídas (varejo) viram C190: resumo fiscal sem produto ou quantidade. A página `01_gestao_vendas.py` mostra faturamento e impostos, não vendas de produto. **NFC-e XML é pré-requisito para o módulo funcionar**.

---

## Stack futura

O Streamlit foi a escolha certa para validar. O teto é baixo para produção: sem controle de estado real, sem componentes customizáveis, dificuldade com multi-usuário e performance limitada em queries pesadas.

**Destino:**
- **Backend:** FastAPI — preserva todo o código Python existente; só adiciona camada de rotas em cima dos services e repositories atuais
- **Frontend:** React + [Tremor](https://tremor.so) — biblioteca de componentes feita para dashboards analíticos (charts, KPI cards, tabelas, filtros prontos)
- **Auth:** JWT com FastAPI — substitui `session_state` por tokens Bearer padrão de mercado

**O que migra sem tocar:** `app/models/`, `app/repositories/`, `app/services/`, `app/parser/`, `app/utils/`
**O que é reescrito:** `app/pages/` (só a camada UI — o menor custo de reescrita possível)

---

## Pendente

### 🔴 Fase 1 — Deploy com produto funcional (prioridade máxima)

Objetivo: ter usuários reais. Produto imperfeito com usuários reais > produto perfeito sem usuários.

- [x] **Import XML NFC-e/NF-e** — `app/parser/xml_parser.py` implementado; suporta NFC-e (mod 65, saída) e NF-e (mod 55, entrada/saída); valida CNPJ, deduplica por chv_nfe, upsert Produto/Participante/ItemFiscal/IcmsC190; suporta ZIP com múltiplos XMLs; `06_dados.py` com aba "Upload XML"
- [ ] **Alembic** — substituir `run_migrations()` pelo padrão correto de versionamento de schema; necessário antes de qualquer uso sério do PostgreSQL
- [ ] **Context manager de sessão** — trocar `next(get_session())` + `db.close()` manual por `with get_db() as db:` em todas as páginas e services
- [ ] **Segurança mínima** — remover fallback `"admin123"`, obrigar `ADMIN_PASSWORD` no `.env`, obscurecer ou proteger URL do admin
- [ ] **Deploy** — Streamlit Cloud + Supabase (PostgreSQL); configurar secrets, remover PRAGMAs SQLite do caminho de migração, testar com dados reais
- [ ] **Definir tipo de cliente foco** — fiscal (contador/escritório contábil) ou gestão (dono de loja); escopo das primeiras demos

### 🟠 Fase 2 — Qualidade interna (com usuários iniciais)

- [ ] **Regras do categorizador no banco** — tabelas `regras_abreviacao` e `regras_categorizacao` editáveis pelo painel admin; elimina o ciclo "escreve no CLAUDE.md → aplica fila → deploy"; regras viram dados, não código
- [ ] **Dividir `08_admin_revisao.py`** — 1.392 linhas fazendo coisas demais; extrair lógica para services; separar UI em módulos por domínio (produtos, marcas, clientes, tokens)
- [ ] **Testes de unidade** — parser silver (arquivo EFD de amostra fixo como fixture) + `processar_descricao` com casos de entrada conhecidos; 20–30 testes já dão segurança para refatorar o pipeline
- [ ] **Padrão de cores global** — paleta de 5–6 cores em `utils/theme.py` aplicada em todas as páginas (já existe o arquivo, falta consistência)
- [ ] **Multi-loja (Etapa 2)** — ver especificação técnica detalhada abaixo; só faz sentido após ter clientes de grupo empresarial reais

### 🟠 Fase 3 — Migração FastAPI + React

O Streamlit foi a escolha certa para validar. O teto é baixo para produção: sem controle de estado real, sem componentes customizáveis, dificuldade com multi-usuário e performance limitada.

Stack destino definida: FastAPI (backend) + React + Tremor (frontend) + JWT (auth). Ver seção "Stack futura" acima.

Ordem dentro da fase:
1. FastAPI com rotas principais (compras, fiscal, produtos, vendas)
2. Auth JWT substituindo `session_state` do Streamlit
3. Frontend React + Tremor replicando páginas uma a uma
4. Desligar Streamlit quando paridade funcional estiver completa

O que migra sem tocar: `app/models/`, `app/repositories/`, `app/services/`, `app/parser/`, `app/utils/`
O que é reescrito: `app/pages/` (só a camada UI — menor custo possível de reescrita)

### 🟡 Fase 4 — Features que só fazem sentido com escala

- [ ] **Dados anônimos para indústrias** — modelo IRI/Nielsen; requer ~50–100 lojas para anonimização estatística válida + contrato explícito com cada cliente autorizando uso secundário dos dados; a pipeline atual já é o investimento certo para isso
- [ ] **Modelo supervisionado de categorização** — TF-IDF + classificador simples (Naive Bayes ou Regressão Logística via scikit-learn) após ~500 revisões manuais acumuladas (`origem_padronizacao = 'manual'`); plugar em `categorizador.py` antes do Jaccard fallback; aumenta cobertura de ~70% para ~90%+
- [ ] **Embeddings para produtos similares** — detectar duplicatas entre tenants, sugerir classificação por similaridade; custo alto de infraestrutura (~400MB de modelo), só justifica com volume alto; pós-MVP
- [ ] **Importação NF-e XML** (B2B, notas de saída entre empresas) — complementa NFC-e; mesma arquitetura do parser XML

### 🟢 Qualidade / backlog

- [ ] **Testar inventário** com arquivo EFD real contendo Bloco H e K200
- [ ] **README prático** — como rodar localmente, configurar `.env`, rodar `init_db` e `backfill`, importar EFD, usar painel admin
- [ ] **Documentação técnica completa** — após autenticação + deploy prontos; diagramas de arquitetura, fluxos, especificação dos models e pipeline
- [ ] **Gestão Macro→Micro nas demais páginas** — infraestrutura criada (2026-04-06) e integrada no Início; pendente: Compras (Fase 2), Fiscal (Fase 3), Vendas (depende XML), Inventário (Fase 5), Produtos (Fase 6)

### ✅ Concluído (histórico)

- [x] Página de cadastro de produto — 3 abas: Cadastro EFD, Padronização & Categorias, Inteligência de Produtos
- [x] Página de gestão de compras — 4 filtros independentes (período, fornecedor, nº nota, produto)
- [x] Página de gestão de vendas (saídas)
- [x] Relatórios fiscais → Gestão Fiscal com 5 abas (ICMS, ST, PIS/COFINS, diagnóstico)
- [x] Dashboard → resumo executivo real (faturamento, ICMS a pagar, crescimento, top fornecedor)
- [x] Página de Dados — upload + histórico de importações unificados
- [x] Estoque virtual com fallback K200/H010/zero
- [x] Silver C190 com constraint correta
- [x] Compras: CNPJ → razão social nos gráficos; gráfico CFOP revisado
- [x] Filtros de período com seleção múltipla de meses/anos
- [x] Renomear e reordenar páginas na sidebar
- [x] Legendas dos gráficos movidas para cima
- [x] Última data contemplada exibida no dashboard
- [x] Revisão em Lote com checkbox por linha no data_editor
- [x] Pipeline de padronização: stopwords, abreviações contextuais, extração de atributos, ordem canônica
- [x] Fuzzy matching de marcas (RapidFuzz threshold=90)
- [x] Tokens desconhecidos salvos no banco para revisão futura
- [x] Catálogo global de EAN (`catalogo_produtos`) — herança de classificação entre tenants; backfill rodado com 2.657 entradas
- [x] GrupoEmpresarial — model + FK em Tenant + TenantService com 5 métodos; aba Clientes & Upload no admin com gestão de grupos
- [x] Infraestrutura macro→micro: `filtro_hierarquia.py` (componente sidebar cascateado), helpers `_filtro_hierarquia_via_doc/item/por_produto` no `base_repo.py`; página Início integrada com filtro e gráfico de composição por departamento; repos `vendas`, `compras`, `fiscal` com params de hierarquia

## Checklist de testes — funcionalidades recentes (2026-04-06)

### 1. Banco de dados (verificação inicial)
- [x] `grupos_empresariais` existe no SQLite ✅
- [x] `tenants.grupo_id` existe ✅
- [x] `catalogo_produtos` tem 2.657 entradas ✅

### 2. Admin — Grupos Empresariais (Seção D da aba Clientes & Upload)
- [x] Abrir `localhost:8501/08_admin_revisao`, logar com a senha admin
- [x] Ir para aba **Clientes & Upload** → rolar até **Grupos Empresariais**
- [x] Criar grupo: ex. "Rede GS"
- [x] Verificar que o grupo aparece na tabela com coluna "Lojas" vazia

### 3. Admin — Cadastrar GS Mercearia
- [x] Seção **Cadastrar novo cliente**: preencher nome "GS Mercearia", CNPJ correto
- [ ] Selecionar grupo "Rede GS" no dropdown opcional
- [ ] Clicar Cadastrar → verificar mensagem de sucesso
- [ ] Verificar na tabela da Seção A que a GS aparece com coluna "Grupo: Rede GS"
- [ ] Verificar na Seção D que o grupo "Rede GS" agora lista "GS Mercearia" em "Lojas"

### 4. Admin — Associar loja existente a grupo (se houver outra loja no banco)
- [ ] Expandir **Associar loja a grupo**, selecionar a loja e o grupo, clicar Associar
- [ ] Verificar que a coluna "Grupo" da loja foi atualizada na tabela

### 5. Admin — Filtro por grupo no upload
- [ ] Na Seção C, selecionar "Rede GS" no dropdown "Filtrar por grupo"
- [ ] Verificar que o selectbox "Tenant de destino" mostra apenas lojas do grupo GS

### 6. Admin — Upload dos arquivos da GS Mercearia
- [ ] Selecionar "GS Mercearia" no selectbox de destino
- [ ] Subir 1 arquivo EFD como teste
- [ ] **Teste de validação de CNPJ**: tentar subir um arquivo de outro supermercado → deve aparecer erro em vermelho e arquivo ser ignorado
- [ ] Subir o arquivo correto da GS → deve processar sem erro
- [ ] Verificar resultado: documentos, itens, produtos criados/atualizados
- [ ] Verificar que o `ArquivoImportado` foi criado com o `tenant_id` correto (não o tenant logado)

### 7. Herança de classificação via EAN
- [ ] Após o upload, consultar no SQLite:
  ```sql
  SELECT origem_padronizacao, COUNT(*) FROM produtos
  WHERE tenant_id = <id_gs> GROUP BY origem_padronizacao;
  ```
- [ ] Verificar que há registros com `origem_padronizacao = 'catalogo'` — indica que produtos já classificados no primeiro tenant foram herdados
- [ ] Produtos com EAN inválido ou novo devem ter `origem_padronizacao = 'regra'`

### 8. Upload dos 5 arquivos restantes
- [ ] Subir os demais arquivos da GS um a um (ou todos de uma vez) pelo admin
- [ ] Verificar que nenhum tem erro de CNPJ divergente
- [ ] Verificar resumo final de cada arquivo

### 9. Login como GS Mercearia
- [ ] Logar na tela principal com o CNPJ da GS
- [ ] Verificar que as páginas de gestão carregam os dados corretos

### Queries úteis para verificar no SQLite
```sql
-- Tenants e grupos
SELECT t.nome, t.cnpj, g.nome as grupo
FROM tenants t LEFT JOIN grupos_empresariais g ON t.grupo_id = g.id;

-- Arquivos importados por tenant
SELECT t.nome, a.nome_padronizado, a.status, a.processado_em
FROM arquivos_importados a JOIN tenants t ON a.tenant_id = t.id
ORDER BY a.processado_em DESC;

-- Origem da classificação após upload
SELECT origem_padronizacao, COUNT(*) as qtd
FROM produtos WHERE tenant_id = <id>
GROUP BY origem_padronizacao ORDER BY qtd DESC;

-- Catálogo EAN
SELECT COUNT(*) FROM catalogo_produtos;
SELECT COUNT(*) FROM catalogo_produtos WHERE categoria_id IS NOT NULL;
```

---

## Decisões mapeadas: Importação NF-e XML

### Contexto
Clientes que não têm o EFD fechado (mês em andamento) ou recebem XMLs diretamente de fornecedores precisam importar dados de compras sem depender do SPED.

### Abordagem decidida
- **Fonte independente**: XML e EFD coexistem no banco; deduplicação pela chave NF-e de 44 dígitos (`chv_nfe`)
- **Escopo**: alimenta Compras + Fiscal (C190 derivado dos itens por agregação CST/CFOP/alíquota)
- **Bronze ignorado**: XML não se encaixa no modelo linha a linha do EfdRaw — ir direto para silver
- **`cod_part` = CNPJ do emitente**: evita conflito com cod_part do EFD (que são códigos internos)
- **Sem nova dependência**: usar `xml.etree.ElementTree` da stdlib
- **Sem mudança de schema**: todos os models já existem com os campos necessários

### Arquivos a criar/editar
- `app/parser/xml_parser.py` — novo: `XmlParser(session, tenant_id).processar(xml, nome)`
- `app/pages/06_dados.py` — nova aba "Upload XML" com suporte a múltiplos arquivos

### Mapeamento XML → banco
| XML | Destino |
|---|---|
| `<infNFe Id>` / `<chNFe>` | `DocumentoFiscal.chv_nfe` |
| `<emit>` CNPJ + xNome | `Participante` (cod_part = CNPJ) |
| `<ide>` nNF, serie, dhEmi | `DocumentoFiscal` (ind_oper="0" fixo) |
| `<ICMSTot>` vNF, vICMS, vPIS, vCOFINS | `DocumentoFiscal` totais |
| `<det>` cProd, xProd, qCom, vProd, CFOP, CST, pICMS | `ItemFiscal` + `Produto` |
| Agrupamento de itens por CST/CFOP/alíq | `IcmsC190` (derivado) |

---

## Fila de adições ao pipeline de padronização

Use esta seção para acumular novas entradas antes de pedir ao Claude para aplicá-las.
Quando quiser aplicar, diga: **"aplica a fila de padronização"**.
Após aplicado, o Claude limpa as entradas e move para o histórico.

### Como preencher

**Abreviações** — `abrev` → `expansão` (vai para `dicionarios.py`)
- Se for bigrama (duas palavras), colocar entre aspas: `"ap glic"` → `glicerinado`
- Expansão sempre em português sem abreviação

**Categorias** — `keyword` → `Departamento > Grupo > Categoria` (vai para `categorizador.py`)
- Keyword pode ser unigrama ou bigrama
- Se a categoria for ambígua em grupos diferentes, indicar o grupo entre parênteses
- Consultar nomes exatos na seção "Hierarquia de categorias" abaixo se necessário

**Marcas** — `Nome da marca | Fabricante | aliases separados por vírgula` (vai para `identificador.py`)
- Aliases: variações de grafia que aparecem nas descrições EFD
- Fabricante deve bater com um fabricante já cadastrado, ou será criado novo

**Fabricantes** — `Nome | aliases separados por vírgula` (vai para `identificador.py`)

**Combinações não adjacentes** — `{TOKEN_A, TOKEN_B}` → `Departamento > Grupo > Categoria` (vai para `categorizador.py` → `_VOCAB_COMBINACAO`)
- Use quando dois tokens **juntos** definem uma categoria, mas podem aparecer separados por marca ou outros termos
- Ex: "COCO ANCHIETA RALADO" — COCO e RALADO não são adjacentes, mas juntos indicam MERCEARIA DOCE > CULINARIA DOCE > COCO RALADO
- Ex: "FARINHA DONA BENTA TRIGO 1KG" — FARINHA e TRIGO separados pela marca
- Escreva os tokens em maiúsculo, separados por vírgula dentro de chaves
- **Quando usar `> -` (sem categoria)**: se o match for apenas até o grupo (ex: FARINHA DE TRIGO é grupo, não categoria), coloque `-` no nível de categoria; o Claude usará `_match_por_grupo_nome` automaticamente
- Prioridade: combinações são checadas APÓS bigramas adjacentes do `_VOCAB_CATEGORIA`, mas ANTES do `_VOCAB_TIPO_PRODUTO`; logo, só precisam cobrir casos que bigramas adjacentes não conseguem

---

### ✏️ Fila — preencha abaixo, peça "aplica a fila" quando quiser aplicar

#### Abreviações
<!-- formato: abrev → expansão -->

#### Categorias
<!-- formato: keyword → Departamento > Grupo > Categoria -->

#### Combinações não adjacentes
<!-- formato: {TOKEN_A, TOKEN_B} → Departamento > Grupo > Categoria (ou > - se só até o grupo) -->

#### Marcas
<!-- formato: Nome | Fabricante | alias1, alias2, ... -->

#### Fabricantes
<!-- formato: Nome | alias1, alias2, ... -->

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
| 2026-04-09 | Marca | FINI \| FINI (aliases já no identificador.py) |
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
| 2026-04-03 | Fabricante | SOVENA |
| 2026-04-03 | Fabricante | VICTOR GUEDES |
| 2026-04-03 | Fabricante | FLAMBOYANT |
| 2026-04-03 | Fabricante | ARCOR |
| 2026-04-03 | Fabricante | DOCILE |
| 2026-04-03 | Fabricante | FINI |
| 2026-04-03 | Fabricante | BARILLA |
| 2026-04-03 | Fabricante | RICLAN |
| 2026-04-03 | Fabricante | PERFETTI VAN MELLE |
| 2026-04-03 | Fabricante | PIF PAF ALIMENTOS |
| 2026-04-03 | Fabricante | TIAL |
| 2026-04-03 | Marca | ANDORINHA \| SOVENA |
| 2026-04-03 | Marca | GALLO \| VICTOR GUEDES |
| 2026-04-03 | Marca | FLAMBOYANT \| FLAMBOYANT |
| 2026-04-03 | Marca | ARCOR \| ARCOR \| alias: BUTTER TOFFEES |
| 2026-04-03 | Marca | DOCILE \| DOCILE |
| 2026-04-03 | Marca | FINI \| FINI \| aliases: DENTADURAS FINI, MINHOCAS FINI, TUBES FINI |
| 2026-04-03 | Marca | FREEGELLS \| RICLAN |
| 2026-04-03 | Marca | AZEDINHA \| RICLAN |
| 2026-04-03 | Marca | MENTOS \| PERFETTI VAN MELLE |
| 2026-04-03 | Marca | BARILLA \| BARILLA |
| 2026-04-03 | Marca | SANTA AMALIA \| CAMIL |
| 2026-04-03 | Marca | DEL VALLE \| THE COCA-COLA CO |
| 2026-04-03 | Marca | TIAL \| TIAL |
| 2026-04-03 | Marca | PIF PAF \| PIF PAF ALIMENTOS \| alias: PIFPAF |
| 2026-04-03 | Marca | AYMORE \| ARCOR \| alias: AYMORÉ |
| 2026-04-06 | Combinação não adjacente | `COCO` + `RALADO` → Mercearia Doce > Culinária Doce > Coco Ralado |
| 2026-04-06 | Combinação não adjacente | `BANANA` + `PASSA` → Mercearia Doce > Frutas Secas > Uva Passa |
| 2026-04-06 | Combinação não adjacente | `ALHO` + `PO/GRANULADO/DESIDRATADO` → Mercearia Salgada > Temperos e Molhos > Caldo Tablete e Pó |
| 2026-04-06 | Combinação não adjacente | `CEBOLA` + `FLOCOS/DESIDRATADA/PO` → Mercearia Salgada > Temperos e Molhos > Caldo Tablete e Pó |
| 2026-04-06 | Combinação não adjacente | `TOMATE` + `SECO` → Mercearia Salgada > Conservas e Enlatados > Outras Conservas |
| 2026-04-06 | Combinação não adjacente | `BATATA` + `CHIPS` → Mercearia Doce > Salgadinho > Batata Frita |
| 2026-04-06 | Combinação não adjacente | `BATATA` + `SNACK` → Mercearia Doce > Salgadinho > Salgadinhos Sabores |
| 2026-04-06 | Combinação não adjacente | `LEITE` + `COCO` → Mercearia Doce > Culinária Doce > Leite de Coco |
| 2026-04-06 | Combinação não adjacente | `OLEO` + `COCO` → Mercearia Salgada > Óleo > Óleo de Coco |
| 2026-04-06 | Combinação não adjacente | `FARINHA` + `MANDIOCA` → Commodities > Farináceos > Farinha de Mandioca |
| 2026-04-06 | Combinação não adjacente | `FARINHA` + `TRIGO` → Commodities > Farinha de Trigo > - (nível grupo) |
| 2026-04-06 | Combinação não adjacente | `ACUCAR` + `MASCAVO/REFINADO/CRISTAL/DEMERARA` → Commodities > Açúcar > subtipo |
| 2026-04-06 | Abreviação | `whiskey` → whisky |
| 2026-04-06 | Abreviação | `whisk` → whisky |
| 2026-04-06 | Abreviação | `sard` → sardinha |
| 2026-04-06 | Categoria | `mingau` → Mercearia Doce > Matinais > Cereais |
| 2026-04-06 | Combinação não adjacente | `PESSEGO` + `CALDA` → Mercearia Doce > Sobremesas e Outros Doces > Compotas de Frutas |
| 2026-04-06 | Combinação não adjacente | `PO` + `DESCOLORANTE` → Perfumaria > Produtos Capilares > Tintura / Descolorantes para Cabelo |
| 2026-04-06 | Abreviação | `plast` → plastico |
| 2026-04-06 | Abreviação | `beb` → bebida |
| 2026-04-06 | Abreviação | `amant` → amanteigado |
| 2026-04-06 | Abreviação | `bisc` → biscoito |
| 2026-04-06 | Categoria | `bacia` → Bazar Geral > Utilidades da Cozinha (nível grupo) |
| 2026-04-06 | Categoria | `club social` → Mercearia Doce > Biscoito Salgado > Água e Sal |
| 2026-04-06 | Categoria | `biscoito amanteigado` → Mercearia Doce > Biscoito Doce > Biscoito Amenteigado (bridge grafia popular) |
| 2026-04-06 | Combinação não adjacente | `AMEIXA` + `SECA` → Hortifruti > Frutas Secas > Frutas Secas / Cristalizadas |
| 2026-04-06 | Combinação não adjacente | `SEQUILHO` + `LEITE` → Mercearia Doce > Biscoito Doce > Rosquinhas e Sequilhos |
| 2026-04-06 | Combinação não adjacente | `BISCOITO` + `AGUA` → Mercearia Doce > Biscoito Salgado > Água e Sal |
| 2026-04-06 | Combinação não adjacente | `BISCOITO` + `MAIZENA` → Mercearia Doce > Biscoito Doce > Biscoito Maizena |
| 2026-04-06 | Combinação não adjacente | `BISCOITO` + `RECHEADO` → Mercearia Doce > Biscoito Doce > Biscoito Recheado |
| 2026-04-06 | Combinação não adjacente | `BISCOITO` + `CRACKER` → Mercearia Doce > Biscoito Salgado > Cream Cracker |
| 2026-04-06 | Combinação não adjacente | `BISCOITO` + `AMANTEIGADO` → Mercearia Doce > Biscoito Doce > Biscoito Amenteigado |
| 2026-04-06 | Combinação não adjacente | `BANANA` + `CHIPS` → Mercearia Doce > Salgadinho > Snacks |
| 2026-04-06 | Combinação não adjacente | `BARRA` + `CEREAL` → Mercearia Doce > Mercearia Doce Light e Diet > Cereais em Barra |
| 2026-04-06 | Combinação não adjacente | `BICARBONATO` + `SODIO` → Mercearia Salgada > Temperos e Molhos > Temperos Pronto em Pó/Sachê |
| 2026-04-06 | Abreviação | `deseng` → desengordurante |
| 2026-04-06 | Abreviação | `preserv` → preservativo |
| 2026-04-06 | Categoria | `preservativo` → Perfumaria > Farmácia > Preservativos |
| 2026-04-06 | Categoria | `banha` → Perecíveis do Autoserviço > Friambreria > Banhas e Gorduras Vegetais |
| 2026-04-06 | Combinação não adjacente | `BANHA` + `SUINA` → Perecíveis do Autoserviço > Friambreria > Banhas e Gorduras Vegetais |
| 2026-04-06 | Combinação não adjacente | `GORDURA` + `SUINA` → Perecíveis do Autoserviço > Friambreria > Banhas e Gorduras Vegetais |
| 2026-04-06 | Combinação não adjacente | `SABAO` + `COCO` → Limpeza > Limpeza para Roupas > Sabão em Barra e Pasta |
| 2026-04-06 | Combinação não adjacente | `BALDE` + `PLASTICO` → Bazar Geral > Utilidades da Cozinha > Baldes de Plástico |
| 2026-04-06 | Categoria | `corante alimenticio` / `corante alimentar` → Mercearia Doce > Culinária Doce > Complementos (bigrama — evita conflito com corante de roupa) |
| 2026-04-06 | Categoria | `anilina` → Mercearia Doce > Culinária Doce > Complementos |
| 2026-04-06 | Categoria | `essencia` → Mercearia Doce > Culinária Doce > Complementos |
| 2026-04-06 | Abreviação | `empan` → empanado |
| 2026-04-06 | Abreviação | `trat` → tratamento |
| 2026-04-06 | Abreviação | `aero` → aerosol |
| 2026-04-06 | Abreviação | `masc` → mascara |
| 2026-04-06 | Abreviação | `pent` → pentear |
| 2026-04-06 | Categoria | `salpet` → Mercearia Doce > Biscoito Salgado > Salpet |
| 2026-04-06 | Categoria | `cominho` → Mercearia Salgada > Temperos e Molhos > Temperos Pronto em Pó/Sachê |
| 2026-04-06 | Categoria | `caneta` → Bazar Geral > Artigos para Papelaria e Armarinho > Canetas em Geral |
| 2026-04-06 | Categoria | `marcador` → Bazar Geral > Artigos para Papelaria e Armarinho > Canetas em Geral |
| 2026-04-06 | Categoria | `pacoca` / `pacoquinha` / `pacoquita` → Mercearia Doce > Guloseimas > Doces de Amendoim |
| 2026-04-06 | Categoria | `peneira` → Bazar Geral > Utilidades da Cozinha > Escorredores e Peneiras |
| 2026-04-06 | Categoria | `luva` → Bazar Geral > Utensílios para Limpeza (nível grupo) |
| 2026-04-06 | Categoria | `haste flexivel` / `hastes flexiveis` → Perfumaria > Higiene Corporal (nível grupo; HASTE FLEXÍVEL tem acento no banco) |
| 2026-04-06 | Combinação não adjacente | `CREME` + `TRATAMENTO` → Perfumaria > Produtos Capilares > Cremes p/ Hidratação |
| 2026-04-06 | Combinação não adjacente | `DESODORANTE` + `AEROSOL` → Perfumaria > Desodorantes e Colônias > Desodorante Aerosol |
| 2026-04-06 | Combinação não adjacente | `DESODORANTE` + `SPRAY` → Perfumaria > Desodorantes e Colônias > Desodorante Aerosol |
| 2026-04-06 | Combinação não adjacente | `SEMENTE` + `GIRASSOL/CHIA/LINHACA/GERGELIM` → Mercearia Salgada > Farináceos > Sementes (Chia, Linhaça, Girassol, etc.) |
| 2026-04-07 | Categoria | `vela` / `velas` → Bazar Geral > Utilidades Descartáveis > Velas Comum / Citronela / Aromáticas |
| 2026-04-07 | Categoria | `copo` → Bazar Geral > Utilidades da Cozinha > Copo Individual |
| 2026-04-07 | Categoria | `tapete` → Têxtil > Cama, Mesa, Banho > Tapetes em Geral |
| 2026-04-07 | Categoria | `adocante` → Mercearia Doce Light e Diet > Mercearia Doce Light e Diet > Adoçantes |
| 2026-04-07 | Categoria | `conhaque` → Bebidas > Destilados > Conhaque/Brandy |
| 2026-04-07 | Categoria | `torrada` / `torradas` → Padaria Industrial > Padaria Industrial > Torradas |
| 2026-04-07 | Categoria | `cloro` → Limpeza > Limpeza para Roupas > Alvejantes e Cloro |
| 2026-04-07 | Categoria | `acetona` → Perfumaria > Estética > Removedores de Esmaltes / Acetona |
| 2026-04-07 | Categoria | `canela` → Mercearia Salgada > Temperos e Molhos > Temperos Pronto em Pó/Sachê |
| 2026-04-07 | Categoria | `oregano` → Mercearia Salgada > Temperos e Molhos > Temperos Pronto em Pó/Sachê |
| 2026-04-07 | Categoria | `soda caustica` → Limpeza > Limpeza de Banheiro > Limpeza Pesada |
| 2026-04-07 | Categoria | `bucha banho` (bigrama) → Perfumaria > Higiene Corporal > Esponja de Banho |
| 2026-04-07 | Categoria | `gel fixador` / `gel capilar` (bigramas) → Perfumaria > Produtos Capilares > Gel Fixador |
| 2026-04-07 | Categoria | `mamadeira` → Perfumaria > Seção Infantil (nível grupo; acento no banco) |
| 2026-04-07 | Categoria | `gel` → Perfumaria > Produtos Capilares (nível grupo; standalone ambíguo) |
| 2026-04-07 | Categoria | `file de peito` → Perecíveis do Autoserviço > Congelados (nível grupo; era AVES, movido para congelados) |
| 2026-04-07 | Categoria | `caderno` → Bazar Geral > Artigos para Papelaria e Armarinho (nível grupo) |
| 2026-04-07 | Categoria | `agua oxigenada` → Perfumaria > Farmácia > Outros Fármacos |
| 2026-04-07 | Combinação não adjacente | `PEIXE` + `POSTAS/POSTA/FILE` → Perecíveis do Autoserviço > Congelados > Peixes Congelado |
| 2026-04-07 | Combinação não adjacente | `PEIXE` + `INTEIRO` → Açougue > Peixes > Peixe Fresco |
| 2026-04-07 | Combinação não adjacente | `CACAU` + `PO` → Mercearia Doce > Culinária Doce > Chocolates em Pó |
| 2026-04-07 | Combinação não adjacente | `AZEITE` + `VIRGEM` → Mercearia Salgada > Azeites > Azeite Extra Virgem |
| 2026-04-07 | Combinação não adjacente | `VINAGRE` + `MACA` → Mercearia Salgada > Vinagres > Vinagre de Maçã |
| 2026-04-07 | Combinação não adjacente | `VINAGRE` + `ARROZ` → Mercearia Salgada > Vinagres > Vinagre de Arroz |
| 2026-04-07 | Combinação não adjacente | `CHOCOLATE` + `BARRA` → Mercearia Doce > Chocolates > Chocolate em Barras |
| 2026-04-07 | Combinação não adjacente | `NOZ` + `MOSCADA` → Mercearia Salgada > Temperos e Molhos > Temperos Pronto em Pó/Sachê |
| 2026-04-07 | Combinação não adjacente | `CERVEJA` + `LATA/LATAO` → Bebidas > Cervejas > Cerveja Lata |
| 2026-04-07 | Combinação não adjacente | `CERVEJA` + `LONG/NECK` → Bebidas > Cervejas > Cerveja Long Neck |
| 2026-04-07 | Abreviação | `capil` → capilar |
| 2026-04-07 | Categoria | `sopao` → Mercearia Salgada > Massas e Sopas > Sopas |
| 2026-04-07 | Categoria | `shoyu` → Mercearia Salgada > Temperos e Molhos > Molho de Soja (movido de grupo para categoria) |
| 2026-04-07 | Categoria | `pimenta` → Mercearia Salgada > Temperos e Molhos > Temperos Pronto em Pó/Sachê |
| 2026-04-07 | Categoria | `paprica` → Mercearia Salgada > Temperos e Molhos > Temperos Pronto em Pó/Sachê |
| 2026-04-07 | Categoria | `lamina` → Perfumaria > Barbearia > Lâminas (Refil) (standalone; bigrama LAMINA BARBEAR já existia) |
| 2026-04-07 | Categoria | `mexerica` / `tangerina` → Hortifruti > Frutas |
| 2026-04-07 | Categoria | `cera` → Limpeza > Limpeza de Pisos (nível grupo) |
| 2026-04-07 | Categoria | `bucha` → Perfumaria > Higiene Corporal (nível grupo; standalone) |
| 2026-04-07 | Categoria | `escova` → Perfumaria > Higiene Corporal (nível grupo; ESCOVA DENTAL bigrama já cobre o específico) |
| 2026-04-07 | Categoria | `sacola` → Bazar Geral > Utilidades Descartáveis (nível grupo) |
| 2026-04-07 | Categoria | `bobina` → Bazar Geral > Utilidades Descartáveis (nível grupo) |
| 2026-04-07 | Categoria | `palito` → Bazar Geral > Utilidades Descartáveis (nível grupo) |
| 2026-04-07 | Categoria | `drink` → Bebidas > Destilados (nível grupo) |
| 2026-04-07 | Categoria | `filtro` → Mercearia Doce > Matinais (nível grupo; filtro de café) |
| 2026-04-07 | Categoria | `torresmo` → Açougue > Suíno (nível grupo) |
| 2026-04-07 | Categoria | `reparador` → Perfumaria > Produtos Capilares (nível grupo) |
| 2026-04-07 | Categoria | `toalha` → Têxtil > Cama, Mesa, Banho (nível grupo) |
| 2026-04-07 | Categoria | `erva` → Bebidas > Matinais (nível grupo; erva-mate) |
| 2026-04-07 | Categoria | `flanela` → Bazar Geral > Utensílios para Limpeza (nível grupo) |
| 2026-04-07 | Categoria | `espuma` → Bazar Geral > Utensílios para Limpeza (nível grupo) |
| 2026-04-07 | Categoria | `tesoura` → Bazar Geral > Artigos para Papelaria e Armarinho (nível grupo) |
| 2026-04-07 | Categoria | `colher` → Bazar Geral > Utilidades da Cozinha (nível grupo) |
| 2026-04-07 | Categoria | `graxa` → Bazar Geral > Ferramentas e Acessórios (nível grupo) |
| 2026-04-07 | Categoria | `cadeado` → Bazar Geral > Ferramentas e Acessórios (nível grupo) |
| 2026-04-07 | Categoria | `extensao` → Bazar Geral > Ferramentas e Acessórios (nível grupo) |
| 2026-04-07 | Categoria | `mangueira` → Bazar Geral > Ferramentas e Acessórios (nível grupo) |
| 2026-04-07 | Combinação não adjacente | `MACARRAO` + `SEMOLA` → Mercearia Salgada > Massas e Sopas > Massa Semola |
| 2026-04-07 | Combinação não adjacente | `MACARRAO` + `OVOS` → Mercearia Salgada > Massas e Sopas > Massa com Ovos |
| 2026-04-07 | Combinação não adjacente | `MASSA` + `PASTEL` → Mercearia Salgada > Massas e Sopas > Outras Massas |
| 2026-04-07 | Combinação não adjacente | `CREME` + `CEBOLA` → Mercearia Salgada > Massas e Sopas > Sopas |
| 2026-04-07 | Combinação não adjacente | `CALDO` + `KNORR/MAGGI` → Mercearia Salgada > Temperos e Molhos > Caldo Tablete e Pó |
| 2026-04-07 | Combinação não adjacente | `MOLHO` + `TOMATE` → Mercearia Salgada > Temperos e Molhos > Molhos e Polpas Tomate |
| 2026-04-07 | Combinação não adjacente | `MOLHO` + `PIMENTA` → Mercearia Salgada > Temperos e Molhos > Molho de Pimenta |
| 2026-04-07 | Combinação não adjacente | `CREME` + `LEITE` → Mercearia Doce > Culinária Doce > Creme de Leite |
| 2026-04-07 | Combinação não adjacente | `DOCE` + `LEITE` → Mercearia Doce > Sobremesas e Outros Doces > Doces de Leite |
| 2026-04-07 | Combinação não adjacente | `TEMPERO` + `SAZON` → Mercearia Salgada > Temperos e Molhos > Temperos Pronto em Pó/Sachê |
| 2026-04-07 | Combinação não adjacente | `LEITE` + `PO` → Commodities > Leite > Leite em Pó |
| 2026-04-07 | Combinação não adjacente | `REPARADOR` + `PONTAS` → Perfumaria > Produtos Capilares (nível grupo) |
| 2026-04-07 | Categoria | `saca rolha` → Bazar Geral > Utilidades da Cozinha > Outras Utilidades de Cozinha |
| 2026-04-07 | Categoria | `bobina` → Uso e Consumo > Embalagens e Bobinas Térmicas > Bobinas Térmicas (era Utilidades Descartáveis) |
| 2026-04-07 | Categoria | `benjamin` → Bazar Geral > Ferramentas e Acessórios > Material Elétrico |
| 2026-04-07 | Marca | BEATS \| Ambev (adicionada ao seed_fabricantes_marcas.py) |
| 2026-04-07 | Combinação não adjacente | `FEIJAO` + `CARIOCA/PRETO/BRANCO/CORDA/JALO` → Commodities > Feijão > subtipo |
| 2026-04-07 | Combinação não adjacente | `ABRIDOR` + `LATA/LATAS/VINHO` → Bazar Geral > Utilidades da Cozinha > Outras Utilidades |
| 2026-04-07 | Combinação não adjacente | `AFIADOR` + `FACA` → Bazar Geral > Utilidades da Cozinha > Outras Utilidades |
| 2026-04-07 | Combinação não adjacente | `ABSORVENTE` + `ABAS` → Perfumaria > Absorventes > Absorvente Externo |
| 2026-04-07 | Combinação não adjacente | `ALICATE` + `CUTICULA` → Perfumaria > Estética > Acessórios Manicure |
| 2026-04-07 | Combinação não adjacente | `CORTADOR` + `UNHAS` → Perfumaria > Estética > Acessórios Manicure |
| 2026-04-07 | Combinação não adjacente | `AGUA` + `COCO` → Bebidas > Águas > Água de Coco (cobre marca separando tokens) |
| 2026-04-07 | Combinação não adjacente | `CAFE` + `SOLUVEL` → Mercearia Doce > Matinais > Café Solúvel (cobre marca separando tokens) |

---

**How to maintain it — simple rule:**

After every commit, ask yourself 3 questions:
```
1. Did I add or change a model?       → update "Status dos models"
2. Did I finish or start a page?      → update "Status das páginas"  
3. Did I make an architectural decision? → update "Decisões de arquitetura"