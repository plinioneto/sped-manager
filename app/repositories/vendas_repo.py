import re
from sqlalchemy import func, and_
from app.models.documento_fiscal import DocumentoFiscal
from app.utils.sql_compat import sf_yearmonth, sf_year, sf_month, sf_dow
from app.models.icms_c190 import IcmsC190
from app.models.itens_fiscal_c170 import ItemFiscal
from app.models.produto import Produto
from app.models.participante import Participante
from app.models.categoria import Departamento
from app.repositories.base_repo import BaseRepository

# SQLite strftime('%w'): 0=Dom, 1=Seg, 2=Ter, 3=Qua, 4=Qui, 5=Sex, 6=Sáb
DIA_SEMANA_MAP = {
    "Dom": "0", "Seg": "1", "Ter": "2", "Qua": "3",
    "Qui": "4", "Sex": "5", "Sáb": "6",
}


def _normalizar_cnpj(valor: str) -> str:
    return re.sub(r"\D", "", valor)


class VendasRepository(BaseRepository):

    def _base_saida(self):
        return self.session.query(DocumentoFiscal).filter(
            DocumentoFiscal.tenant_id == self.tenant_id,
            DocumentoFiscal.ind_oper == "1",
            DocumentoFiscal.dt_doc.isnot(None),
        )

    def _filtrar(self, q, ano=None, meses=None, dias_semana=None):
        if ano:
            q = q.filter(sf_year(DocumentoFiscal.dt_doc) == ano)
        if meses:
            q = q.filter(sf_month(DocumentoFiscal.dt_doc).in_(meses))
        if dias_semana:
            codigos = [DIA_SEMANA_MAP[d] for d in dias_semana if d in DIA_SEMANA_MAP]
            if codigos:
                q = q.filter(sf_dow(DocumentoFiscal.dt_doc).in_(codigos))
        return q

    def _filtrar_c190(self, q, ano=None, meses=None, dias_semana=None):
        if ano:
            q = q.filter(sf_year(DocumentoFiscal.dt_doc) == ano)
        if meses:
            q = q.filter(sf_month(DocumentoFiscal.dt_doc).in_(meses))
        if dias_semana:
            codigos = [DIA_SEMANA_MAP[d] for d in dias_semana if d in DIA_SEMANA_MAP]
            if codigos:
                q = q.filter(sf_dow(DocumentoFiscal.dt_doc).in_(codigos))
        return q

    # ------------------------------------------------------------------
    # Utilitários
    # ------------------------------------------------------------------

    def meses_disponiveis(self) -> list:
        rows = (
            self.session.query(
                sf_yearmonth(DocumentoFiscal.dt_doc).label("mes")
            )
            .filter(
                DocumentoFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "1",
                DocumentoFiscal.dt_doc.isnot(None),
            )
            .distinct()
            .order_by(sf_yearmonth(DocumentoFiscal.dt_doc).desc())
            .all()
        )
        return [r.mes for r in rows if r.mes]

    # ------------------------------------------------------------------
    # Métricas globais
    # ------------------------------------------------------------------

    def metricas_globais(self, ano=None, meses=None, dias_semana=None,
                         departamento_id=None, grupo_id=None, categoria_id=None) -> dict:
        base = self._filtrar(self._base_saida(), ano, meses, dias_semana)
        base = self._filtro_hierarquia_via_doc(base, departamento_id, grupo_id, categoria_id)

        fat = base.with_entities(func.sum(DocumentoFiscal.vl_doc)).scalar() or 0.0
        notas = base.with_entities(func.count(DocumentoFiscal.id)).scalar() or 0
        ticket = fat / notas if notas else 0.0
        b2b = (
            base.filter(DocumentoFiscal.cod_part.isnot(None))
            .with_entities(func.count(DocumentoFiscal.cod_part.distinct()))
            .scalar() or 0
        )

        # Deltas (só quando mês único selecionado)
        crescimento_pct = None
        delta_fat = delta_notas = delta_ticket = None
        if ano and meses and len(meses) == 1:
            yyyymm = ano + meses[0]
            meses_disp = self.meses_disponiveis()
            idx = meses_disp.index(yyyymm) if yyyymm in meses_disp else -1
            if idx >= 0 and idx + 1 < len(meses_disp):
                mes_ant = meses_disp[idx + 1]
                ano_ant, mes_num_ant = mes_ant[:4], mes_ant[4:]
                base_ant = self._filtrar(self._base_saida(), ano_ant, [mes_num_ant], dias_semana)
                base_ant = self._filtro_hierarquia_via_doc(base_ant, departamento_id, grupo_id, categoria_id)
                fat_ant = base_ant.with_entities(func.sum(DocumentoFiscal.vl_doc)).scalar() or 0.0
                notas_ant = base_ant.with_entities(func.count(DocumentoFiscal.id)).scalar() or 0
                ticket_ant = fat_ant / notas_ant if notas_ant else 0.0
                if fat_ant:
                    crescimento_pct = (fat - fat_ant) / fat_ant * 100
                delta_fat = fat - fat_ant
                delta_notas = notas - notas_ant
                delta_ticket = ticket - ticket_ant

        dias_com_vendas = (
            base.with_entities(
                func.count(func.distinct(func.date(DocumentoFiscal.dt_doc)))
            ).scalar() or 0
        )
        fat_por_dia = fat / dias_com_vendas if dias_com_vendas else 0.0

        return {
            "faturamento": fat,
            "total_notas": notas,
            "ticket_medio": ticket,
            "crescimento_pct": crescimento_pct,
            "total_b2b": b2b,
            "delta_fat": delta_fat,
            "delta_notas": delta_notas,
            "delta_ticket": delta_ticket,
            "dias_com_vendas": dias_com_vendas,
            "fat_por_dia": fat_por_dia,
        }

    # ------------------------------------------------------------------
    # Visão Geral
    # ------------------------------------------------------------------

    def evolucao_mensal(self, dias_semana=None,
                        departamento_id=None, grupo_id=None, categoria_id=None) -> list:
        """Série mensal completa (sem filtro de período)."""
        q = self._filtrar(self._base_saida(), ano=None, meses=None, dias_semana=dias_semana)
        q = self._filtro_hierarquia_via_doc(q, departamento_id, grupo_id, categoria_id)
        q = q.with_entities(
            sf_yearmonth(DocumentoFiscal.dt_doc).label("mes"),
            func.sum(DocumentoFiscal.vl_doc).label("faturamento"),
            func.count(DocumentoFiscal.id).label("total_notas"),
        )
        rows = (
            q.group_by(sf_yearmonth(DocumentoFiscal.dt_doc))
            .order_by(sf_yearmonth(DocumentoFiscal.dt_doc))
            .all()
        )
        result = []
        for r in rows:
            ticket = r.faturamento / r.total_notas if r.total_notas else 0.0
            result.append({
                "mes": r.mes,
                "faturamento": r.faturamento or 0.0,
                "total_notas": r.total_notas or 0,
                "ticket_medio": ticket,
            })
        return result

    # ------------------------------------------------------------------
    # Ritmo de Vendas
    # ------------------------------------------------------------------

    def faturamento_por_dia_semana(self, ano=None, meses=None, dias_semana=None) -> list:
        q = self._filtrar(self._base_saida(), ano, meses, dias_semana)
        q = q.with_entities(
            sf_dow(DocumentoFiscal.dt_doc).label("dia_semana"),
            func.sum(DocumentoFiscal.vl_doc).label("faturamento"),
            func.count(DocumentoFiscal.id).label("total_notas"),
        )
        rows = (
            q.group_by(sf_dow(DocumentoFiscal.dt_doc))
            .order_by(sf_dow(DocumentoFiscal.dt_doc))
            .all()
        )
        result = []
        for r in rows:
            ticket = r.faturamento / r.total_notas if r.total_notas else 0.0
            result.append({
                "dia_semana": r.dia_semana,
                "faturamento": r.faturamento or 0.0,
                "total_notas": r.total_notas or 0,
                "ticket_medio": ticket,
            })
        return result

    def heatmap_dia_mes(self) -> list:
        """Série histórica: faturamento por (mes, dia_semana). Sem filtros."""
        q = self._base_saida().with_entities(
            sf_yearmonth(DocumentoFiscal.dt_doc).label("mes"),
            sf_dow(DocumentoFiscal.dt_doc).label("dia_semana"),
            func.sum(DocumentoFiscal.vl_doc).label("faturamento"),
        )
        rows = (
            q.group_by(
                sf_yearmonth(DocumentoFiscal.dt_doc),
                sf_dow(DocumentoFiscal.dt_doc),
            )
            .order_by(sf_yearmonth(DocumentoFiscal.dt_doc))
            .all()
        )
        return [
            {"mes": r.mes, "dia_semana": r.dia_semana, "faturamento": r.faturamento or 0.0}
            for r in rows
        ]

    def distribuicao_ticket(self, ano=None, meses=None, dias_semana=None) -> dict:
        """Contagem de notas por faixa de valor."""
        base = self._filtrar(self._base_saida(), ano, meses, dias_semana)
        faixas = {
            "Até R$25": 0,
            "R$25–50": 0,
            "R$50–100": 0,
            "R$100–200": 0,
            "Acima de R$200": 0,
        }
        notas = base.with_entities(DocumentoFiscal.vl_doc).all()
        for (vl,) in notas:
            v = vl or 0.0
            if v <= 25:
                faixas["Até R$25"] += 1
            elif v <= 50:
                faixas["R$25–50"] += 1
            elif v <= 100:
                faixas["R$50–100"] += 1
            elif v <= 200:
                faixas["R$100–200"] += 1
            else:
                faixas["Acima de R$200"] += 1
        return faixas

    # ------------------------------------------------------------------
    # Mix Comercial (via C190)
    # ------------------------------------------------------------------

    def _base_c190_saida(self):
        return (
            self.session.query(IcmsC190)
            .join(DocumentoFiscal, IcmsC190.documento_id == DocumentoFiscal.id)
            .filter(
                IcmsC190.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "1",
                DocumentoFiscal.dt_doc.isnot(None),
            )
        )

    def distribuicao_cfop(self, ano=None, meses=None, dias_semana=None) -> list:
        q = self._filtrar_c190(self._base_c190_saida(), ano, meses, dias_semana)
        q = q.with_entities(
            IcmsC190.cfop,
            func.sum(IcmsC190.vl_opr).label("vl_opr"),
            func.count(IcmsC190.id).label("qtd"),
        )
        return (
            q.group_by(IcmsC190.cfop)
            .order_by(func.sum(IcmsC190.vl_opr).desc())
            .all()
        )

    def distribuicao_cst(self, ano=None, meses=None, dias_semana=None) -> list:
        q = self._filtrar_c190(self._base_c190_saida(), ano, meses, dias_semana)
        q = q.with_entities(
            IcmsC190.cst_icms,
            func.sum(IcmsC190.vl_opr).label("vl_opr"),
            func.count(IcmsC190.id).label("qtd"),
        )
        return (
            q.group_by(IcmsC190.cst_icms)
            .order_by(func.sum(IcmsC190.vl_opr).desc())
            .all()
        )

    def evolucao_cfop_mensal(self, cfops_top=3) -> list:
        """Série mensal para os top N CFOPs por valor total."""
        top_q = (
            self._base_c190_saida()
            .with_entities(IcmsC190.cfop)
            .group_by(IcmsC190.cfop)
            .order_by(func.sum(IcmsC190.vl_opr).desc())
            .limit(cfops_top)
            .all()
        )
        top_cfops = [r[0] for r in top_q if r[0]]
        if not top_cfops:
            return []

        q = (
            self._base_c190_saida()
            .filter(IcmsC190.cfop.in_(top_cfops))
            .with_entities(
                sf_yearmonth(DocumentoFiscal.dt_doc).label("mes"),
                IcmsC190.cfop,
                func.sum(IcmsC190.vl_opr).label("vl_opr"),
            )
        )
        rows = (
            q.group_by(
                sf_yearmonth(DocumentoFiscal.dt_doc),
                IcmsC190.cfop,
            )
            .order_by(sf_yearmonth(DocumentoFiscal.dt_doc))
            .all()
        )
        return [{"mes": r.mes, "cfop": r.cfop, "vl_opr": r.vl_opr or 0.0} for r in rows]

    # ------------------------------------------------------------------
    # Clientes B2B
    # ------------------------------------------------------------------

    def ranking_clientes(self, ano=None, meses=None, dias_semana=None) -> list:
        q = (
            self.session.query(
                DocumentoFiscal.cod_part,
                Participante.nome.label("nome_part"),
                Participante.cnpj.label("cnpj_part"),
                func.sum(DocumentoFiscal.vl_doc).label("fat_total"),
                func.count(DocumentoFiscal.id).label("qtd_notas"),
                func.max(DocumentoFiscal.dt_doc).label("ultima_nota"),
            )
            .outerjoin(
                Participante,
                and_(
                    Participante.tenant_id == self.tenant_id,
                    Participante.cod_part == DocumentoFiscal.cod_part,
                ),
            )
            .filter(
                DocumentoFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "1",
                DocumentoFiscal.cod_part.isnot(None),
                DocumentoFiscal.dt_doc.isnot(None),
            )
        )
        q = self._filtrar(q, ano, meses, dias_semana)
        rows = (
            q.group_by(DocumentoFiscal.cod_part, Participante.nome, Participante.cnpj)
            .order_by(func.sum(DocumentoFiscal.vl_doc).desc())
            .all()
        )
        result = []
        for r in rows:
            ticket = r.fat_total / r.qtd_notas if r.qtd_notas else 0.0
            result.append({
                "cod_part": r.cod_part,
                "nome_part": r.nome_part or r.cod_part,
                "cnpj_part": r.cnpj_part or "—",
                "fat_total": r.fat_total or 0.0,
                "qtd_notas": r.qtd_notas or 0,
                "ticket_medio": ticket,
                "ultima_nota": r.ultima_nota,
            })
        return result

    def evolucao_top_clientes(self, limit=5) -> list:
        """Série mensal dos top N clientes por faturamento."""
        top_q = (
            self.session.query(DocumentoFiscal.cod_part)
            .filter(
                DocumentoFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "1",
                DocumentoFiscal.cod_part.isnot(None),
                DocumentoFiscal.dt_doc.isnot(None),
            )
            .group_by(DocumentoFiscal.cod_part)
            .order_by(func.sum(DocumentoFiscal.vl_doc).desc())
            .limit(limit)
            .all()
        )
        top_clientes = [r[0] for r in top_q]
        if not top_clientes:
            return []

        q = (
            self.session.query(
                sf_yearmonth(DocumentoFiscal.dt_doc).label("mes"),
                DocumentoFiscal.cod_part,
                Participante.nome.label("nome_part"),
                func.sum(DocumentoFiscal.vl_doc).label("fat_total"),
            )
            .outerjoin(
                Participante,
                and_(
                    Participante.tenant_id == self.tenant_id,
                    Participante.cod_part == DocumentoFiscal.cod_part,
                ),
            )
            .filter(
                DocumentoFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "1",
                DocumentoFiscal.cod_part.in_(top_clientes),
                DocumentoFiscal.dt_doc.isnot(None),
            )
        )
        rows = (
            q.group_by(
                sf_yearmonth(DocumentoFiscal.dt_doc),
                DocumentoFiscal.cod_part,
                Participante.nome,
            )
            .order_by(sf_yearmonth(DocumentoFiscal.dt_doc))
            .all()
        )
        return [
            {
                "mes": r.mes,
                "cod_part": r.cod_part,
                "nome_part": r.nome_part or r.cod_part,
                "fat_total": r.fat_total or 0.0,
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Composição por hierarquia
    # ------------------------------------------------------------------

    def composicao_por_departamento(self, ano=None, meses=None, dias_semana=None) -> list:
        """Faturamento por departamento via C190 (saídas) quando há itens C170,
        senão retorna lista vazia (supermercados não emitem C170 de saída)."""
        q = (
            self.session.query(
                func.coalesce(Departamento.descricao, "Não classificado").label("departamento"),
                func.sum(ItemFiscal.vl_item).label("valor"),
            )
            .join(DocumentoFiscal, ItemFiscal.documento_id == DocumentoFiscal.id)
            .outerjoin(
                Produto,
                (Produto.tenant_id == self.tenant_id)
                & (Produto.cod_item == ItemFiscal.cod_item),
            )
            .outerjoin(Departamento, Departamento.id == Produto.departamento_id)
            .filter(
                ItemFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "1",
                DocumentoFiscal.dt_doc.isnot(None),
            )
        )
        q = self._filtrar(q, ano, meses, dias_semana)
        rows = (
            q.group_by(func.coalesce(Departamento.descricao, "Não classificado"))
            .order_by(func.sum(ItemFiscal.vl_item).desc())
            .all()
        )
        return [{"departamento": r.departamento, "valor": r.valor or 0.0} for r in rows]

    # ------------------------------------------------------------------
    # Notas de venda
    # ------------------------------------------------------------------

    def listar_notas(self, ano=None, meses=None, num_nota=None, cliente=None) -> list:
        q = (
            self.session.query(
                DocumentoFiscal,
                Participante.nome.label("nome_part"),
            )
            .outerjoin(
                Participante,
                and_(
                    Participante.tenant_id == self.tenant_id,
                    Participante.cod_part == DocumentoFiscal.cod_part,
                ),
            )
            .filter(
                DocumentoFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "1",
                DocumentoFiscal.dt_doc.isnot(None),
            )
        )
        if ano:
            q = q.filter(sf_year(DocumentoFiscal.dt_doc) == ano)
        if meses:
            q = q.filter(sf_month(DocumentoFiscal.dt_doc).in_(meses))
        if num_nota:
            q = q.filter(DocumentoFiscal.num_doc.ilike(f"%{num_nota}%"))
        if cliente:
            cnpj_norm = _normalizar_cnpj(cliente)
            termo = f"%{cliente}%"
            subq = (
                self.session.query(Participante.cod_part)
                .filter(Participante.tenant_id == self.tenant_id)
            )
            if cnpj_norm:
                subq = subq.filter(
                    Participante.nome.ilike(termo)
                    | Participante.cnpj.ilike(f"%{cnpj_norm}%")
                )
            else:
                subq = subq.filter(Participante.nome.ilike(termo))
            subq = subq.subquery().select()
            if cnpj_norm:
                q = q.filter(
                    DocumentoFiscal.cod_part.ilike(f"%{cnpj_norm}%")
                    | DocumentoFiscal.cod_part.in_(subq)
                )
            else:
                q = q.filter(DocumentoFiscal.cod_part.in_(subq))
        return q.order_by(DocumentoFiscal.dt_doc.desc()).limit(500).all()
