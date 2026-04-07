import sys
sys.path.insert(0, '.')
from app.utils.db import SessionLocal
from app.models.produto import Produto

session = SessionLocal()

total = session.query(Produto).count()
com_cat = session.query(Produto).filter(Produto.categoria_id.isnot(None)).count()
sem_cat = session.query(Produto).filter(Produto.categoria_id.is_(None)).count()

print(f"Total de produtos : {total}")
print(f"Com categoria     : {com_cat} ({com_cat/total*100:.1f}%)")
print(f"Sem categoria     : {sem_cat} ({sem_cat/total*100:.1f}%)")

print()
print("=== Produtos SEM categoria (descricao_padrao) ===")
sem = session.query(Produto).filter(Produto.categoria_id.is_(None)).order_by(Produto.descricao_padrao).all()
for p in sem:
    print(f"  [{p.origem_padronizacao}] {p.descricao_padrao or p.descricao}")

session.close()
