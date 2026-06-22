# Arquitetura de Dados

> Última atualização: 2026-06-22

---

## Visão geral

```
Fontes                  Bronze              Silver              Gold
──────                  ──────              ──────              ────
EFD .txt   ──┐          Cloudflare R2       Supabase            Supabase
XML NFC-e  ──┤  parser  ───────────────     ────────────────    ─────────────────
XML NF-e   ──┘  Python  raw files (*)       notas_fiscais       gold_kpis_mensais
                        efd/{cnpj}/{nome}    resumo_fiscal       ... (outras gold)
                        xml/{cnpj}/{chv}.xml produtos
                                            fornecedores

                                                                FastAPI → React
```

`(*)` Arquivos originais armazenados permanentemente — fonte de verdade para reprocessamento.

---

## Camada Bronze — Cloudflare R2

- Bucket: `sped-manager`
- Endpoint: `https://50ce142bb2aeec16ccdd829d1d34f1ab.r2.cloudflarestorage.com`
- Custo: $0.015/GB/mês, egresso gratuito
- Acesso Python: `app/utils/r2.py` via `boto3` (S3-compatible)
- Paths:
  - EFD: `efd/{cnpj}/{CNPJ_YYYYMMDD_YYYYMMDD.txt}`
  - XML: `xml/{cnpj}/{chv_nfe_44_digitos}.xml`

**A tabela `efd_raw` foi eliminada** — o arquivo bruto no R2 substitui com vantagem: ocupa menos no Supabase e permite reprocessamento integral.

---

## Camada Silver — Supabase (tabelas leves)

Tabelas estruturadas que o sistema ainda usa diretamente. Ficam no Supabase porque o volume é controlado mesmo com dezenas de clientes.

| Tabela | Fonte | Volume estimado (50 lojas) |
|--------|-------|---------------------------|
| `notas_fiscais` | C100 + NF-e/NFC-e XML | ~2,4 M linhas |
| `resumo_fiscal` | C190 (CST/CFOP/alíq) | ~7,2 M linhas |
| `produtos` | 0200 + XML | ~500 K linhas |
| `fornecedores` | 0150 + XML emit | ~300 K linhas |

**O que NÃO fica no Supabase:**
- `itens_nota_fiscal` de NFC-e (saídas varejo): ~657 M linhas em escala — arquivo XML fica no R2
- `efd_raw`: eliminada — arquivo bruto fica no R2

**Dívida técnica consciente:** as tabelas silver ficam no Supabase enquanto o Streamlit existir, pois as páginas atuais fazem queries direto nelas. Quando o FastAPI assumir todas as rotas e a Gold cobrir todos os casos de uso, silver sai do Supabase.

---

## Camada Gold — Supabase (agregações pré-calculadas)

Resultados prontos para o frontend consumir sem JOIN pesado em runtime.
Calculadas no momento da importação por `app/services/gold_kpis_service.py`.

### Implementadas

| Tabela | Conteúdo | Status |
|--------|----------|--------|
| `gold_kpis_mensais` | Faturamento, compras, ICMS, PIS/COFINS por tenant+mês | ✅ ativa |

### Planejadas (pendentes de implementação)

```
gold_vendas_diarias      tenant_id, data, total_vendas, qtd_cupons, ticket_medio
gold_vendas_produto      tenant_id, ano, mes, cod_item, qtd_vendida, vl_total
gold_vendas_hora         tenant_id, data, hora, qtd_cupons  (heatmap PDV)

gold_compras_fornecedor  tenant_id, ano, mes, cnpj_fornecedor, vl_total, qtd_notas
gold_compras_produto     tenant_id, ano, mes, cod_item, qtd_comprada, preco_medio

gold_fiscal_cfop         tenant_id, ano, mes, cfop, cst_icms, vl_opr, vl_icms

gold_estoque_atual       tenant_id, cod_item, qt_estoque, dt_referencia
```

---

## Fluxo de importação — estado atual

### EFD .txt

```
scripts/importar_efd.py
  1. Lê arquivo → latin-1
  2. Extrai CNPJ + período do registro |0000|
  3. Busca tenant pelo CNPJ
  4. Verifica dedup em arquivos_importados (status=concluido)
  5. Upload para R2  →  efd/{cnpj}/{nome}.txt
  6. silver.processar_conteudo(conteudo)  [em memória, sem tocar efd_raw]
       → notas_fiscais, resumo_fiscal, produtos, fornecedores
  7. gold_kpis_service.calcular_kpis_arquivo()
       → upsert em gold_kpis_mensais
  8. arquivos_importados.status = 'concluido'
```

### XML NFC-e / NF-e

```
parser/xml_parser.py  (via 06_dados.py ou scripts/importar_xmls_pasta.py)
  1. Valida CNPJ do emitente
  2. Deduplica por chv_nfe
  3. Grava notas_fiscais, fornecedores, produtos
  4. Deriva resumo_fiscal por agregação CST/CFOP/alíq
  [upload para R2 ainda não implementado no xml_parser]
```

---

## API — FastAPI

Estrutura criada em `api/`:

```
api/
├── main.py          FastAPI app, CORS
├── auth.py          JWT: criar/decodificar token, hash de senha (bcrypt)
├── deps.py          get_db, get_tenant (Depends)
└── routers/
    ├── auth.py      POST /auth/token · /auth/senha · GET /auth/me
    └── kpis.py      GET /kpis/mensais · /kpis/mensais/{ano}/{mes}
```

**Rodar:** `uvicorn api.main:app --reload --port 8000`
**Docs:** `http://localhost:8000/docs`

**Auth:**
- Login: `POST /auth/token` com `username=CNPJ&password=senha` (form OAuth2)
- Token JWT com TTL de 24h (configurável via `JWT_TTL_HOURS`)
- Todas as rotas de dados requerem `Authorization: Bearer <token>`

**Variáveis de ambiente necessárias:**

| Variável | Descrição |
|----------|-----------|
| `DATABASE_URL` | PostgreSQL Supabase ou SQLite local |
| `JWT_SECRET` | Chave secreta para assinar tokens |
| `JWT_TTL_HOURS` | Validade do token (padrão: 24) |
| `R2_ENDPOINT` | Endpoint Cloudflare R2 |
| `R2_ACCESS_KEY` | Access key do bucket |
| `R2_SECRET_KEY` | Secret key do bucket |
| `R2_BUCKET` | Nome do bucket (padrão: sped-manager) |
| `ADMIN_PASSWORD` | Senha do painel admin (Streamlit) |
| `CORS_ORIGINS` | Origens permitidas (padrão: http://localhost:5173) |

---

## O que não muda com a migração FastAPI

Todo o código de `app/models/`, `app/repositories/`, `app/services/`, `app/parser/` e `app/utils/` é reutilizado integralmente pelo FastAPI. Só a camada de apresentação (`app/pages/`) é substituída.

---

## Motivação: por que não tudo no Supabase?

Volume estimado de NFC-e (itens de saída):
```
800 cupons/dia × 15 itens × 365 dias × 50 clientes × 3 anos ≈ 657 milhões de linhas
```
95% das queries do frontend precisam de agregações, não de itens individuais.
Guardar esses itens no PostgreSQL seria caro e desnecessário.

---

## Evolução futura (quando houver escala)

Se surgir necessidade de consultar itens individuais históricos em tempo real:

```
R2 (bronze raw) → Parquet no R2 (silver) → DuckDB para queries analíticas
```

Os arquivos já estão no R2 — bastaria um job de conversão para Parquet.
Não há migração de dados: é uma adição, não uma substituição.
