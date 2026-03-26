import re
import pandas as pd
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.documento_fiscal import DocumentoFiscal
from app.models.itens_fiscal_c170 import ItemFiscal
from app.models.icms_c190 import IcmsC190
from app.models.produto import Produto
from app.models.inventario_h005 import InventarioH005
from app.models.inventario_h010 import InventarioH010
from app.models.estoque_k200 import EstoqueK200


class SilverProcessor:
    def __init__(self, session: Session, tenant_id: int):
        self.session = session
        self.tenant_id = tenant_id

    def _cast_decimal(self, valor) -> float:
        """
        Equivalente ao cast_decimal do Databricks —
        converte string para float tratando vírgula como separador decimal.
        """
        try:
            if valor is None or str(valor).strip() == '':
                return 0.0
            return float(str(valor).replace(',', '.'))
        except:
            return 0.0

    def _cast_data(self, valor) -> datetime:
        """
        Equivalente ao try_to_timestamp do Databricks —
        converte ddMMyyyy para datetime.
        """
        try:
            return datetime.strptime(str(valor).strip(), '%d%m%Y')
        except:
            return None

    def _parse_linhas(self, linhas_raw: list) -> dict:
        """
        Equivalente às células 3, 4 e 5 do Databricks:
        - divide cada linha por pipe
        - identifica o bloco
        - propaga CHV_DOC para as linhas filhas (C170, C190)
        """
        registros = {
            'c100': [],
            'c170': [],
            'c190': [],
            '0200': [],
            'loja': [],
            'h005': [],
            'h010': [],
            'k200': [],
        }

        chv_doc_atual = None
        dt_inv_atual = None

        for linha in linhas_raw:
            campos = linha.split('|')
            if len(campos) < 2:
                continue

            bloco = campos[1]

            # equivalente ao CHV_DOC_TEMP + window propagation do Databricks
            if bloco == 'C100' and len(campos) > 9:
                chv_doc_atual = campos[9]

            registros_bloco = {
                'campos': campos,
                'chv_doc': chv_doc_atual
            }

            if bloco == 'C100':
                registros['c100'].append(registros_bloco)
            elif bloco == 'C170':
                registros['c170'].append(registros_bloco)
            elif bloco == 'C190':
                registros['c190'].append(registros_bloco)
            elif bloco == '0200':
                registros['0200'].append(registros_bloco)
            elif bloco == '0000':
                registros['loja'].append(registros_bloco)
            elif bloco == 'H005' and len(campos) > 2:
                dt_inv_atual = campos[2]
                registros['h005'].append({'campos': campos})
            elif bloco == 'H010':
                registros['h010'].append({'campos': campos, 'dt_inv': dt_inv_atual})
            elif bloco == 'K200':
                registros['k200'].append({'campos': campos})

        return registros

    def _processar_c100(self, registros: list) -> int:
        """
        Equivalente à célula 6 do Databricks — extrai campos do C100.
        Upsert por tenant_id + chv_nfe.
        """
        criados = 0

        for reg in registros:
            c = reg['campos']
            chv = c[9] if len(c) > 9 else ''

            if not chv:
                continue

            existente = self.session.query(DocumentoFiscal).filter(
                DocumentoFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.chv_nfe == chv
            ).first()

            if existente:
                continue

            doc = DocumentoFiscal(
                tenant_id=self.tenant_id,
                chv_nfe=chv,
                ind_oper=c[2] if len(c) > 2 else '',
                ind_emit=c[3] if len(c) > 3 else '',
                cod_part=c[4] if len(c) > 4 else '',
                cod_mod=c[5] if len(c) > 5 else '',
                cod_sit=c[6] if len(c) > 6 else '',
                ser=c[7] if len(c) > 7 else '',
                num_doc=c[8] if len(c) > 8 else '',
                dt_doc=self._cast_data(c[10]) if len(c) > 10 else None,
                dt_e_s=self._cast_data(c[11]) if len(c) > 11 else None,
                vl_doc=self._cast_decimal(c[12]) if len(c) > 12 else 0.0,
                vl_desc=self._cast_decimal(c[14]) if len(c) > 14 else 0.0,
                vl_merc=self._cast_decimal(c[16]) if len(c) > 16 else 0.0,
                vl_bc_icms=self._cast_decimal(c[21]) if len(c) > 21 else 0.0,
                vl_icms=self._cast_decimal(c[22]) if len(c) > 22 else 0.0,
                vl_bc_icms_st=self._cast_decimal(c[23]) if len(c) > 23 else 0.0,
                vl_icms_st=self._cast_decimal(c[24]) if len(c) > 24 else 0.0,
                vl_pis=self._cast_decimal(c[26]) if len(c) > 26 else 0.0,
                vl_cofins=self._cast_decimal(c[27]) if len(c) > 27 else 0.0,
            )
            self.session.add(doc)
            criados += 1

        self.session.commit()
        return criados

    def _processar_c170(self, registros: list) -> int:
        """
        Equivalente à célula 7 do Databricks — extrai campos do C170.
        Upsert por tenant_id + chv_doc + num_item.
        """
        criados = 0

        for reg in registros:
            c = reg['campos']
            chv = reg['chv_doc']

            if not chv:
                continue

            existente = self.session.query(ItemFiscal).filter(
                ItemFiscal.tenant_id == self.tenant_id,
                ItemFiscal.chv_doc == chv,
                ItemFiscal.num_item == int(c[2]) if len(c) > 2 and c[2].isdigit() else 0
            ).first()

            if existente:
                continue

            # busca o documento pai para associar
            doc = self.session.query(DocumentoFiscal).filter(
                DocumentoFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.chv_nfe == chv
            ).first()

            item = ItemFiscal(
                tenant_id=self.tenant_id,
                chv_doc=chv,
                documento_id=doc.id if doc else None,
                num_item=int(c[2]) if len(c) > 2 and c[2].isdigit() else 0,
                cod_item=c[3] if len(c) > 3 else '',
                descr_compl=c[4] if len(c) > 4 else '',
                qtd=self._cast_decimal(c[5]) if len(c) > 5 else 0.0,
                unid=c[6] if len(c) > 6 else '',
                vl_item=self._cast_decimal(c[7]) if len(c) > 7 else 0.0,
                vl_desc=self._cast_decimal(c[8]) if len(c) > 8 else 0.0,
                cst_icms=c[10] if len(c) > 10 else '',
                cfop=c[11] if len(c) > 11 else '',
                vl_bc_icms=self._cast_decimal(c[13]) if len(c) > 13 else 0.0,
                aliq_icms=self._cast_decimal(c[14]) if len(c) > 14 else 0.0,
                vl_icms=self._cast_decimal(c[15]) if len(c) > 15 else 0.0,
                vl_pis=self._cast_decimal(c[30]) if len(c) > 30 else 0.0,
                vl_cofins=self._cast_decimal(c[36]) if len(c) > 36 else 0.0,
            )
            self.session.add(item)
            criados += 1

        self.session.commit()
        return criados

    def _processar_c190(self, registros: list) -> int:
        """
        Extrai campos do C190 — registro analítico de ICMS por CST/CFOP/alíquota.
        Upsert por tenant_id + chv_doc + cst_icms + cfop + aliq_icms.
        """
        criados = 0

        for reg in registros:
            c = reg['campos']
            chv = reg['chv_doc']

            if not chv:
                continue

            cst = c[2] if len(c) > 2 else ''
            cfop = c[3] if len(c) > 3 else ''
            aliq = c[4] if len(c) > 4 else ''

            existente = self.session.query(IcmsC190).filter(
                IcmsC190.tenant_id == self.tenant_id,
                IcmsC190.chv_doc == chv,
                IcmsC190.cst_icms == cst,
                IcmsC190.cfop == cfop,
                IcmsC190.aliq_icms == aliq,
            ).first()

            if existente:
                continue

            doc = self.session.query(DocumentoFiscal).filter(
                DocumentoFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.chv_nfe == chv
            ).first()

            registro = IcmsC190(
                tenant_id=self.tenant_id,
                chv_doc=chv,
                documento_id=doc.id if doc else None,
                cst_icms=cst,
                cfop=cfop,
                aliq_icms=aliq,
                vl_opr=self._cast_decimal(c[5]) if len(c) > 5 else 0.0,
                vl_bc_icms=self._cast_decimal(c[6]) if len(c) > 6 else 0.0,
                vl_icms=self._cast_decimal(c[7]) if len(c) > 7 else 0.0,
                vl_bc_icms_st=self._cast_decimal(c[8]) if len(c) > 8 else 0.0,
                vl_icms_st=self._cast_decimal(c[9]) if len(c) > 9 else 0.0,
                vl_red_bc=self._cast_decimal(c[10]) if len(c) > 10 else 0.0,
                vl_pis=self._cast_decimal(c[11]) if len(c) > 11 else 0.0,
                vl_cofins=self._cast_decimal(c[12]) if len(c) > 12 else 0.0,
                cod_obs=c[13] if len(c) > 13 else '',
            )
            self.session.add(registro)
            criados += 1

        self.session.commit()
        return criados

    def _processar_0200(self, registros: list) -> dict:
        """
        Equivalente à célula 9 do Databricks — extrai campos do 0200.
        Upsert por tenant_id + cod_item.
        """
        criados = 0
        atualizados = 0

        for reg in registros:
            c = reg['campos']
            cod = c[2] if len(c) > 2 else ''

            if not cod:
                continue

            existente = self.session.query(Produto).filter(
                Produto.tenant_id == self.tenant_id,
                Produto.cod_item == cod
            ).first()

            if existente:
                existente.descr_item = c[3] if len(c) > 3 else ''
                existente.cod_barra = c[4] if len(c) > 4 else ''
                existente.unid_inv = c[6] if len(c) > 6 else ''
                existente.tipo_item = c[7] if len(c) > 7 else ''
                existente.cod_ncm = c[8] if len(c) > 8 else ''
                existente.aliq_icms = self._cast_decimal(c[12]) if len(c) > 12 else 0.0
                existente.cest = c[13] if len(c) > 13 else ''
                atualizados += 1
            else:
                produto = Produto(
                    tenant_id=self.tenant_id,
                    cod_item=cod,
                    descr_item=c[3] if len(c) > 3 else '',
                    cod_barra=c[4] if len(c) > 4 else '',
                    unid_inv=c[6] if len(c) > 6 else '',
                    tipo_item=c[7] if len(c) > 7 else '',
                    cod_ncm=c[8] if len(c) > 8 else '',
                    aliq_icms=self._cast_decimal(c[12]) if len(c) > 12 else 0.0,
                    cest=c[13] if len(c) > 13 else '',
                )
                self.session.add(produto)
                criados += 1

        self.session.commit()
        return {"criados": criados, "atualizados": atualizados}

    def _processar_h005(self, registros: list) -> int:
        """
        Extrai campos do H005 — cabeçalho do inventário físico.
        Upsert por tenant_id + dt_inv + mot_inv.
        """
        criados = 0

        for reg in registros:
            c = reg['campos']
            dt_inv = self._cast_data(c[2]) if len(c) > 2 else None
            mot_inv = c[4] if len(c) > 4 else ''

            if not dt_inv:
                continue

            existente = self.session.query(InventarioH005).filter(
                InventarioH005.tenant_id == self.tenant_id,
                InventarioH005.dt_inv == dt_inv,
                InventarioH005.mot_inv == mot_inv,
            ).first()

            if existente:
                existente.vl_inv = self._cast_decimal(c[3]) if len(c) > 3 else 0.0
                continue

            registro = InventarioH005(
                tenant_id=self.tenant_id,
                dt_inv=dt_inv,
                vl_inv=self._cast_decimal(c[3]) if len(c) > 3 else 0.0,
                mot_inv=mot_inv,
            )
            self.session.add(registro)
            criados += 1

        self.session.commit()
        return criados

    def _processar_h010(self, registros: list) -> int:
        """
        Extrai campos do H010 — itens do inventário físico.
        Upsert por tenant_id + dt_inv + cod_item + ind_prop.
        Deve ser chamado após _processar_h005() (precisa do FK do pai).
        """
        criados = 0

        for reg in registros:
            c = reg['campos']
            dt_inv = self._cast_data(reg.get('dt_inv')) if reg.get('dt_inv') else None
            cod_item = c[2] if len(c) > 2 else ''
            ind_prop = c[7] if len(c) > 7 else '0'

            if not dt_inv or not cod_item:
                continue

            existente = self.session.query(InventarioH010).filter(
                InventarioH010.tenant_id == self.tenant_id,
                InventarioH010.dt_inv == dt_inv,
                InventarioH010.cod_item == cod_item,
                InventarioH010.ind_prop == ind_prop,
            ).first()

            if existente:
                existente.qtd = self._cast_decimal(c[4]) if len(c) > 4 else 0.0
                existente.vl_unit = self._cast_decimal(c[5]) if len(c) > 5 else 0.0
                existente.vl_item = self._cast_decimal(c[6]) if len(c) > 6 else 0.0
                continue

            pai = self.session.query(InventarioH005).filter(
                InventarioH005.tenant_id == self.tenant_id,
                InventarioH005.dt_inv == dt_inv,
            ).first()

            item = InventarioH010(
                tenant_id=self.tenant_id,
                inventario_id=pai.id if pai else None,
                dt_inv=dt_inv,
                cod_item=cod_item,
                unid=c[3] if len(c) > 3 else '',
                qtd=self._cast_decimal(c[4]) if len(c) > 4 else 0.0,
                vl_unit=self._cast_decimal(c[5]) if len(c) > 5 else 0.0,
                vl_item=self._cast_decimal(c[6]) if len(c) > 6 else 0.0,
                ind_prop=ind_prop,
                cod_part=c[8] if len(c) > 8 else '',
                txt_compl=c[9] if len(c) > 9 else '',
                cod_cta=c[10] if len(c) > 10 else '',
            )
            self.session.add(item)
            criados += 1

        self.session.commit()
        return criados

    def _processar_k200(self, registros: list) -> int:
        """
        Extrai campos do K200 — saldo de estoque por data.
        Upsert por tenant_id + dt_est + cod_item + ind_est.
        """
        criados = 0

        for reg in registros:
            c = reg['campos']
            dt_est = self._cast_data(c[2]) if len(c) > 2 else None
            cod_item = c[3] if len(c) > 3 else ''
            ind_est = c[5] if len(c) > 5 else '0'

            if not dt_est or not cod_item:
                continue

            existente = self.session.query(EstoqueK200).filter(
                EstoqueK200.tenant_id == self.tenant_id,
                EstoqueK200.dt_est == dt_est,
                EstoqueK200.cod_item == cod_item,
                EstoqueK200.ind_est == ind_est,
            ).first()

            if existente:
                existente.qt_est = self._cast_decimal(c[4]) if len(c) > 4 else 0.0
                continue

            saldo = EstoqueK200(
                tenant_id=self.tenant_id,
                dt_est=dt_est,
                cod_item=cod_item,
                qt_est=self._cast_decimal(c[4]) if len(c) > 4 else 0.0,
                ind_est=ind_est,
            )
            self.session.add(saldo)
            criados += 1

        self.session.commit()
        return criados

    def processar(self, file_path: str) -> dict:
        """
        Ponto de entrada — lê o efd_raw do banco e processa todas as tabelas.
        Equivalente ao fluxo completo do notebook silver.
        """
        from app.models.efd_raw import EfdRaw

        # lê as linhas do bronze — equivalente ao df_raw do Databricks
        linhas = (
            self.session.query(EfdRaw.conteudo_linha)
            .filter(
                EfdRaw.tenant_id == self.tenant_id,
                EfdRaw.file_path == file_path
            )
            .order_by(EfdRaw.num_linha)
            .all()
        )

        linhas_raw = [l.conteudo_linha for l in linhas]

        if not linhas_raw:
            return {"status": "erro", "motivo": "arquivo não encontrado no bronze"}

        # equivalente às células 3, 4 e 5
        registros = self._parse_linhas(linhas_raw)

        # equivalente às células 6, 7, 8 e 9
        docs = self._processar_c100(registros['c100'])
        itens = self._processar_c170(registros['c170'])
        c190 = self._processar_c190(registros['c190'])
        resultado_produtos = self._processar_0200(registros['0200'])
        h005 = self._processar_h005(registros['h005'])
        h010 = self._processar_h010(registros['h010'])
        k200 = self._processar_k200(registros['k200'])

        return {
            "status": "concluido",
            "documentos": docs,
            "itens": itens,
            "c190": c190,
            "produtos_criados": resultado_produtos['criados'],
            "produtos_atualizados": resultado_produtos['atualizados'],
            "h005": h005,
            "h010": h010,
            "k200": k200,
        }