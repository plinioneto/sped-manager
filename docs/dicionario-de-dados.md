# Dicionário de Dados — SPED Manager

> Gerado em 2026-05-29. Reflete o schema após a migration `5a7e9db4919c` (model_review_v2).

---

## Visão geral

O banco tem dois grupos de tabelas:

| Grupo | Tabelas | Descrição |
|-------|---------|-----------|
| **Multi-tenant** | `tenants`, `produtos`, `documentos_fiscais`, `itens_fiscais`, `icms_c190`, `participantes`, `inventarios_h005`, `inventarios_h010`, `estoques_k200`, `efd_raw`, `arquivos_importados` | Dados de cada loja. Toda query filtra por `tenant_id`. |
| **Global** | `grupos_empresariais`, `fabricantes`, `marcas`, `departamentos`, `grupos`, `categorias`, `catalogo_produtos`, `tokens_desconhecidos` | Dados compartilhados entre todos os tenants (catálogo, hierarquia, marcas). Não têm `tenant_id`. |

---

## Tabelas multi-tenant

### `tenants`
Representa cada loja/supermercado cliente do sistema.

| Coluna | Tipo | Obrigatório | Descrição |
|--------|------|-------------|-----------|
| `id` | Integer PK | ✅ | Identificador interno |
| `nome` | String | ✅ | Nome da loja |
| `cnpj` | String(14) UNIQUE | ✅ | CNPJ sem máscara (14 dígitos). Formatado só na exibição com `formatar_cnpj()` |
| `ativo` | Boolean | — | `true` por padrão |
| `criado_em` | DateTime | — | Data de cadastro (UTC) |
| `grupo_id` | Integer FK → `grupos_empresariais.id` | — | Grupo ao qual a loja pertence. Nullable |
| `senha_hash` | String | — | Hash bcrypt da senha. Nullable (autenticação futura via JWT) |
| `codigo_acesso` | String UNIQUE | — | Código alternativo de acesso. Nullable |

---

### `participantes`
Fornecedores, clientes e outras contrapartes. Corresponde ao registro `0150` do EFD.

| Coluna | Tipo | Obrigatório | Descrição |
|--------|------|-------------|-----------|
| `id` | Integer PK | ✅ | — |
| `tenant_id` | Integer FK → `tenants.id` | ✅ | — |
| `cod_part` | String | ✅ | Código interno do EFD (ex: "0001") ou CNPJ quando a origem é XML |
| `nome` | String | — | Razão social |
| `cnpj` | String(14) | — | CNPJ sem máscara. Usado para deduplicação entre EFD e XML |
| `cpf` | String(11) | — | CPF sem máscara (pessoa física) |
| `ie` | String | — | Inscrição Estadual |
| `cod_pais` | String(5) | — | Código do país (ex: "1058" = Brasil) |
| `cod_mun` | String(7) | — | Código IBGE do município |
| `suframa` | String | — | Número SUFRAMA |
| `endereco` | String | — | Logradouro |
| `num` | String | — | Número do endereço |
| `compl` | String | — | Complemento |
| `bairro` | String | — | Bairro |
| `criado_em` | DateTime | — | — |

**Constraint única:** `(tenant_id, cod_part)`

> **Atenção — deduplicação EFD vs XML:** O mesmo fornecedor pode gerar dois registros se importado via EFD (cod_part = "0001") e depois via XML (cod_part = CNPJ). O `xml_parser._upsert_participante` faz lookup por CNPJ primeiro para reusar o registro existente do EFD.

---

### `documentos_fiscais`
Cabeçalho de notas fiscais. Corresponde ao registro `C100` do EFD ou ao `<infNFe>` do XML.

| Coluna | Tipo | Obrigatório | Descrição |
|--------|------|-------------|-----------|
| `id` | Integer PK | ✅ | — |
| `tenant_id` | Integer FK → `tenants.id` | ✅ | — |
| `chv_nfe` | String(44) | — | Chave de acesso da NF-e/NFC-e (44 dígitos). Principal chave de negócio |
| `ind_oper` | String | — | Indicador de operação: `"0"` = entrada, `"1"` = saída |
| `ind_emit` | String | — | Indicador do emitente: `"0"` = emissão própria, `"1"` = terceiros |
| `cod_part` | String | — | Código do participante (FK lógica → `participantes.cod_part`) |
| `cod_mod` | String | — | Modelo do documento: `"55"` = NF-e, `"65"` = NFC-e |
| `cod_sit` | String | — | Situação: `"00"` = regular |
| `ser` | String | — | Série da nota |
| `num_doc` | String | — | Número da nota |
| `dt_doc` | DateTime | — | Data de emissão |
| `dt_e_s` | DateTime | — | Data de entrada/saída |
| `vl_doc` | Numeric(15,2) | — | Valor total do documento |
| `vl_desc` | Numeric(15,2) | — | Desconto total |
| `vl_merc` | Numeric(15,2) | — | Valor das mercadorias |
| `vl_bc_icms` | Numeric(15,2) | — | Base de cálculo do ICMS |
| `vl_icms` | Numeric(15,2) | — | Valor do ICMS |
| `vl_bc_icms_st` | Numeric(15,2) | — | Base de cálculo do ICMS-ST |
| `vl_icms_st` | Numeric(15,2) | — | Valor do ICMS-ST |
| `vl_pis` | Numeric(15,2) | — | Valor do PIS |
| `vl_cofins` | Numeric(15,2) | — | Valor do COFINS |
| `fonte` | String(3) | — | Origem do dado: `"efd"` ou `"xml"` |
| `criado_em` | DateTime | — | — |

**Constraint única:** `(tenant_id, chv_nfe)` — garante que a mesma NF-e não é importada em duplicata.

---

### `itens_fiscais`
Itens de nota fiscal. Corresponde ao registro `C170` do EFD ou ao `<det>` do XML.

| Coluna | Tipo | Obrigatório | Descrição |
|--------|------|-------------|-----------|
| `id` | Integer PK | ✅ | — |
| `tenant_id` | Integer FK → `tenants.id` | ✅ | — |
| `chv_nfe` | String(44) | — | Chave da NF-e pai — mesmo valor de `documentos_fiscais.chv_nfe` |
| `documento_id` | Integer FK → `documentos_fiscais.id` | — | FK para o cabeçalho |
| `num_item` | Integer | — | Número sequencial do item na nota |
| `cod_item` | String | — | Código interno do produto (mesmo do `produtos.cod_item`) |
| `descr_compl` | String | — | Descrição complementar do item |
| `qtd` | Numeric(15,4) | — | Quantidade (4 casas para pesos fracionados) |
| `unid` | String(6) | — | Unidade: UN, KG, CX, PC... |
| `vl_item` | Numeric(15,2) | — | Valor bruto do item |
| `vl_desc` | Numeric(15,2) | — | Desconto no item |
| `cst_icms` | String | — | CST do ICMS (ex: "060", "400") |
| `cfop` | String | — | CFOP (ex: "5405", "1102") |
| `vl_bc_icms` | Numeric(15,2) | — | Base de cálculo do ICMS |
| `aliq_icms` | Numeric(7,4) | — | Alíquota do ICMS (ex: 12.0000) |
| `vl_icms` | Numeric(15,2) | — | Valor do ICMS |
| `vl_pis` | Numeric(15,2) | — | Valor do PIS |
| `vl_cofins` | Numeric(15,2) | — | Valor do COFINS |
| `cst_pis` | String(3) | — | CST do PIS (ex: "01", "07") |
| `cst_cofins` | String(3) | — | CST do COFINS |
| `aliq_pis` | Numeric(7,4) | — | Alíquota do PIS |
| `aliq_cofins` | Numeric(7,4) | — | Alíquota do COFINS |

**Constraint única:** `(tenant_id, chv_doc, num_item)`

> **Atenção — cod_item por fonte:**
> - EFD e NFC-e (saída): código interno da loja → consistente e usável para análises de vendas
> - NF-e entrada com EAN: EAN do produto → inconsistente com código interno
> - NF-e entrada sem EAN: `cProd` do fornecedor → código externo
>
> O cruzamento compra×venda por produto exige mapeamento manual. Use `catalogo_produtos` via `cod_barra` como ponto de convergência.

---

### `icms_c190`
Totais de ICMS por CST/CFOP/alíquota dentro de um documento. Corresponde ao registro `C190` do EFD ou é derivado por agregação dos itens do XML.

| Coluna | Tipo | Obrigatório | Descrição |
|--------|------|-------------|-----------|
| `id` | Integer PK | ✅ | — |
| `tenant_id` | Integer FK → `tenants.id` | ✅ | — |
| `chv_nfe` | String(44) | ✅ | Chave da NF-e — mesmo valor de `documentos_fiscais.chv_nfe` |
| `documento_id` | Integer FK → `documentos_fiscais.id` | — | FK para o cabeçalho (nullable: C190 pode existir sem C100 no EFD) |
| `cst_icms` | String(3) | — | CST do ICMS |
| `cfop` | String(4) | — | CFOP |
| `aliq_icms` | Numeric(7,4) | — | Alíquota do ICMS |
| `vl_opr` | Numeric(15,2) | — | Valor das operações |
| `vl_bc_icms` | Numeric(15,2) | — | Base de cálculo do ICMS |
| `vl_icms` | Numeric(15,2) | — | Valor do ICMS |
| `vl_bc_icms_st` | Numeric(15,2) | — | Base de cálculo do ICMS-ST |
| `vl_icms_st` | Numeric(15,2) | — | Valor do ICMS-ST |
| `vl_red_bc` | Numeric(15,2) | — | Valor da redução da BC |
| `vl_pis` | Numeric(15,2) | — | Valor do PIS |
| `vl_cofins` | Numeric(15,2) | — | Valor do COFINS |
| `cod_obs` | String | — | Código de observação |
| `criado_em` | DateTime | — | — |

**Constraint única:** `(tenant_id, chv_nfe, cst_icms, cfop, aliq_icms)`

---

### `produtos`
Cadastro de produtos da loja (registro `0200` do EFD), enriquecido pelo pipeline de padronização.

| Coluna | Tipo | Obrigatório | Descrição |
|--------|------|-------------|-----------|
| `id` | Integer PK | ✅ | — |
| `tenant_id` | Integer FK → `tenants.id` | ✅ | — |
| `cod_item` | String | ✅ | Código interno da loja (mesmo usado em `itens_fiscais.cod_item`) |
| `descr_item` | String | ✅ | Descrição original do EFD (uppercase, latin-1) |
| `cod_barra` | String | — | EAN-13 / EAN-8. Quando válido, permite herança de classificação via `catalogo_produtos` |
| `unid_inv` | String(6) | — | Unidade de inventário: UN, KG, CX... |
| `tipo_item` | String | — | Tipo: "00"=mercadoria para revenda, "01"=MP, etc. |
| `cod_ncm` | String(8) | — | NCM sem pontuação |
| `cest` | String | — | CEST (substituição tributária) |
| `aliq_icms` | Float | — | Alíquota padrão do ICMS (campo legado, substituir por dados do C190) |
| `ativo` | Boolean | — | `true` por padrão |
| `criado_em` | DateTime | — | — |
| **Padronização** | | | |
| `descricao_padrao` | String(200) | — | Descrição normalizada pelo pipeline (sem abreviações, em ordem canônica) |
| `tipo_produto` | String(60) | — | Categoria semântica: REFRIGERANTE, BISCOITO, LEITE... |
| `tipo_embalagem` | String(30) | — | PET, LATA, VIDRO, SACO, CAIXA... |
| `peso_volume_valor` | Numeric(12,3) | — | Valor numérico do peso/volume (ex: 1.5) |
| `peso_volume_unidade` | String(10) | — | Unidade: ML, L, G, KG, UN... |
| `score_padronizacao` | Numeric(5,4) | — | Confiança da padronização (0.0 a 1.0) |
| `origem_padronizacao` | String(20) | — | `regra` \| `fuzzy` \| `catalogo` \| `manual` \| `manual_sem_cat` |
| `revisao_necessaria` | Boolean | — | Flag para revisão manual no painel admin |
| `marca_id` | Integer FK → `marcas.id` | — | — |
| `categoria_id` | Integer FK → `categorias.id` | — | Nível 3 da hierarquia |
| `grupo_id` | Integer FK → `grupos.id` | — | Nível 2 (cache de performance — derivável via categoria) |
| `departamento_id` | Integer FK → `departamentos.id` | — | Nível 1 (cache de performance — derivável via grupo) |
| `score_categoria` | Numeric(5,4) | — | Confiança da classificação automática (0.0 a 1.0) |

**Constraint única:** `(tenant_id, cod_item)`

> **Regra de proteção:** produtos com `origem_padronizacao IN ('manual', 'manual_sem_cat')` nunca são sobrescritos pelo backfill automático.

---

### `inventarios_h005`
Cabeçalho de inventário físico. Corresponde ao registro `H005` do EFD.

| Coluna | Tipo | Obrigatório | Descrição |
|--------|------|-------------|-----------|
| `id` | Integer PK | ✅ | — |
| `tenant_id` | Integer FK → `tenants.id` | ✅ | — |
| `dt_inv` | DateTime | ✅ | Data do inventário |
| `vl_inv` | Float | — | Valor total do inventário |
| `mot_inv` | String(2) | — | Motivo: "01"=no final do período, "02"=na mudança de forma de tributação, etc. |
| `file_path` | String | — | Arquivo EFD de origem |
| `criado_em` | DateTime | — | — |

**Constraint única:** `(tenant_id, dt_inv, mot_inv)`

---

### `inventarios_h010`
Itens do inventário físico. Corresponde ao registro `H010` do EFD.

| Coluna | Tipo | Obrigatório | Descrição |
|--------|------|-------------|-----------|
| `id` | Integer PK | ✅ | — |
| `tenant_id` | Integer FK → `tenants.id` | ✅ | — |
| `inventario_id` | Integer FK → `inventarios_h005.id` | — | FK para o cabeçalho do inventário |
| `dt_inv` | DateTime | ✅ | Data do inventário (desnormalizado do H005 para facilitar queries) |
| `cod_item` | String | ✅ | Código interno do produto |
| `unid` | String(6) | — | Unidade |
| `qtd` | Float | — | Quantidade em estoque |
| `vl_unit` | Float | — | Valor unitário |
| `vl_item` | Float | — | Valor total do item (qtd × vl_unit) |
| `ind_prop` | String(1) | — | Propriedade: `"0"` = próprio, `"1"` = de terceiro |
| `cod_part` | String | — | Proprietário (quando ind_prop = "1") |
| `txt_compl` | String | — | Texto complementar |
| `cod_cta` | String | — | Código da conta contábil |
| `criado_em` | DateTime | — | — |

**Constraint única:** `(tenant_id, dt_inv, cod_item, ind_prop)`

---

### `estoques_k200`
Saldo de estoque periódico. Corresponde ao registro `K200` do EFD (Bloco K).

| Coluna | Tipo | Obrigatório | Descrição |
|--------|------|-------------|-----------|
| `id` | Integer PK | ✅ | — |
| `tenant_id` | Integer FK → `tenants.id` | ✅ | — |
| `dt_est` | DateTime | ✅ | Data do saldo |
| `cod_item` | String | ✅ | Código interno do produto |
| `qt_est` | Float | — | Quantidade em estoque |
| `ind_est` | String(1) | — | Indicador: `"0"` = próprio, `"1"` = de terceiro, `"2"` = em poder de terceiro |
| `criado_em` | DateTime | — | — |

**Constraint única:** `(tenant_id, dt_est, cod_item, ind_est)`

---

### `efd_raw`
Bronze layer — cada linha do arquivo EFD armazenada literalmente. Usada para reprocessamento silver sem precisar do arquivo original.

| Coluna | Tipo | Obrigatório | Descrição |
|--------|------|-------------|-----------|
| `id` | Integer PK | ✅ | — |
| `tenant_id` | Integer FK → `tenants.id` | ✅ | — |
| `file_path` | String | ✅ | Caminho do arquivo EFD de origem |
| `num_linha` | Integer | ✅ | Número da linha no arquivo |
| `tipo_registro` | String(10) | ✅ | Ex: "C100", "C170", "0200" |
| `conteudo_linha` | Text | ✅ | Linha completa do EFD (encoding latin-1 convertido para UTF-8) |
| `ingest_timestamp` | DateTime | ✅ | Momento da ingestão |

> **Candidato a arquivamento:** com volume alto, mover para S3 e manter só os silver no banco.

---

### `arquivos_importados`
Histórico de importações de arquivos EFD.

| Coluna | Tipo | Obrigatório | Descrição |
|--------|------|-------------|-----------|
| `id` | Integer PK | ✅ | — |
| `tenant_id` | Integer FK → `tenants.id` | ✅ | — |
| `nome_original` | String | ✅ | Nome original do arquivo enviado |
| `nome_padronizado` | String | ✅ | Nome após renomeação: `CNPJ_YYYYMMDD_YYYYMMDD.txt` |
| `cnpj` | String(14) | ✅ | CNPJ extraído do arquivo (validado contra o tenant) |
| `periodo_ini` | String(8) | ✅ | Data inicial do período (`YYYYMMDD`) |
| `periodo_fin` | String(8) | ✅ | Data final do período (`YYYYMMDD`) |
| `status` | String | — | `"pendente"` \| `"processado"` \| `"erro"` |
| `erro_msg` | String | — | Mensagem de erro quando `status = "erro"` |
| `criado_em` | DateTime | — | — |
| `processado_em` | DateTime | — | Momento em que o processamento terminou |

---

## Tabelas globais (sem tenant_id)

### `grupos_empresariais`
Agrupa tenants de um mesmo dono (rede de supermercados).

| Coluna | Tipo | Obrigatório | Descrição |
|--------|------|-------------|-----------|
| `id` | Integer PK | ✅ | — |
| `nome` | String | ✅ | Nome do grupo (ex: "Rede GS") |
| `ativo` | Boolean | — | `true` por padrão |
| `criado_em` | DateTime | — | — |

---

### `fabricantes`
Fabricantes / grupos industriais (Unilever, BRF, Ambev, P&G...).

| Coluna | Tipo | Obrigatório | Descrição |
|--------|------|-------------|-----------|
| `id` | Integer PK | ✅ | — |
| `nome` | String(100) UNIQUE | ✅ | Nome canônico do fabricante |
| `cnpj` | String(14) | — | CNPJ do fabricante (nullable — nem todos têm CNPJ BR) |
| `aliases` | JSONB | — | Array de variações de nome encontradas nas descrições (ex: `["UNILEVER BR", "UNILEVER BRASIL"]`) |
| `ativo` | Boolean | — | `true` por padrão |

> 45 fabricantes seedados em `scripts/seed_fabricantes_marcas.py`.

---

### `marcas`
Marcas comerciais (Dove, Sadia, Skol, Gillette...).

| Coluna | Tipo | Obrigatório | Descrição |
|--------|------|-------------|-----------|
| `id` | Integer PK | ✅ | — |
| `fabricante_id` | Integer FK → `fabricantes.id` | — | Fabricante dono da marca. Nullable |
| `nome` | String(100) UNIQUE | ✅ | Nome canônico da marca |
| `aliases` | JSONB | — | Array de variações (ex: `["COCA", "COCA-COLA", "COCACOLA"]`) |
| `categoria` | String(50) | — | Segmento livre: bebidas, limpeza, frios, higiene, alimentos... |
| `ativo` | Boolean | — | `true` por padrão |

> 225 marcas seedadas. O banco tem prioridade sobre o dicionário fixo no pipeline.

---

### `departamentos` / `grupos` / `categorias`
Hierarquia global de classificação de produtos em 3 níveis.

| Nível | Tabela | Qtd | Exemplo |
|-------|--------|-----|---------|
| 1 | `departamentos` | 18 | BEBIDAS, LIMPEZA, PERFUMARIA, AÇOUGUE |
| 2 | `grupos` | 118 | CERVEJAS, REFRIGERANTE, BISCOITO DOCE |
| 3 | `categorias` | 720 | CERVEJA PURO MALTE, REFRIGERANTE COLA |

**`departamentos`**

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | Integer PK | — |
| `descricao` | String(100) UNIQUE | Nome do departamento (maiúsculas, sem acento) |

**`grupos`**

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | Integer PK | — |
| `departamento_id` | Integer FK → `departamentos.id` | — |
| `descricao` | String(100) | Nome do grupo |

**`categorias`**

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | Integer PK | — |
| `grupo_id` | Integer FK → `grupos.id` | — |
| `descricao` | String(150) | Nome da categoria |

---

### `catalogo_produtos`
Catálogo global de produtos por EAN. Permite que a classificação feita para um produto de um tenant seja herdada por outros tenants que vendem o mesmo item.

| Coluna | Tipo | Obrigatório | Descrição |
|--------|------|-------------|-----------|
| `id` | Integer PK | ✅ | — |
| `cod_barra` | String(14) UNIQUE | ✅ | EAN-13 / EAN-8 — chave de negócio |
| `descricao_padrao` | String(200) | — | Descrição normalizada |
| `tipo_produto` | String(60) | — | Categoria semântica |
| `tipo_embalagem` | String(30) | — | Tipo de embalagem |
| `peso_volume_valor` | Numeric(12,3) | — | — |
| `peso_volume_unidade` | String(10) | — | — |
| `categoria_id` | Integer FK → `categorias.id` | — | — |
| `grupo_id` | Integer FK → `grupos.id` | — | — |
| `departamento_id` | Integer FK → `departamentos.id` | — | — |
| `marca_id` | Integer FK → `marcas.id` | — | — |
| `score_categoria` | Numeric(5,4) | — | — |
| `origem_padronizacao` | String(20) | — | `regra` \| `manual` \| `catalogo` |
| `atualizado_em` | DateTime | — | Atualizado automaticamente a cada mudança |

> 2.657 entradas seedadas. Quando um produto com EAN válido é importado, o sistema busca aqui antes de rodar o pipeline — herança gratuita de classificação.

---

### `tokens_desconhecidos`
Tokens encontrados nas descrições de produtos que nenhum dicionário do pipeline reconheceu. Serve de insumo para alimentar novos dicionários.

| Coluna | Tipo | Obrigatório | Descrição |
|--------|------|-------------|-----------|
| `id` | Integer PK | ✅ | — |
| `token` | String(100) UNIQUE | ✅ | Token normalizado (sem acento, uppercase) |
| `contagem` | Integer | ✅ | Quantas vezes apareceu no total |
| `primeiro_visto` | DateTime | — | — |
| `ultimo_visto` | DateTime | — | Atualizado automaticamente |
| `exemplo` | Text | — | Uma descrição original onde o token apareceu |

> Acessível no painel admin → aba "Tokens Desconhecidos", ordenados por frequência.

---

## Relacionamentos principais

```
GrupoEmpresarial (1) ──── (N) Tenant
Tenant (1) ──── (N) Produto
Tenant (1) ──── (N) DocumentoFiscal
Tenant (1) ──── (N) ItemFiscal
Tenant (1) ──── (N) IcmsC190
Tenant (1) ──── (N) Participante
Tenant (1) ──── (N) InventarioH005 ──── (N) InventarioH010
Tenant (1) ──── (N) EstoqueK200
Tenant (1) ──── (N) EfdRaw
Tenant (1) ──── (N) ArquivoImportado

DocumentoFiscal (1) ──── (N) ItemFiscal
DocumentoFiscal (1) ──── (N) IcmsC190

Fabricante (1) ──── (N) Marca
Marca (1) ──── (N) Produto
Departamento (1) ──── (N) Grupo (1) ──── (N) Categoria
Categoria (1) ──── (N) Produto
CatalogoProduto ── (EAN) ── Produto  [relação lógica, não FK]
```

---

## Convenções

| Regra | Detalhe |
|-------|---------|
| CNPJ | Sempre sem máscara (14 dígitos). Formatado só na exibição com `formatar_cnpj()` |
| Valores monetários | `Numeric(15,2)` — nunca `Float` para evitar erro de representação binária |
| Alíquotas | `Numeric(7,4)` — ex: `12.0000` para 12% |
| Datas | `DateTime` em UTC. Formatadas na camada de apresentação |
| Multi-tenant | Todo repository filtra por `tenant_id`. Nunca fazer query sem esse filtro |
| Encoding EFD | Arquivos latin-1, convertidos para UTF-8 na ingestão |
| Upsert | Todas as tabelas silver têm constraint única + upsert (não duplica em reprocessamento) |
