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
| 08_admin_revisao.py | ✅ concluído | painel interno (sem sidebar); auth por senha; aba Revisão (classificação manual Dep→Grp→Cat com pré-seleção do pipeline) + aba Marcas & Fabricantes (cadastro individual + importação em lote via seed script) |
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
- Pipeline de padronização de produtos: limpeza → abreviações → unidades → marca/fabricante → categorização por vocabulário + Jaccard (54% de cobertura automática na base atual)
- Marcas e fabricantes globais: 45 fabricantes + 225 marcas seedadas; banco tem prioridade sobre dicionário fixo
- scripts/backfill_padronizacao.py: reprocessa produtos existentes; scripts/seed_fabricantes_marcas.py: popula fabricantes/marcas

## Pendente
- [x] Página de cadastro de produto com listagem e filtros
- [x] Página de gestão de compras com filtros independentes por período, fornecedor, nº nota e produto
- [ ] Testar página de inventário com arquivo EFD real contendo Bloco H e K200
- [x] Relatórios fiscais (ICMS, PIS, COFINS) → renomeado para Gestao Fiscal com 5 abas
- [ ] Autenticação completa com senha criptografada
- [x] Silver C190 com tratamento correto de constraint
- [ ] Documentação técnica completa
- [ ] Migração para PostgreSQL (produção)
- [ ] Deploy no Streamlit Cloud
- [x] Compras: revisar gráfico de pizza do CFOP (ficou confuso, melhorar legibilidade)
- [x] Compras: exibir nome/razão social dos fornecedores ao invés de CNPJ nos gráficos e tabelas
- [x] Mudar legenda dos gráficos de barra pra cima pra que os rótulos de dados não atrapalhem a leitura da legenda
- [x] Adicionar na página de dashboard do sistema qual a última data contemplada nos arquivos
- [x] Criar página de gestão de vendas (saídas)
- [ ] Criar um padrão de cores para a ferramenta, as páginas estão usando cores diferentes (definir quantas cores e quais devem ser usadas)
- [x] Renomear as páginas e reordená-las por ordem de importância na sidebar
- [x] Renomear a página dashboard de dados para "Dados" e adicionar a parte de upload de arquivo dentro dela, ajustando o layout para ficar coeso
- [x] Ajustar a página de estoque. Muitos supermercadistas não preenchem o bloco H e não fazem inventário de maneira correta. Portanto, será necessário um ajuste. Faremos um "estoque virtual", em que teremos um controle das entradas e saídas, mas assumindo um estoque inicial igual a zero. Caso o cliente tenha preenchido o bloco H e K, usamos ele como base, se não saímos do ponto zero.
- [x] Revisitar cadastro de produto — 3 abas: Cadastro EFD, Padronização & Categorias, Inteligência de Produtos (preço médio, concentração de fornecedor, carga tributária)
- [x] Transformar o Dashboard atual em resumo executivo real (faturamento, ICMS a pagar, crescimento, top fornecedor) — dados técnicos de importação vão pra página "Dados"
- [x] Verificar se é possível selecionar mais meses e anos ao mesmo tempo, por exemplo: "quero ver os primeiros 3 meses do ano"
- [ ] Importação de NF-e XML como fonte independente de dados (ver decisões abaixo)
- [ ] Atualizar cadastro de produto com as orientações abaixo:
    1. Adicionar amac como redução para amaciante
    2. acai como redução para açaí
    3. procurar uma maneira de incluir também algumas palavras chaves depois de padronizado que já categorizarão mais corretamente (ex.: agua sanitaria vai para limpeza -> limpeza de roupas -> agua sanitaria, acai vai para pereciveis do autosserviço -> congelados -> sorvetes/acai)
```

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

**How to maintain it — simple rule:**

After every commit, ask yourself 3 questions:
```
1. Did I add or change a model?       → update "Status dos models"
2. Did I finish or start a page?      → update "Status das páginas"  
3. Did I make an architectural decision? → update "Decisões de arquitetura"