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
| 01_dashboard.py | ✅ concluído | 4 métricas reais do banco |
| 02_upload_sped.py | ✅ concluído | bronze + silver, múltiplos arquivos |
| 03_estoque.py | ⏳ pendente | |
| 04_relatorios.py | ⏳ pendente | |
| 05_configuracoes.py | ⏳ pendente | |

## Status dos models
| Model | Status | Observações |
|-------|--------|-------------|
| Tenant | ✅ | |
| Produto | ✅ | campos 0200 completos |
| DocumentoFiscal | ✅ | campos C100 completos |
| ItemFiscal | ✅ | campos C170 completos |
| EfdRaw | ✅ | |
| ArquivoImportado | ✅ | |
| IcmsC190 | ❌ removido | problema de constraint — reimplementar |

## Status do parser
| Etapa | Status | Observações |
|-------|--------|-------------|
| Renomeação | ✅ | CNPJ_YYYYMMDD_YYYYMMDD.txt |
| Bronze | ✅ | efd_raw linha a linha |
| Silver C100 | ✅ | todos os campos |
| Silver C170 | ✅ | todos os campos |
| Silver 0200 | ✅ | todos os campos |
| Silver C190 | ❌ pendente | constraint única com problema |

## Decisões de arquitetura
- SQLite no dev, PostgreSQL na produção — troca só o .env
- Multi-tenant via tenant_id em todos os models
- Bronze/Silver seguindo padrão do Databricks original
- Storage local em storage/arquivos/ — vira S3 na produção
- Autenticação temporária só por CNPJ — senha ainda não implementada

## Pendente
- [ ] Página de estoque com listagem e filtros
- [ ] Relatórios fiscais (ICMS, PIS, COFINS)
- [ ] Autenticação completa com senha criptografada
- [ ] Silver C190 com tratamento correto de constraint
- [ ] Documentação técnica completa
- [ ] Migração para PostgreSQL (produção)
- [ ] Deploy no Streamlit Cloud
```

**How to maintain it — simple rule:**

After every commit, ask yourself 3 questions:
```
1. Did I add or change a model?       → update "Status dos models"
2. Did I finish or start a page?      → update "Status das páginas"  
3. Did I make an architectural decision? → update "Decisões de arquitetura"