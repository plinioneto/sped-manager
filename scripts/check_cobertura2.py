import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '.')
from app.utils.db import SessionLocal
from app.models.produto import Produto
from sqlalchemy import func

session = SessionLocal()

total = session.query(Produto).count()
com_cat   = session.query(Produto).filter(Produto.categoria_id.isnot(None)).count()
so_grupo  = session.query(Produto).filter(Produto.categoria_id.is_(None), Produto.grupo_id.isnot(None)).count()
nada      = session.query(Produto).filter(Produto.categoria_id.is_(None), Produto.grupo_id.is_(None)).count()

print(f"Total de produtos        : {total}")
print(f"Com categoria (nivel 3)  : {com_cat}  ({com_cat/total*100:.1f}%)")
print(f"So grupo (nivel 2)       : {so_grupo}  ({so_grupo/total*100:.1f}%)")
print(f"Sem nada (nivel 0)       : {nada}  ({nada/total*100:.1f}%)")
print(f"Cobertos (cat ou grupo)  : {com_cat+so_grupo}  ({(com_cat+so_grupo)/total*100:.1f}%)")

print()
print("=== Primeiros tokens dos produtos SEM NADA (sem grupo nem categoria) ===")
sem_nada = (
    session.query(Produto.descricao_padrao)
    .filter(Produto.categoria_id.is_(None), Produto.grupo_id.is_(None))
    .all()
)
from collections import Counter
primeiros = Counter()
for (desc,) in sem_nada:
    if desc:
        primeiros[desc.split()[0]] += 1

print(f"Total sem nada: {len(sem_nada)}")
for token, cnt in primeiros.most_common(40):
    print(f"  {token:30s}: {cnt}")

session.close()
