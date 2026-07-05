# Guia de desenvolvimento

Setup local e fluxo de trabalho para quem está entrando no projeto.

## 1. Acesso

- **GitHub:** peça convite como collaborator em `plinioneto/sped-manager` (Settings → Collaborators).
- **Credenciais (`.env`):** peça ao Plínio o conteúdo real das variáveis abaixo por um canal seguro (gerenciador de senha compartilhado — 1Password/Bitwarden — ou app de mensagem, nunca em issue/PR/commit público). O repositório é **público**, então nada disso pode ir para o Git.

## 2. Setup do ambiente

```bash
git clone https://github.com/plinioneto/sped-manager.git
cd sped-manager
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e preencha com as credenciais reais recebidas no passo 1:

```bash
cp .env.example .env
```

| Variável | Descrição |
|----------|-----------|
| `DATABASE_URL` | Supabase PostgreSQL (compartilhado — mesmo banco de produção por enquanto, ver seção 5) |
| `SECRET_KEY` / `JWT_SECRET` | Chaves de sessão/token — **usar exatamente o mesmo valor entre todos os devs**, senão tokens emitidos por um não são válidos no outro |
| `ADMIN_PASSWORD` | Senha do painel admin Streamlit |
| `R2_ACCESS_KEY` / `R2_SECRET_KEY` / `R2_ENDPOINT` / `R2_BUCKET` | Cloudflare R2 (armazenamento dos arquivos brutos EFD/XML) |

Rode as migrations (banco já deve estar com o schema, mas garante que está em dia):

```bash
alembic upgrade head
```

## 3. Rodando o projeto

**API (FastAPI):**
```bash
uvicorn api.main:app --reload --port 8000
```
Docs interativas em `http://localhost:8000/docs`.

**Streamlit (legado, ainda é a interface principal):**
```bash
streamlit run app/main.py
```

## 4. Fluxo de trabalho em equipe

`main` está protegida: push direto é bloqueado, todo merge precisa de Pull Request com pelo menos 1 aprovação.

1. Antes de começar algo, veja a seção **🎯 Próximos passos** do [`CLAUDE.md`](../CLAUDE.md) — é o backlog priorizado do MVP.
2. Crie uma branch a partir de `main`: `feat/nome-da-coisa`, `fix/nome-do-bug`, `docs/nome`.
3. Commits seguem [Conventional Commits](https://www.conventionalcommits.org/) em português: `tipo(escopo): mensagem` (ex: `feat(api): adiciona rota /compras/mensais`). Veja `git log` para exemplos.
4. Abra o PR cedo, mesmo incompleto (rascunho), se for uma tarefa grande — facilita revisão incremental.
5. Combine no PR ou no chat quem está mexendo em qual pasta, para reduzir conflito de merge. O roadmap do `CLAUDE.md` já separa bem por camada (`api/routers/`, `app/services/`, frontend React).

### Cuidado com Alembic (migrations)

Como as duas pessoas podem gerar migrations, avise no chat/PR **antes** de rodar `alembic revision --autogenerate`, para não criar dois heads a partir do mesmo ponto (conflito de migration). Se acontecer, resolva com `alembic merge heads` antes de aplicar.

### Depois de cada commit

O `CLAUDE.md` tem uma seção "Como manter este arquivo" — sempre que um model, um passo do MVP ou uma decisão de arquitetura mudar, atualize o `CLAUDE.md` correspondente no mesmo PR.

## 5. Banco de dados: mesmo ambiente para os dois

Por ora, ambos os devs apontam para o **mesmo Supabase de produção** (`DATABASE_URL` compartilhada) — decisão consciente para simplificar o início da colaboração. Pontos de atenção:

- Evite rodar scripts destrutivos (`scripts/apagar_ano.py`, `scripts/liberar_espaco_supabase.py`) sem avisar o outro dev antes.
- Dados de teste devem usar um `tenant_id` de teste dedicado, não misturar com tenants de clientes reais.
- Se o projeto crescer ou algum teste começar a arriscar dados de produção, revisitar essa decisão e separar um projeto Supabase de dev/staging.
