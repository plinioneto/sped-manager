from sqlalchemy import func, and_
from app.models.documento_fiscal import DocumentoFiscal
from app.models.icms_c190 import IcmsC190
from app.models.itens_fiscal_c170 import ItemFiscal
from app.models.produto import Produto
from app.models.participante import Participante
from app.repositories.base_repo import BaseRepository


def _parse_aliq(aliq_str: str) -> float:
    """Converte alíquota string '18,00' para float 18.0."""
    if not aliq_str:
        return 0.0
    try:
        return float(str(aliq_str).replace(",", "."))
    except (ValueError, TypeError):
        return 0.0


class FiscalRepository(BaseRepository):

    # ------------------------------------------------------------------
    # Base queries
    # ------------------------------------------------------------------

    def _base_c190(self, ind_oper=None):
        """Query base: C190 joined to DocumentoFiscal, filtrado por tenant."""
        q = (
            self.session.query(IcmsC190)
            .join(DocumentoFiscal, IcmsC190.documento_id == DocumentoFiscal.id)
            .filter(IcmsC190.tenant_id == self.tenant_id)
        )
        if ind_oper is not None:
            q = q.filter(DocumentoFiscal.ind_oper == ind_oper)
        return q

    def _filtrar(self, q, ano=None, meses=None, cst_icms=None, cfop=None):
        """Aplica filtros padrão a queries que contêm C190 + DocumentoFiscal."""
        if ano:
            q = q.filter(func.strftime("%Y", DocumentoFiscal.dt_doc) == ano)
        if meses:
            q = q.filter(func.strftime("%m", DocumentoFiscal.dt_doc).in_(meses))
        if cst_icms:
            q = q.filter(IcmsC190.cst_icms.in_(cst_icms))
        if cfop:
            q = q.filter(IcmsC190.cfop.in_(cfop))
        return q

    def _filtrar_doc(self, q, ano=None, meses=None):
        """Aplica filtro de período a queries que só contêm DocumentoFiscal."""
        if ano:
            q = q.filter(func.strftime("%Y", DocumentoFiscal.dt_doc) == ano)
        if meses:
            q = q.filter(func.strftime("%m", DocumentoFiscal.dt_doc).in_(meses))
        return q

    # ------------------------------------------------------------------
    # Utilitários
    # ------------------------------------------------------------------

    def meses_disponiveis(self) -> list:
        rows = (
            self.session.query(
                func.strftime("%Y%m", DocumentoFiscal.dt_doc).label("mes")
            )
            .filter(DocumentoFiscal.tenant_id == self.tenant_id)
            .distinct()
            .order_by(func.strftime("%Y%m", DocumentoFiscal.dt_doc).desc())
            .all()
        )
        return [r.mes for r in rows if r.mes]

    def csts_disponiveis(self) -> list:
        rows = (
            self.session.query(IcmsC190.cst_icms)
            .filter(IcmsC190.tenant_id == self.tenant_id)
            .distinct()
            .order_by(IcmsC190.cst_icms)
            .all()
        )
        return [r.cst_icms for r in rows if r.cst_icms]

    def cfops_disponiveis(self) -> list:
        rows = (
            self.session.query(IcmsC190.cfop)
            .filter(IcmsC190.tenant_id == self.tenant_id)
            .distinct()
            .order_by(IcmsC190.cfop)
            .all()
        )
        return [r.cfop for r in rows if r.cfop]

    # ------------------------------------------------------------------
    # Visão Geral
    # ------------------------------------------------------------------

    def metricas_visao_geral(self, ano=None, meses=None, cst_icms=None, cfop=None) -> dict:
        # ICMS Débito (saídas)
        q_deb = self._filtrar(
            self.session.query(func.sum(IcmsC190.vl_icms))
            .join(DocumentoFiscal, IcmsC190.documento_id == DocumentoFiscal.id)
            .filter(IcmsC190.tenant_id == self.tenant_id, DocumentoFiscal.ind_oper == "1"),
            ano, meses, cst_icms, cfop,
        )
        icms_debito = q_deb.scalar() or 0.0

        # ICMS Crédito (entradas)
        q_cred = self._filtrar(
            self.session.query(func.sum(IcmsC190.vl_icms))
            .join(DocumentoFiscal, IcmsC190.documento_id == DocumentoFiscal.id)
            .filter(IcmsC190.tenant_id == self.tenant_id, DocumentoFiscal.ind_oper == "0"),
            ano, meses, cst_icms, cfop,
        )
        icms_credito = q_cred.scalar() or 0.0

        # Faturamento total (saídas)
        q_fat = self._filtrar(
            self.session.query(func.sum(IcmsC190.vl_opr))
            .join(DocumentoFiscal, IcmsC190.documento_id == DocumentoFiscal.id)
            .filter(IcmsC190.tenant_id == self.tenant_id, DocumentoFiscal.ind_oper == "1"),
            ano, meses, cst_icms, cfop,
        )
        faturamento_total = q_fat.scalar() or 0.0

        # Faturamento ST (CST 060)
        q_st = self._filtrar(
            self.session.query(func.sum(IcmsC190.vl_opr))
            .join(DocumentoFiscal, IcmsC190.documento_id == DocumentoFiscal.id)
            .filter(
                IcmsC190.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "1",
                IcmsC190.cst_icms == "060",
            ),
            ano, meses, None, cfop,  # não filtra por cst aqui
        )
        faturamento_st = q_st.scalar() or 0.0

        # Faturamento tributado (excl 060 e 040) para alíquota efetiva
        q_trib = self._filtrar(
            self.session.query(func.sum(IcmsC190.vl_opr))
            .join(DocumentoFiscal, IcmsC190.documento_id == DocumentoFiscal.id)
            .filter(
                IcmsC190.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "1",
                ~IcmsC190.cst_icms.in_(["060", "040", "041"]),
            ),
            ano, meses, cst_icms, cfop,
        )
        faturamento_tributado = q_trib.scalar() or 0.0

        # PIS + COFINS saída (via DocumentoFiscal)
        q_pis_cof = self._filtrar_doc(
            self.session.query(
                func.sum(DocumentoFiscal.vl_pis),
                func.sum(DocumentoFiscal.vl_cofins),
            )
            .filter(DocumentoFiscal.tenant_id == self.tenant_id, DocumentoFiscal.ind_oper == "1"),
            ano, meses,
        )
        pis_cofins = q_pis_cof.first()
        total_pis = (pis_cofins[0] or 0.0) if pis_cofins else 0.0
        total_cofins = (pis_cofins[1] or 0.0) if pis_cofins else 0.0

        icms_a_pagar = max(icms_debito - icms_credito, 0.0)
        pct_st = (faturamento_st / faturamento_total * 100) if faturamento_total else 0.0
        aliquota_efetiva = (icms_debito / faturamento_tributado * 100) if faturamento_tributado else 0.0

        return {
            "icms_debito": icms_debito,
            "icms_credito": icms_credito,
            "icms_a_pagar": icms_a_pagar,
            "faturamento_total": faturamento_total,
            "faturamento_st": faturamento_st,
            "pct_st": pct_st,
            "aliquota_efetiva": aliquota_efetiva,
            "total_pis": total_pis,
            "total_cofins": total_cofins,
        }

    def evolucao_mensal_tributos(self, ano=None, meses=None, cst_icms=None, cfop=None) -> list:
        """Retorna por mês: icms_debito, icms_credito, pis_saida, cofins_saida."""
        resultado = {}

        # ICMS via C190 (respeita filtros de CST/CFOP)
        for ind_oper, label_icms in [("1", "debito"), ("0", "credito")]:
            q = self._filtrar(
                self.session.query(
                    func.strftime("%Y%m", DocumentoFiscal.dt_doc).label("mes"),
                    func.sum(IcmsC190.vl_icms).label("icms"),
                )
                .join(DocumentoFiscal, IcmsC190.documento_id == DocumentoFiscal.id)
                .filter(IcmsC190.tenant_id == self.tenant_id, DocumentoFiscal.ind_oper == ind_oper),
                ano, meses, cst_icms, cfop,
            )
            rows = (
                q.group_by(func.strftime("%Y%m", DocumentoFiscal.dt_doc))
                .order_by(func.strftime("%Y%m", DocumentoFiscal.dt_doc))
                .all()
            )
            for r in rows:
                if r.mes not in resultado:
                    resultado[r.mes] = {
                        "mes": r.mes, "icms_debito": 0.0, "icms_credito": 0.0,
                        "pis_saida": 0.0, "cofins_saida": 0.0,
                    }
                resultado[r.mes][f"icms_{label_icms}"] = r.icms or 0.0

        # PIS/COFINS via DocumentoFiscal
        q_pis = self._filtrar_doc(
            self.session.query(
                func.strftime("%Y%m", DocumentoFiscal.dt_doc).label("mes"),
                func.sum(DocumentoFiscal.vl_pis).label("pis"),
                func.sum(DocumentoFiscal.vl_cofins).label("cofins"),
            )
            .filter(
                DocumentoFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "1",
                DocumentoFiscal.dt_doc.isnot(None),
            ),
            ano, meses,
        )
        for r in q_pis.group_by(func.strftime("%Y%m", DocumentoFiscal.dt_doc)).all():
            if r.mes not in resultado:
                resultado[r.mes] = {
                    "mes": r.mes, "icms_debito": 0.0, "icms_credito": 0.0,
                    "pis_saida": 0.0, "cofins_saida": 0.0,
                }
            resultado[r.mes]["pis_saida"] = r.pis or 0.0
            resultado[r.mes]["cofins_saida"] = r.cofins or 0.0

        return sorted(resultado.values(), key=lambda x: x["mes"])

    def composicao_tributaria(self, ano=None, meses=None, cst_icms=None, cfop=None) -> dict:
        """Totais para donut: ICMS Próprio, ICMS-ST, PIS, COFINS (saídas)."""
        q = self._filtrar(
            self.session.query(
                func.sum(IcmsC190.vl_icms).label("icms_proprio"),
                func.sum(IcmsC190.vl_icms_st).label("icms_st"),
            )
            .join(DocumentoFiscal, IcmsC190.documento_id == DocumentoFiscal.id)
            .filter(IcmsC190.tenant_id == self.tenant_id, DocumentoFiscal.ind_oper == "1"),
            ano, meses, cst_icms, cfop,
        )
        r = q.first()

        q_pis = self._filtrar_doc(
            self.session.query(
                func.sum(DocumentoFiscal.vl_pis),
                func.sum(DocumentoFiscal.vl_cofins),
            )
            .filter(DocumentoFiscal.tenant_id == self.tenant_id, DocumentoFiscal.ind_oper == "1"),
            ano, meses,
        )
        r_pis = q_pis.first()

        return {
            "ICMS Proprio": (r.icms_proprio or 0.0) if r else 0.0,
            "ICMS-ST": (r.icms_st or 0.0) if r else 0.0,
            "PIS": (r_pis[0] or 0.0) if r_pis else 0.0,
            "COFINS": (r_pis[1] or 0.0) if r_pis else 0.0,
        }

    # ------------------------------------------------------------------
    # ICMS
    # ------------------------------------------------------------------

    def distribuicao_por_cst(self, ano=None, meses=None, cst_icms=None, cfop=None) -> list:
        """Agrupa C190 saídas por CST: vl_opr, vl_icms, contagem."""
        q = self._filtrar(
            self.session.query(
                IcmsC190.cst_icms,
                func.sum(IcmsC190.vl_opr).label("vl_opr"),
                func.sum(IcmsC190.vl_icms).label("vl_icms"),
                func.sum(IcmsC190.vl_icms_st).label("vl_icms_st"),
                func.count(IcmsC190.id).label("qtd"),
            )
            .join(DocumentoFiscal, IcmsC190.documento_id == DocumentoFiscal.id)
            .filter(IcmsC190.tenant_id == self.tenant_id, DocumentoFiscal.ind_oper == "1"),
            ano, meses, cst_icms, cfop,
        )
        return (
            q.group_by(IcmsC190.cst_icms)
            .order_by(func.sum(IcmsC190.vl_opr).desc())
            .all()
        )

    def analise_por_aliquota(self, ano=None, meses=None, cst_icms=None, cfop=None) -> list:
        """Agrupa C190 saídas por alíquota (excl CST 060/040)."""
        q = self._filtrar(
            self.session.query(
                IcmsC190.aliq_icms,
                func.sum(IcmsC190.vl_opr).label("vl_opr"),
                func.sum(IcmsC190.vl_bc_icms).label("vl_bc_icms"),
                func.sum(IcmsC190.vl_icms).label("vl_icms"),
                func.count(IcmsC190.id).label("qtd"),
            )
            .join(DocumentoFiscal, IcmsC190.documento_id == DocumentoFiscal.id)
            .filter(
                IcmsC190.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "1",
                ~IcmsC190.cst_icms.in_(["060", "040", "041"]),
            ),
            ano, meses, cst_icms, cfop,
        )
        return (
            q.group_by(IcmsC190.aliq_icms)
            .order_by(func.sum(IcmsC190.vl_opr).desc())
            .all()
        )

    def detalhe_c190(self, ano=None, meses=None, cst_icms=None, cfop=None, ind_oper=None) -> list:
        """Lista C190 completo com dados do documento e participante."""
        q = (
            self.session.query(
                IcmsC190,
                DocumentoFiscal.dt_doc,
                DocumentoFiscal.num_doc,
                DocumentoFiscal.ind_oper,
                Participante.nome.label("nome_part"),
            )
            .join(DocumentoFiscal, IcmsC190.documento_id == DocumentoFiscal.id)
            .outerjoin(
                Participante,
                and_(
                    Participante.tenant_id == self.tenant_id,
                    Participante.cod_part == DocumentoFiscal.cod_part,
                ),
            )
            .filter(IcmsC190.tenant_id == self.tenant_id)
        )
        if ind_oper is not None:
            q = q.filter(DocumentoFiscal.ind_oper == ind_oper)
        q = self._filtrar(q, ano, meses, cst_icms, cfop)
        return q.order_by(DocumentoFiscal.dt_doc.desc()).limit(500).all()

    # ------------------------------------------------------------------
    # Substituição Tributária
    # ------------------------------------------------------------------

    def metricas_st(self, ano=None, meses=None) -> dict:
        """Métricas de ST: total operações, % faturamento, ST pago nas compras."""
        q_fat = self._filtrar_doc(
            self.session.query(func.sum(IcmsC190.vl_opr))
            .join(DocumentoFiscal, IcmsC190.documento_id == DocumentoFiscal.id)
            .filter(IcmsC190.tenant_id == self.tenant_id, DocumentoFiscal.ind_oper == "1"),
            ano, meses,
        )
        faturamento_total = q_fat.scalar() or 0.0

        q_st = self._filtrar_doc(
            self.session.query(func.sum(IcmsC190.vl_opr))
            .join(DocumentoFiscal, IcmsC190.documento_id == DocumentoFiscal.id)
            .filter(
                IcmsC190.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "1",
                IcmsC190.cst_icms == "060",
            ),
            ano, meses,
        )
        total_st_saida = q_st.scalar() or 0.0

        q_st_entrada = self._filtrar_doc(
            self.session.query(func.sum(DocumentoFiscal.vl_icms_st))
            .filter(
                DocumentoFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "0",
            ),
            ano, meses,
        )
        icms_st_compras = q_st_entrada.scalar() or 0.0

        pct_st = (total_st_saida / faturamento_total * 100) if faturamento_total else 0.0

        return {
            "total_st_saida": total_st_saida,
            "pct_st": pct_st,
            "icms_st_compras": icms_st_compras,
            "faturamento_total": faturamento_total,
        }

    def top_produtos_st_entrada(self, ano=None, meses=None, limit=20) -> list:
        """Top produtos com maior custo de ST nas compras (C170 CFOP 1403/2403)."""
        q = (
            self.session.query(
                ItemFiscal.cod_item,
                Produto.descr_item,
                func.sum(ItemFiscal.vl_item).label("vl_total"),
                func.sum(ItemFiscal.vl_icms).label("vl_icms"),
                func.count(ItemFiscal.id).label("qtd_itens"),
            )
            .join(DocumentoFiscal, ItemFiscal.documento_id == DocumentoFiscal.id)
            .outerjoin(
                Produto,
                and_(
                    Produto.tenant_id == self.tenant_id,
                    Produto.cod_item == ItemFiscal.cod_item,
                ),
            )
            .filter(
                ItemFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "0",
                ItemFiscal.cfop.in_(["1403", "2403"]),
            )
        )
        if ano:
            q = q.filter(func.strftime("%Y", DocumentoFiscal.dt_doc) == ano)
        if meses:
            q = q.filter(func.strftime("%m", DocumentoFiscal.dt_doc).in_(meses))
        return (
            q.group_by(ItemFiscal.cod_item, Produto.descr_item)
            .order_by(func.sum(ItemFiscal.vl_item).desc())
            .limit(limit)
            .all()
        )

    def evolucao_st_vs_proprio(self, ano=None, meses=None) -> list:
        """Mensal: valor operações ST (CST 060) vs ICMS Próprio (CST 000/020) nas saídas."""
        q = self._filtrar_doc(
            self.session.query(
                func.strftime("%Y%m", DocumentoFiscal.dt_doc).label("mes"),
                func.sum(
                    func.iif(IcmsC190.cst_icms == "060", IcmsC190.vl_opr, 0)
                ).label("vl_st"),
                func.sum(
                    func.iif(IcmsC190.cst_icms.in_(["000", "020"]), IcmsC190.vl_opr, 0)
                ).label("vl_proprio"),
            )
            .join(DocumentoFiscal, IcmsC190.documento_id == DocumentoFiscal.id)
            .filter(IcmsC190.tenant_id == self.tenant_id, DocumentoFiscal.ind_oper == "1"),
            ano, meses,
        )
        return (
            q.group_by(func.strftime("%Y%m", DocumentoFiscal.dt_doc))
            .order_by(func.strftime("%Y%m", DocumentoFiscal.dt_doc))
            .all()
        )

    # ------------------------------------------------------------------
    # PIS/COFINS
    # ------------------------------------------------------------------

    def metricas_pis_cofins(self, ano=None, meses=None) -> dict:
        """PIS/COFINS via DocumentoFiscal (C190 não tem dados confiáveis)."""
        result = {}
        for ind_oper, label in [("0", "entrada"), ("1", "saida")]:
            q = self._filtrar_doc(
                self.session.query(
                    func.sum(DocumentoFiscal.vl_pis),
                    func.sum(DocumentoFiscal.vl_cofins),
                )
                .filter(DocumentoFiscal.tenant_id == self.tenant_id, DocumentoFiscal.ind_oper == ind_oper),
                ano, meses,
            )
            r = q.first()
            result[f"pis_{label}"] = (r[0] or 0.0) if r else 0.0
            result[f"cofins_{label}"] = (r[1] or 0.0) if r else 0.0
        return result

    def evolucao_pis_cofins(self, ano=None, meses=None) -> list:
        """Evolução mensal PIS/COFINS via DocumentoFiscal."""
        resultado = {}
        for ind_oper, label in [("0", "entrada"), ("1", "saida")]:
            q = self._filtrar_doc(
                self.session.query(
                    func.strftime("%Y%m", DocumentoFiscal.dt_doc).label("mes"),
                    func.sum(DocumentoFiscal.vl_pis).label("pis"),
                    func.sum(DocumentoFiscal.vl_cofins).label("cofins"),
                )
                .filter(
                    DocumentoFiscal.tenant_id == self.tenant_id,
                    DocumentoFiscal.ind_oper == ind_oper,
                    DocumentoFiscal.dt_doc.isnot(None),
                ),
                ano, meses,
            )
            rows = (
                q.group_by(func.strftime("%Y%m", DocumentoFiscal.dt_doc))
                .order_by(func.strftime("%Y%m", DocumentoFiscal.dt_doc))
                .all()
            )
            for r in rows:
                if r.mes not in resultado:
                    resultado[r.mes] = {
                        "mes": r.mes,
                        "pis_entrada": 0.0, "cofins_entrada": 0.0,
                        "pis_saida": 0.0, "cofins_saida": 0.0,
                    }
                resultado[r.mes][f"pis_{label}"] = r.pis or 0.0
                resultado[r.mes][f"cofins_{label}"] = r.cofins or 0.0

        return sorted(resultado.values(), key=lambda x: x["mes"])

    # ------------------------------------------------------------------
    # Diagnóstico
    # ------------------------------------------------------------------

    def alertas_cst_inconsistente(self, ano=None, meses=None) -> list:
        """Itens com CST 000 mas CFOP de ST (1403/2403) — possível erro."""
        q = (
            self.session.query(
                ItemFiscal.cod_item,
                Produto.descr_item,
                ItemFiscal.cst_icms,
                ItemFiscal.cfop,
                func.count(ItemFiscal.id).label("qtd"),
                func.sum(ItemFiscal.vl_item).label("vl_total"),
            )
            .join(DocumentoFiscal, ItemFiscal.documento_id == DocumentoFiscal.id)
            .outerjoin(
                Produto,
                and_(
                    Produto.tenant_id == self.tenant_id,
                    Produto.cod_item == ItemFiscal.cod_item,
                ),
            )
            .filter(
                ItemFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "0",
                ItemFiscal.cst_icms == "000",
                ItemFiscal.cfop.in_(["1403", "2403"]),
            )
        )
        if ano:
            q = q.filter(func.strftime("%Y", DocumentoFiscal.dt_doc) == ano)
        if meses:
            q = q.filter(func.strftime("%m", DocumentoFiscal.dt_doc).in_(meses))
        return (
            q.group_by(ItemFiscal.cod_item, Produto.descr_item, ItemFiscal.cst_icms, ItemFiscal.cfop)
            .order_by(func.sum(ItemFiscal.vl_item).desc())
            .all()
        )

    def produtos_sem_cst(self, ano=None, meses=None) -> list:
        """Itens de entrada com CST vazio ou nulo."""
        q = (
            self.session.query(
                ItemFiscal.cod_item,
                Produto.descr_item,
                func.count(ItemFiscal.id).label("qtd"),
                func.sum(ItemFiscal.vl_item).label("vl_total"),
            )
            .join(DocumentoFiscal, ItemFiscal.documento_id == DocumentoFiscal.id)
            .outerjoin(
                Produto,
                and_(
                    Produto.tenant_id == self.tenant_id,
                    Produto.cod_item == ItemFiscal.cod_item,
                ),
            )
            .filter(
                ItemFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "0",
                (ItemFiscal.cst_icms.is_(None)) | (ItemFiscal.cst_icms == ""),
            )
        )
        if ano:
            q = q.filter(func.strftime("%Y", DocumentoFiscal.dt_doc) == ano)
        if meses:
            q = q.filter(func.strftime("%m", DocumentoFiscal.dt_doc).in_(meses))
        return (
            q.group_by(ItemFiscal.cod_item, Produto.descr_item)
            .order_by(func.sum(ItemFiscal.vl_item).desc())
            .all()
        )

    def concentracao_tributaria(self, ano=None, meses=None, limit=20) -> list:
        """Top produtos com maior carga tributária total nas entradas."""
        q = (
            self.session.query(
                ItemFiscal.cod_item,
                Produto.descr_item,
                func.sum(ItemFiscal.vl_icms).label("vl_icms"),
                func.sum(ItemFiscal.vl_pis).label("vl_pis"),
                func.sum(ItemFiscal.vl_cofins).label("vl_cofins"),
                (
                    func.sum(ItemFiscal.vl_icms)
                    + func.sum(ItemFiscal.vl_pis)
                    + func.sum(ItemFiscal.vl_cofins)
                ).label("carga_total"),
                func.sum(ItemFiscal.vl_item).label("vl_item_total"),
            )
            .join(DocumentoFiscal, ItemFiscal.documento_id == DocumentoFiscal.id)
            .outerjoin(
                Produto,
                and_(
                    Produto.tenant_id == self.tenant_id,
                    Produto.cod_item == ItemFiscal.cod_item,
                ),
            )
            .filter(
                ItemFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.ind_oper == "0",
            )
        )
        if ano:
            q = q.filter(func.strftime("%Y", DocumentoFiscal.dt_doc) == ano)
        if meses:
            q = q.filter(func.strftime("%m", DocumentoFiscal.dt_doc).in_(meses))
        return (
            q.group_by(ItemFiscal.cod_item, Produto.descr_item)
            .order_by(
                (
                    func.sum(ItemFiscal.vl_icms)
                    + func.sum(ItemFiscal.vl_pis)
                    + func.sum(ItemFiscal.vl_cofins)
                ).desc()
            )
            .limit(limit)
            .all()
        )
