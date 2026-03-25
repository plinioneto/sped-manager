from datetime import datetime
from sqlalchemy.orm import Session
from app.models.documento_fiscal import DocumentoFiscal
from app.models.itens_fiscal_c170 import ItemFiscal
from app.models.produto import Produto


class SilverProcessor:
    def __init__(self, session: Session, tenant_id: int):
        self.session = session
        self.tenant_id = tenant_id

    def _cast_decimal(self, valor) -> float:
        try:
            if valor is None or str(valor).strip() == '':
                return 0.0
            return float(str(valor).replace(',', '.'))
        except:
            return 0.0

    def _cast_data(self, valor) -> datetime:
        try:
            return datetime.strptime(str(valor).strip(), '%d%m%Y')
        except:
            return None

    def _get(self, campos, idx, default=''):
        try:
            return campos[idx] if len(campos) > idx else default
        except:
            return default

    def _parse_linhas(self, linhas_raw: list) -> dict:
        registros = {
            'c100': [],
            'c170': [],
            'c190': [],
            '0200': [],
            'loja': []
        }

        chv_doc_atual = None

        for linha in linhas_raw:
            campos = linha.split('|')
            if len(campos) < 2:
                continue

            bloco = campos[1]

            if bloco == 'C100' and len(campos) > 9:
                chv_doc_atual = campos[9]

            reg = {'campos': campos, 'chv_doc': chv_doc_atual}

            if bloco == 'C100':
                registros['c100'].append(reg)
            elif bloco == 'C170':
                registros['c170'].append(reg)
            elif bloco == 'C190':
                registros['c190'].append(reg)
            elif bloco == '0200':
                registros['0200'].append(reg)
            elif bloco == '0000':
                registros['loja'].append(reg)

        return registros

    def _processar_c100(self, registros: list) -> int:
        criados = 0

        for reg in registros:
            c = reg['campos']
            chv = self._get(c, 9)

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
                ind_oper=self._get(c, 2),
                ind_emit=self._get(c, 3),
                cod_part=self._get(c, 4),
                cod_mod=self._get(c, 5),
                cod_sit=self._get(c, 6),
                ser=self._get(c, 7),
                num_doc=self._get(c, 8),
                dt_doc=self._cast_data(self._get(c, 10)),
                dt_e_s=self._cast_data(self._get(c, 11)),
                vl_doc=self._cast_decimal(self._get(c, 12)),
                ind_pgto=self._get(c, 13),
                vl_desc=self._cast_decimal(self._get(c, 14)),
                vl_abat_nt=self._cast_decimal(self._get(c, 15)),
                vl_merc=self._cast_decimal(self._get(c, 16)),
                ind_frt=self._get(c, 17),
                vl_frt=self._cast_decimal(self._get(c, 18)),
                vl_seg=self._cast_decimal(self._get(c, 19)),
                vl_out_da=self._cast_decimal(self._get(c, 20)),
                vl_bc_icms=self._cast_decimal(self._get(c, 21)),
                vl_icms=self._cast_decimal(self._get(c, 22)),
                vl_bc_icms_st=self._cast_decimal(self._get(c, 23)),
                vl_icms_st=self._cast_decimal(self._get(c, 24)),
                vl_ipi=self._cast_decimal(self._get(c, 25)),
                vl_pis=self._cast_decimal(self._get(c, 26)),
                vl_cofins=self._cast_decimal(self._get(c, 27)),
                vl_pis_st=self._cast_decimal(self._get(c, 28)),
                vl_cofins_st=self._cast_decimal(self._get(c, 29)),
            )
            self.session.add(doc)
            criados += 1

        self.session.commit()
        return criados

    def _processar_c170(self, registros: list) -> int:
        criados = 0

        for reg in registros:
            c = reg['campos']
            chv = reg['chv_doc']

            if not chv:
                continue

            num_item = int(self._get(c, 2)) if self._get(c, 2).isdigit() else 0

            existente = self.session.query(ItemFiscal).filter(
                ItemFiscal.tenant_id == self.tenant_id,
                ItemFiscal.chv_doc == chv,
                ItemFiscal.num_item == num_item
            ).first()

            if existente:
                continue

            doc = self.session.query(DocumentoFiscal).filter(
                DocumentoFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.chv_nfe == chv
            ).first()

            item = ItemFiscal(
                tenant_id=self.tenant_id,
                chv_doc=chv,
                documento_id=doc.id if doc else None,
                num_item=num_item,
                cod_item=self._get(c, 3),
                descr_compl=self._get(c, 4),
                qtd=self._cast_decimal(self._get(c, 5)),
                unid=self._get(c, 6),
                vl_item=self._cast_decimal(self._get(c, 7)),
                vl_desc=self._cast_decimal(self._get(c, 8)),
                ind_mov=self._get(c, 9),
                cst_icms=self._get(c, 10),
                cfop=self._get(c, 11),
                cod_nat=self._get(c, 12),
                vl_bc_icms=self._cast_decimal(self._get(c, 13)),
                aliq_icms=self._cast_decimal(self._get(c, 14)),
                vl_icms=self._cast_decimal(self._get(c, 15)),
                vl_bc_icms_st=self._cast_decimal(self._get(c, 16)),
                aliq_st=self._cast_decimal(self._get(c, 17)),
                vl_icms_st=self._cast_decimal(self._get(c, 18)),
                ind_apur=self._get(c, 19),
                cst_ipi=self._get(c, 20),
                cod_enq=self._get(c, 21),
                vl_bc_ipi=self._cast_decimal(self._get(c, 22)),
                aliq_ipi=self._cast_decimal(self._get(c, 23)),
                vl_ipi=self._cast_decimal(self._get(c, 24)),
                cst_pis=self._get(c, 25),
                vl_bc_pis=self._cast_decimal(self._get(c, 26)),
                aliq_pis=self._cast_decimal(self._get(c, 27)),
                quant_bc_pis=self._cast_decimal(self._get(c, 28)),
                aliq_pis_r=self._cast_decimal(self._get(c, 29)),
                vl_pis=self._cast_decimal(self._get(c, 30)),
                cst_cofins=self._get(c, 31),
                vl_bc_cofins=self._cast_decimal(self._get(c, 32)),
                aliq_cofins=self._cast_decimal(self._get(c, 33)),
                quant_bc_cofins=self._cast_decimal(self._get(c, 34)),
                aliq_cofins_r=self._cast_decimal(self._get(c, 35)),
                vl_cofins=self._cast_decimal(self._get(c, 36)),
                cod_cta=self._get(c, 37),
                cod_item_pai=self._get(c, 38),
            )
            self.session.add(item)
            criados += 1

        self.session.commit()
        return criados

    def _processar_0200(self, registros: list) -> dict:
        criados = 0
        atualizados = 0

        for reg in registros:
            c = reg['campos']
            cod = self._get(c, 2)

            if not cod:
                continue

            existente = self.session.query(Produto).filter(
                Produto.tenant_id == self.tenant_id,
                Produto.cod_item == cod
            ).first()

            if existente:
                existente.descr_item = self._get(c, 3)
                existente.cod_barra = self._get(c, 4)
                existente.cod_ant_item = self._get(c, 5)
                existente.unid_inv = self._get(c, 6)
                existente.tipo_item = self._get(c, 7)
                existente.cod_ncm = self._get(c, 8)
                existente.ex_ipi = self._get(c, 9)
                existente.cod_gen = self._get(c, 10)
                existente.cod_lst = self._get(c, 11)
                existente.aliq_icms = self._cast_decimal(self._get(c, 12))
                existente.cest = self._get(c, 13)
                atualizados += 1
            else:
                produto = Produto(
                    tenant_id=self.tenant_id,
                    cod_item=cod,
                    descr_item=self._get(c, 3),
                    cod_barra=self._get(c, 4),
                    cod_ant_item=self._get(c, 5),
                    unid_inv=self._get(c, 6),
                    tipo_item=self._get(c, 7),
                    cod_ncm=self._get(c, 8),
                    ex_ipi=self._get(c, 9),
                    cod_gen=self._get(c, 10),
                    cod_lst=self._get(c, 11),
                    aliq_icms=self._cast_decimal(self._get(c, 12)),
                    cest=self._get(c, 13),
                )
                self.session.add(produto)
                criados += 1

        self.session.commit()
        return {"criados": criados, "atualizados": atualizados}

    def processar(self, file_path: str) -> dict:
        from app.models.efd_raw import EfdRaw

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

        registros = self._parse_linhas(linhas_raw)

        docs = self._processar_c100(registros['c100'])
        itens = self._processar_c170(registros['c170'])
        resultado_produtos = self._processar_0200(registros['0200'])

        return {
            "status": "concluido",
            "documentos": docs,
            "itens": itens,
            "produtos_criados": resultado_produtos['criados'],
            "produtos_atualizados": resultado_produtos['atualizados'],
        }