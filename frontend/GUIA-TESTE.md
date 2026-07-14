# Guia de teste do frontend (SaaS multi-tenant v1)

Como subir o ambiente completo (API + frontend + link público) para testar a
usabilidade fora do `localhost`, sem precisar de deploy.

## Pré-requisitos (setup único, já feito nesta máquina)

- `.venv` na raiz do projeto com `fastapi`/`uvicorn` instalados
- `frontend/node_modules` instalado (`npm install` dentro de `frontend/`)
- `ngrok` instalado em `%LOCALAPPDATA%\ngrok\ngrok.exe` com authtoken configurado
  (`ngrok config add-authtoken <token>` — token gratuito em
  [dashboard.ngrok.com](https://dashboard.ngrok.com/get-started/your-authtoken))

Se algum desses faltar em outra máquina, rode antes:

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
cd frontend && npm install
```

## Subir tudo

Na raiz do projeto, dê duplo clique em **`iniciar-teste.bat`** (ou rode pelo
terminal). Ele abre 3 janelas:

1. **API** — FastAPI na porta `8000`
2. **Frontend** — Vite dev server na porta `5173`
3. **ngrok** — túnel público apontando só para o frontend

Ao final, abre automaticamente `http://127.0.0.1:4040` — o painel do ngrok,
onde fica a URL pública (algo como `https://xxxxx.ngrok-free.dev`). É esse
link que você compartilha para o teste.

> A primeira visita de quem não conhece o link vai ver uma tela de aviso do
> ngrok ("Visit Site") — normal do plano grátis, é só clicar em continuar.

## Como funciona (por que só 1 túnel)

O plano grátis do ngrok permite só 1 endpoint público por vez. Em vez de dois
túneis (API + frontend), o `frontend/vite.config.ts` faz *proxy* das rotas
`/auth`, `/kpis`, `/admin` e `/health` para `localhost:8000` — então só o
frontend precisa ficar exposto publicamente; a API continua só local.

Isso depende de:
- `frontend/.env` com `VITE_API_URL=` vazio (baseURL relativa)
- `frontend/vite.config.ts` com `server.proxy` configurado
- `server.allowedHosts` liberando `.ngrok-free.dev` / `.ngrok-free.app`

## Credenciais de teste

O login não tem senha fixa em texto — é gerada a cada execução do script de
seed e mostrada só no console. Para gerar (ou renovar) credenciais:

```bash
.venv\Scripts\python.exe scripts\seed_usuarios_and_produtos_saas.py
```

Isso imprime um login/senha de admin e um de cliente (tenant
`POSTO JAGUAR EIRELI`, com o produto "Análise Sell In" ativado). Rodar de
novo **reseta** essas duas senhas — não afeta os demais tenants.

## Encerrar

Feche as 3 janelas abertas pelo `.bat` (API, Frontend, ngrok). Fechar só a
janela do ngrok já derruba o link público; a API e o frontend continuam
acessíveis em `localhost`.

## Limitações do link ngrok

- Muda a cada reinício do túnel (domínio grátis não é fixo)
- Só funciona enquanto esta máquina estiver ligada e conectada
- Serve para teste pontual com poucas pessoas — para algo mais permanente ou
  compartilhado mais amplamente, ver a seção "Passo 5 — Deploy da API" e
  "Passo 6 — Frontend React + Tremor" no `CLAUDE.md` (Vercel + Render)
