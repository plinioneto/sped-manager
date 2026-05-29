"""
Popula o banco de produção (Supabase) com:
  1. Departamentos / Grupos / Categorias  (de categorias.db)
  2. Fabricantes e Marcas                 (via seed_fabricantes_marcas)
  3. Tenants do banco local               (de sped_manager.db)

Uso:
    python scripts/seed_supabase.py
"""

import os
import sys
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv()

from app.utils.db import get_db, engine
from app.models.base import Base
import app.models  # noqa
from app.models.categoria import Departamento, Grupo, Categoria
from app.models.tenant import Tenant


# ---------------------------------------------------------------------------
# 1. Hierarquia de categorias
# ---------------------------------------------------------------------------

def seed_categorias():
    cat_db = os.path.join(ROOT, "categorias.db")
    if not os.path.exists(cat_db):
        print("AVISO: categorias.db não encontrado — pulando hierarquia.")
        return

    src = sqlite3.connect(cat_db)
    cur = src.cursor()

    depts  = cur.execute("SELECT id, description FROM departments").fetchall()
    groups = cur.execute("SELECT id, description, department_id FROM groups").fetchall()
    cats   = cur.execute("SELECT id, description, group_id FROM categories").fetchall()
    src.close()

    with get_db() as db:
        existing_depts = {d.descricao for d in db.query(Departamento).all()}
        for (eid, desc) in depts:
            if desc not in existing_depts:
                db.add(Departamento(id=eid, descricao=desc))
        db.flush()

        existing_groups = {(g.departamento_id, g.descricao) for g in db.query(Grupo).all()}
        for (eid, desc, dept_id) in groups:
            if (dept_id, desc) not in existing_groups:
                db.add(Grupo(id=eid, descricao=desc, departamento_id=dept_id))
        db.flush()

        existing_cats = {(c.grupo_id, c.descricao) for c in db.query(Categoria).all()}
        for (eid, desc, group_id) in cats:
            if (group_id, desc) not in existing_cats:
                db.add(Categoria(id=eid, descricao=desc, grupo_id=group_id))
        db.commit()

    print(f"  Categorias: {len(depts)} departamentos, {len(groups)} grupos, {len(cats)} categorias")


# ---------------------------------------------------------------------------
# 2. Fabricantes e Marcas
# ---------------------------------------------------------------------------

def seed_fab_marcas():
    from scripts.seed_fabricantes_marcas import main as seed_main
    print("  Fabricantes e Marcas...")
    seed_main()


# ---------------------------------------------------------------------------
# 3. Tenants do banco local
# ---------------------------------------------------------------------------

def seed_tenants():
    local_db = os.path.join(ROOT, "sped_manager.db")
    if not os.path.exists(local_db):
        print("AVISO: sped_manager.db não encontrado — pulando tenants.")
        return

    src = sqlite3.connect(local_db)
    cur = src.cursor()
    tenants = cur.execute(
        "SELECT nome, cnpj, ativo, senha_hash, codigo_acesso FROM tenants"
    ).fetchall()
    src.close()

    with get_db() as db:
        existentes = {t.cnpj for t in db.query(Tenant).all()}
        novos = 0
        for (nome, cnpj, ativo, senha_hash, codigo_acesso) in tenants:
            if cnpj not in existentes:
                db.add(Tenant(
                    nome=nome,
                    cnpj=cnpj,
                    ativo=bool(ativo),
                    senha_hash=senha_hash,
                    codigo_acesso=codigo_acesso,
                ))
                novos += 1
        db.commit()

    print(f"  Tenants: {novos} criados de {len(tenants)} encontrados no banco local")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== Seed Supabase ===")
    print("1. Hierarquia de categorias...")
    seed_categorias()
    print("2. Fabricantes e Marcas...")
    seed_fab_marcas()
    print("3. Tenants...")
    seed_tenants()
    print("Concluído.")
