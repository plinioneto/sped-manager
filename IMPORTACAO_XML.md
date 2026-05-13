# Importação de XMLs de NFC-e / NF-e

## Visão geral

A importação é feita via terminal pelo script `scripts/importar_xmls_pasta.py`.
Ele processa arquivos em lote (~3.000 arq/s), ignora duplicatas automaticamente e não interfere no Streamlit.

---

## Estrutura esperada de pastas

```
PASTA RAIZ/
  CAIXA01/
    2025/
      01/
        Transmitidos/    <- importa
        *.xml            <- importa (XMLs soltos na pasta do mês)
        Contingencia/    <- ignorado
        ErroTransmissao/ <- ignorado
      02/
        ...
  CAIXA02/
    ...
```

> Os nomes das pastas de caixa, ano e mês podem variar — o script lê a estrutura conforme ela estiver organizada.

---

## Como importar

### 1. Abra o terminal na pasta do projeto

```powershell
cd "D:\Data Science\Projeto SPED\Dashboard\sped-manager"
```

### 2. Certifique-se de que o Streamlit está fechado

O SQLite não suporta múltiplas conexões de escrita simultâneas. Feche o Streamlit antes de importar.

### 3. Execute o script

**Um mês específico (recomendado para testes):**
```powershell
.\.venv\Scripts\python.exe scripts/importar_xmls_pasta.py `
  --pasta "D:\caminho\para\PASTA" `
  --cnpj 68514439000176 `
  --ano 2025 `
  --mes 01
```

**Um ano completo:**
```powershell
.\.venv\Scripts\python.exe scripts/importar_xmls_pasta.py `
  --pasta "D:\caminho\para\PASTA" `
  --cnpj 68514439000176 `
  --ano 2025
```

**Todos os anos disponíveis:**
```powershell
.\.venv\Scripts\python.exe scripts/importar_xmls_pasta.py `
  --pasta "D:\caminho\para\PASTA" `
  --cnpj 68514439000176
```

### 4. Ver o que seria importado sem gravar (dry-run)

```powershell
.\.venv\Scripts\python.exe scripts/importar_xmls_pasta.py `
  --pasta "D:\caminho\para\PASTA" `
  --cnpj 68514439000176 `
  --ano 2025 `
  --dry-run
```

---

## Após a importação: padronizar produtos

O script importa os dados fiscais mas não classifica os produtos na hierarquia de categorias.
Rode o backfill depois:

```powershell
.\.venv\Scripts\python.exe scripts/backfill_padronizacao.py --todos
```

> Isso pode demorar alguns minutos dependendo do volume de produtos novos.

---

## Clientes cadastrados

| Cliente | CNPJ |
|---------|------|
| Franmak Supermercado Ltda | 68514439000176 |

> Para cadastrar um novo cliente, acesse o painel admin em `localhost:8501/08_admin_revisao`.

---

## O que o script ignora

| Pasta | Motivo |
|-------|--------|
| `Contingencia/` | NFC-es emitidas offline — status de autorização incerto |
| `ErroTransmissao/` | Notas rejeitadas pela SEFAZ |
| `Cancelados/` | Notas canceladas não devem entrar no faturamento |

---

## Histórico de importações — Franmak

| Período | Registros importados | Data |
|---------|---------------------|------|
| 2024 (jan–dez) | 198.973 NFC-es | 2026-05-13 |
| 2025 (jan–dez) | 66.603 NFC-es | 2026-05-13 |
