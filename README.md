# SPED Manager

Sistema de gestão fiscal para supermercados baseado em arquivos EFD (SPED Fiscal) e XML NFC-e/NF-e.

Contexto completo, stack e roadmap: veja [`CLAUDE.md`](CLAUDE.md).

## Setup rápido

Guia detalhado de instalação, variáveis de ambiente e fluxo de trabalho em equipe: [`docs/guia-de-desenvolvimento.md`](docs/guia-de-desenvolvimento.md).

```bash
git clone https://github.com/plinioneto/sped-manager.git
cd sped-manager
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env          # preencher com as credenciais compartilhadas
alembic upgrade head
```

Rodar a API:

```bash
uvicorn api.main:app --reload --port 8000
```

Rodar o Streamlit (legado):

```bash
streamlit run app/main.py
```
