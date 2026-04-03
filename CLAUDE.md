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
- Tenant — empresa/supermercado (CNPJ sem máscara, 14 dígitos)
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
| 00_inicio.py | ✅ concluído | resumo executivo: cards (faturamento, ICMS a pagar, ticket médio, PIS+COFINS), evolução últimos 6 meses, top 5 fornecedores, rodapé com última data e arquivo importado |
| 01_gestao_vendas.py | ✅ concluído | gestão de vendas: visão geral com evolução mensal, ritmo de vendas (heatmap dia×mês, histograma de ticket), mix comercial (CFOP/CST via C190), clientes B2B e notas; 2 filtros (período, dia da semana) |
| 02_compras.py | ✅ concluído | gestão de compras: notas entrada, itens, por fornecedor, por produto; 4 filtros independentes (período, fornecedor, nº nota, produto) aplicados em todas as seções; CNPJ normalizado no filtro |
| 03_gestao_fiscal.py | ✅ concluído | gestão fiscal: visão geral tributos, ICMS débito/crédito, ST, PIS/COFINS, diagnóstico; 5 abas, 3 filtros (período, CST, CFOP); PIS/COFINS via DocumentoFiscal |
| 04_inventario.py | ✅ concluído | 3 abas: Estoque Virtual (movimentação calculada via C170 com fallback K200/H010/zero), Inventário H005/H010, Saldo K200 |
| 05_produtos.py | ✅ concluído | 3 abas: Cadastro EFD (campos 0200 + filtros), Padronização & Categorias (descrição padronizada, marca, embalagem, scores, situação), Inteligência de Produtos (preço médio, concentração de fornecedor, carga tributária) |
| 08_admin_revisao.py | ✅ concluído | painel interno (sem sidebar); auth por senha; 4 abas: Revisão Individual, Revisão em Lote (checkbox por linha), Marcas & Fabricantes (cadastro + seed), Tokens Desconhecidos (lista tokens não reconhecidos pelo pipeline, filtro por contagem, limpeza de ruído) |
| 06_dados.py | ✅ concluído | 2 abas: Upload (bronze+silver, múltiplos arquivos) e Histórico (5 métricas + tabela de arquivos importados com exclusão) |
| 07_configuracoes.py | ⏳ pendente | |

## Status dos models
| Model | Status | Observações |
|-------|--------|-------------|
| Tenant | ✅ | |
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

## Pendente

### 🔴 Alta prioridade — bloqueiam uso com clientes reais

- [ ] **Autenticação com senha criptografada** — hoje qualquer pessoa com o CNPJ entra; pré-requisito para qualquer deploy
- [ ] **Login por código curto**: coluna `codigo_acesso` (String, unique, nullable) na tabela `tenants`; tela de login tenta código curto primeiro, depois CNPJ; geração automática no cadastro ou definida pelo admin
- [ ] **Migração para PostgreSQL** — troca só o `.env`; necessário antes do deploy
- [ ] **Deploy no Streamlit Cloud**

### 🟡 Média prioridade — funcionalidades novas de valor

- [ ] **Importação de NF-e XML** como fonte independente de dados (arquitetura decidida — ver seção abaixo)
- [ ] **Página `07_configuracoes.py`** — dados do tenant, gestão de usuários, código de acesso; escopo ainda a definir
- [ ] **Padrão de cores** — todas as páginas usam cores diferentes; definir paleta de 5–6 cores e aplicar globalmente via constantes em `utils/` ou tema Streamlit

### 🟢 Baixa prioridade — qualidade e escala

- [ ] **Catálogo global de produtos via EAN**: tabela `catalogo_produtos` (global, sem tenant_id), chave = `cod_barra`. No import do 0200, após upsert normal do produto, buscar o EAN no catálogo e setar `produto.catalogo_id` (FK nullable). Só vincular quando EAN for numérico válido (8, 12, 13 ou 14 dígitos) — ignorar "SEM GTIN" e campos vazios.
- [ ] **Testar inventário** com arquivo EFD real contendo Bloco H e K200
- [ ] **Documentação técnica completa**

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

---

### ✏️ Fila — preencha abaixo, peça "aplica a fila" quando quiser aplicar

#### Abreviações
<!-- formato: abrev → expansão -->


#### Categorias
<!-- formato: keyword → Departamento > Grupo > Categoria -->


#### Marcas
<!-- formato: Nome | Fabricante | alias1, alias2, ... -->


#### Fabricantes
<!-- formato: Nome | alias1, alias2, ... -->

---

### ✅ Histórico de adições aplicadas

| Data | Tipo | Entrada |
|------|------|---------|
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

---

**How to maintain it — simple rule:**

After every commit, ask yourself 3 questions:
```
1. Did I add or change a model?       → update "Status dos models"
2. Did I finish or start a page?      → update "Status das páginas"  
3. Did I make an architectural decision? → update "Decisões de arquitetura"