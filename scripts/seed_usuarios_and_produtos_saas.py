"""
Cria/atualiza os dados iniciais de autenticação e do catálogo de produtos SaaS.

Idempotente — pode ser rodado quantas vezes for necessário.

Uso:
    python scripts/seed_usuarios_and_produtos_saas.py

O que faz:
1. Backfill de `usuarios` a partir de `lojas.senha_hash` (role='cliente'), preservando
   os hashes já existentes (sem precisar saber a senha em texto).
2. Cria/atualiza 1 usuário admin com senha de teste conhecida.
3. Reseta a senha do usuário do tenant informado (ADMIN_TESTE / TENANT_TESTE abaixo)
   para uma senha de teste conhecida, já que não temos o texto do hash atual.
4. Cria o produto SaaS "Análise Sell In" e ativa o entitlement para esse tenant.

Imprime no console as credenciais finais em texto puro — nunca são commitadas,
só o hash fica no banco.
"""

import sys
import secrets
import string
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.utils.db import get_db
from app.models.tenant import Tenant
from app.models.usuario import Usuario
from app.models.produto_saas import ProdutoSaas
from app.models.tenant_produto_saas import TenantProdutoSaas
from api.auth import hash_senha

ADMIN_LOGIN = "admin@spedmanager.com"
ADMIN_NOME = "Administrador"

TENANT_TESTE_NOME = "POSTO JAGUAR EIRELI"
PRODUTO_SLUG = "analise_sell_in"
PRODUTO_NOME = "Análise Sell In"
PRODUTO_DESCRICAO = "Análise de compras (sell-in): volume e valor de entrada por período."


def gerar_senha(tamanho: int = 14) -> str:
    alfabeto = string.ascii_letters + string.digits
    return "".join(secrets.choice(alfabeto) for _ in range(tamanho))


def main():
    credenciais = {}

    with get_db() as db:
        # 1. Backfill usuarios a partir de lojas com senha_hash já definido
        tenants_com_senha = db.query(Tenant).filter(Tenant.senha_hash.isnot(None)).all()
        for tenant in tenants_com_senha:
            existente = db.query(Usuario).filter(Usuario.tenant_id == tenant.id, Usuario.role == "cliente").first()
            if not existente:
                db.add(Usuario(
                    tenant_id=tenant.id,
                    login=tenant.cnpj,
                    senha_hash=tenant.senha_hash,
                    nome=tenant.nome,
                    role="cliente",
                    ativo=True,
                ))
        db.commit()

        # 2. Usuário admin com senha de teste conhecida
        admin = db.query(Usuario).filter(Usuario.login == ADMIN_LOGIN).first()
        senha_admin = gerar_senha()
        if not admin:
            admin = Usuario(login=ADMIN_LOGIN, nome=ADMIN_NOME, role="admin", tenant_id=None, ativo=True)
            db.add(admin)
        admin.senha_hash = hash_senha(senha_admin)
        db.commit()
        credenciais["admin"] = (ADMIN_LOGIN, senha_admin)

        # 3. Reset de senha do tenant de teste
        tenant_teste = db.query(Tenant).filter(Tenant.nome == TENANT_TESTE_NOME).first()
        if not tenant_teste:
            raise SystemExit(f"Tenant '{TENANT_TESTE_NOME}' não encontrado")

        usuario_teste = db.query(Usuario).filter(Usuario.tenant_id == tenant_teste.id, Usuario.role == "cliente").first()
        senha_teste = gerar_senha()
        if not usuario_teste:
            usuario_teste = Usuario(
                tenant_id=tenant_teste.id, login=tenant_teste.cnpj, nome=tenant_teste.nome,
                role="cliente", ativo=True,
            )
            db.add(usuario_teste)
        usuario_teste.senha_hash = hash_senha(senha_teste)
        db.commit()
        credenciais["cliente"] = (usuario_teste.login, senha_teste)

        # 4. Catálogo de produto SaaS + entitlement
        produto = db.query(ProdutoSaas).filter(ProdutoSaas.slug == PRODUTO_SLUG).first()
        if not produto:
            produto = ProdutoSaas(slug=PRODUTO_SLUG, nome=PRODUTO_NOME, descricao=PRODUTO_DESCRICAO, ativo=True)
            db.add(produto)
            db.commit()
            db.refresh(produto)

        entitlement = (
            db.query(TenantProdutoSaas)
            .filter(TenantProdutoSaas.tenant_id == tenant_teste.id, TenantProdutoSaas.produto_saas_id == produto.id)
            .first()
        )
        if not entitlement:
            entitlement = TenantProdutoSaas(tenant_id=tenant_teste.id, produto_saas_id=produto.id)
            db.add(entitlement)
        entitlement.ativo = True
        db.commit()

    print("\n=== Credenciais de teste ===")
    print(f"Admin   -> login: {credenciais['admin'][0]}   senha: {credenciais['admin'][1]}")
    print(f"Cliente -> login: {credenciais['cliente'][0]}   senha: {credenciais['cliente'][1]}  ({TENANT_TESTE_NOME})")
    print(f"Produto SaaS ativado: '{PRODUTO_NOME}' ({PRODUTO_SLUG}) para {TENANT_TESTE_NOME}")


if __name__ == "__main__":
    main()
