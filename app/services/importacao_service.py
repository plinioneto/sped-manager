import pandas as pd
from sqlalchemy.orm import Session
from app.models.documento_fiscal import DocumentoFiscal
from app.models.itens_fiscal_c170 import ItemFiscal
from app.models.produto import Produto
from datetime import datetime

class ImportacaoService:
    def __init__(self, session: Session, tenant_id: int):
        self.session = session
        self.tenant_id = tenant_id

    def _parse_data(self, valor):
        try:
            return pd.to_datetime(valor).to_pydatetime()
        except:
            return None

    def _parse_float(self, valor):
        try:
            return float(str(valor).replace(',', '.'))
        except:
            return 0.0

    def importar_produtos(self, df: pd.DataFrame) -> int:
        count = 0
        for _, row in df.iterrows():
            # verifica se produto já existe
            existente = self.session.query(Produto).filter(
                Produto.tenant_id == self.tenant_id,
                Produto.cod_item == str(row.get('COD_ITEM', ''))
            ).first()

            if not existente:
                produto = Produto(
                    tenant_id=self.tenant_id,
                    cod_item=str(row.get('COD_ITEM', '')),
                    descr_item=str(row.get('DESCR_ITEM', '')),
                    cod_barra=str(row.get('COD_BARRA', '')),
                    unid_inv=str(row.get('UNID_INV', '')),
                    tipo_item=str(row.get('TIPO_ITEM', '')),
                    cod_ncm=str(row.get('COD_NCM', '')),
                    cest=str(row.get('CEST', '')),
                    aliq_icms=self._parse_float(row.get('ALIQ_ICMS', 0))
                )
                self.session.add(produto)
                count += 1

        self.session.commit()
        return count

    def importar_documentos(self, df_c100: pd.DataFrame, df_c170: pd.DataFrame) -> int:
        count = 0
        for _, row in df_c100.iterrows():
            chv = str(row.get('CHV_NFE', ''))

            # verifica se documento já existe
            existente = self.session.query(DocumentoFiscal).filter(
                DocumentoFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.chv_nfe == chv
            ).first()

            if not existente:
                doc = DocumentoFiscal(
                    tenant_id=self.tenant_id,
                    chv_nfe=chv,
                    ind_oper=str(row.get('IND_OPER', '')),
                    ind_emit=str(row.get('IND_EMIT', '')),
                    cod_part=str(row.get('COD_PART', '')),
                    cod_mod=str(row.get('COD_MOD', '')),
                    cod_sit=str(row.get('COD_SIT', '')),
                    ser=str(row.get('SER', '')),
                    num_doc=str(row.get('NUM_DOC', '')),
                    dt_doc=self._parse_data(row.get('DT_DOC')),
                    dt_e_s=self._parse_data(row.get('DT_E_S')),
                    vl_doc=self._parse_float(row.get('VL_DOC', 0)),
                    vl_desc=self._parse_float(row.get('VL_DESC', 0)),
                    vl_merc=self._parse_float(row.get('VL_MERC', 0)),
                    vl_bc_icms=self._parse_float(row.get('VL_BC_ICMS', 0)),
                    vl_icms=self._parse_float(row.get('VL_ICMS', 0)),
                    vl_pis=self._parse_float(row.get('VL_PIS', 0)),
                    vl_cofins=self._parse_float(row.get('VL_COFINS', 0)),
                )
                self.session.add(doc)
                self.session.flush()

                # importa os itens do c170 para esse documento
                itens = df_c170[df_c170['CHV_DOC'] == chv]
                for _, item_row in itens.iterrows():
                    item = ItemFiscal(
                        tenant_id=self.tenant_id,
                        chv_doc=chv,
                        documento_id=doc.id,
                        num_item=int(item_row.get('NUM_ITEM', 0)),
                        cod_item=str(item_row.get('COD_ITEM', '')),
                        descr_compl=str(item_row.get('DESCR_COMPL', '')),
                        qtd=self._parse_float(item_row.get('QTD', 0)),
                        unid=str(item_row.get('UNID', '')),
                        vl_item=self._parse_float(item_row.get('VL_ITEM', 0)),
                        vl_desc=self._parse_float(item_row.get('VL_DESC', 0)),
                        cst_icms=str(item_row.get('CST_ICMS', '')),
                        cfop=str(item_row.get('CFOP', '')),
                        vl_bc_icms=self._parse_float(item_row.get('VL_BC_ICMS', 0)),
                        aliq_icms=self._parse_float(item_row.get('ALIQ_ICMS', 0)),
                        vl_icms=self._parse_float(item_row.get('VL_ICMS', 0)),
                        vl_pis=self._parse_float(item_row.get('VL_PIS', 0)),
                        vl_cofins=self._parse_float(item_row.get('VL_COFINS', 0)),
                    )
                    self.session.add(item)

                count += 1

        self.session.commit()
        return count