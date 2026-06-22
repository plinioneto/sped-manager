import re
import pandas as pd
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.documento_fiscal import DocumentoFiscal
from app.models.itens_fiscal_c170 import ItemFiscal
from app.models.icms_c190 import IcmsC190
from app.models.produto import Produto
from app.models.marca import Marca
from app.models.inventario_h005 import InventarioH005
from app.models.inventario_h010 import InventarioH010
from app.models.estoque_k200 import EstoqueK200
from app.models.participante import Participante

try:
    from app.services.produto_padronizacao import processar_descricao
    _PADRONIZACAO_DISPONIVEL = True
except Exception:
    _PADRONIZACAO_DISPONIVEL = False

try:
    from app.repositories.catalogo_repo import CatalogoProdutoRepository, ean_valido
    _CATALOGO_DISPONIVEL = True
except Exception:
    _CATALOGO_DISPONIVEL = False


def _esta_classificado_catalogo(entrada) -> bool:
    return entrada.categoria_id is not None or entrada.grupo_id is not None


def _esta_classificado_produto(produto: Produto) -> bool:
    return produto.categoria_id is not None or produto.grupo_id is not None


def _copiar_do_catalogo(produto: Produto, catalogo) -> None:
    produto.descricao_padrao    = catalogo.descricao_padrao
    produto.tipo_produto        = catalogo.tipo_produto
    produto.tipo_embalagem      = catalogo.tipo_embalagem
    produto.peso_volume_valor   = catalogo.peso_volume_valor
    produto.peso_volume_unidade = catalogo.peso_volume_unidade
    produto.categoria_id        = catalogo.categoria_id
    produto.grupo_id            = catalogo.grupo_id
    produto.departamento_id     = catalogo.departamento_id
    produto.marca_id            = catalogo.marca_id
    produto.score_categoria     = catalogo.score_categoria
    produto.origem_padronizacao = "catalogo"
    produto.revisao_necessaria  = False


class SilverProcessor:
    def __init__(self, session: Session, tenant_id: int):
        self.session   = session
        self.tenant_id = tenant_id

    # ------------------------------------------------------------------
    # Helpers de conversão
    # ------------------------------------------------------------------

    def _cast_decimal(self, valor) -> float:
        try:
            if valor is None or str(valor).strip() == '':
                return 0.0
            return float(str(valor).replace(',', '.'))
        except Exception:
            return 0.0

    def _cast_data(self, valor) -> datetime:
        try:
            return datetime.strptime(str(valor).strip(), '%d%m%Y')
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Parser de linhas (sem I/O)
    # ------------------------------------------------------------------

    def _parse_linhas(self, linhas_raw: list) -> dict:
        registros = {
            'c100': [], 'c170': [], 'c190': [],
            '0200': [], '0150': [], 'loja': [],
            'h005': [], 'h010': [], 'k200': [],
        }

        chv_nfe_atual = None
        dt_inv_atual  = None

        for linha in linhas_raw:
            campos = linha.split('|')
            if len(campos) < 2:
                continue

            bloco = campos[1]

            if bloco == 'C100' and len(campos) > 9:
                chv_nfe_atual = campos[9]

            rb = {'campos': campos, 'chv_nfe': chv_nfe_atual}

            if bloco == 'C100':
                registros['c100'].append(rb)
            elif bloco == 'C170':
                registros['c170'].append(rb)
            elif bloco == 'C190':
                registros['c190'].append(rb)
            elif bloco == '0150':
                registros['0150'].append({'campos': campos})
            elif bloco == '0200':
                registros['0200'].append(rb)
            elif bloco == '0000':
                registros['loja'].append(rb)
            elif bloco == 'H005' and len(campos) > 2:
                dt_inv_atual = campos[2]
                registros['h005'].append({'campos': campos})
            elif bloco == 'H010':
                registros['h010'].append({'campos': campos, 'dt_inv': dt_inv_atual})
            elif bloco == 'K200':
                registros['k200'].append({'campos': campos})

        return registros

    # ------------------------------------------------------------------
    # Carregamento de chaves existentes (evita N+1 de existência)
    # ------------------------------------------------------------------

    def _chaves_existentes(self, model, *colunas):
        """Retorna set de tuplas com os valores das colunas para registros já existentes."""
        rows = self.session.query(*[getattr(model, c) for c in colunas]).filter(
            getattr(model, 'tenant_id') == self.tenant_id
        ).all()
        return {tuple(r) for r in rows}

    # ------------------------------------------------------------------
    # Processadores (sem commits intermediários)
    # ------------------------------------------------------------------

    def _processar_0150(self, registros: list, existentes: set) -> int:
        criados = 0
        for reg in registros:
            c = reg['campos']
            cod_part = c[2] if len(c) > 2 else ''
            if not cod_part or (cod_part,) in existentes:
                continue
            self.session.add(Participante(
                tenant_id=self.tenant_id,
                cod_part=cod_part,
                nome    =c[3]  if len(c) > 3  else '',
                cod_pais=c[4]  if len(c) > 4  else '',
                cnpj    =c[5]  if len(c) > 5  else '',
                cpf     =c[6]  if len(c) > 6  else '',
                ie      =c[7]  if len(c) > 7  else '',
                cod_mun =c[8]  if len(c) > 8  else '',
                suframa =c[9]  if len(c) > 9  else '',
                endereco=c[10] if len(c) > 10 else '',
                num     =c[11] if len(c) > 11 else '',
                compl   =c[12] if len(c) > 12 else '',
                bairro  =c[13] if len(c) > 13 else '',
            ))
            existentes.add((cod_part,))
            criados += 1
        return criados

    def _processar_c100(self, registros: list, existentes: set) -> int:
        """Retorna contagem. Após chamar, faça session.flush() para obter IDs."""
        criados = 0
        for reg in registros:
            c   = reg['campos']
            chv = c[9] if len(c) > 9 else ''
            if not chv or (chv,) in existentes:
                continue
            self.session.add(DocumentoFiscal(
                tenant_id    =self.tenant_id,
                chv_nfe      =chv,
                ind_oper     =c[2]  if len(c) > 2  else '',
                ind_emit     =c[3]  if len(c) > 3  else '',
                cod_part     =c[4]  if len(c) > 4  else '',
                cod_mod      =c[5]  if len(c) > 5  else '',
                cod_sit      =c[6]  if len(c) > 6  else '',
                ser          =c[7]  if len(c) > 7  else '',
                num_doc      =c[8]  if len(c) > 8  else '',
                dt_doc       =self._cast_data(c[10])    if len(c) > 10 else None,
                dt_e_s       =self._cast_data(c[11])    if len(c) > 11 else None,
                vl_doc       =self._cast_decimal(c[12]) if len(c) > 12 else 0.0,
                vl_desc      =self._cast_decimal(c[14]) if len(c) > 14 else 0.0,
                vl_merc      =self._cast_decimal(c[16]) if len(c) > 16 else 0.0,
                vl_bc_icms   =self._cast_decimal(c[21]) if len(c) > 21 else 0.0,
                vl_icms      =self._cast_decimal(c[22]) if len(c) > 22 else 0.0,
                vl_bc_icms_st=self._cast_decimal(c[23]) if len(c) > 23 else 0.0,
                vl_icms_st   =self._cast_decimal(c[24]) if len(c) > 24 else 0.0,
                vl_pis       =self._cast_decimal(c[26]) if len(c) > 26 else 0.0,
                vl_cofins    =self._cast_decimal(c[27]) if len(c) > 27 else 0.0,
                fonte        ='efd',
            ))
            existentes.add((chv,))
            criados += 1
        return criados

    def _build_doc_cache(self) -> dict:
        """Retorna dict {chv_nfe: doc_id} após flush do C100."""
        rows = self.session.query(DocumentoFiscal.chv_nfe, DocumentoFiscal.id).filter(
            DocumentoFiscal.tenant_id == self.tenant_id
        ).all()
        return {r.chv_nfe: r.id for r in rows}

    def _processar_c170(self, registros: list, existentes: set, doc_cache: dict) -> int:
        criados = 0
        for reg in registros:
            c   = reg['campos']
            chv = reg['chv_nfe']
            num = int(c[2]) if len(c) > 2 and c[2].isdigit() else 0
            if not chv or (chv, num) in existentes:
                continue
            self.session.add(ItemFiscal(
                tenant_id   =self.tenant_id,
                chv_nfe     =chv,
                documento_id=doc_cache.get(chv),
                num_item    =num,
                cod_item    =c[3]  if len(c) > 3  else '',
                descr_compl =c[4]  if len(c) > 4  else '',
                qtd         =self._cast_decimal(c[5])  if len(c) > 5  else 0.0,
                unid        =c[6]  if len(c) > 6  else '',
                vl_item     =self._cast_decimal(c[7])  if len(c) > 7  else 0.0,
                vl_desc     =self._cast_decimal(c[8])  if len(c) > 8  else 0.0,
                cst_icms    =c[10] if len(c) > 10 else '',
                cfop        =c[11] if len(c) > 11 else '',
                vl_bc_icms  =self._cast_decimal(c[13]) if len(c) > 13 else 0.0,
                aliq_icms   =self._cast_decimal(c[14]) if len(c) > 14 else 0.0,
                vl_icms     =self._cast_decimal(c[15]) if len(c) > 15 else 0.0,
                vl_pis      =self._cast_decimal(c[30]) if len(c) > 30 else 0.0,
                vl_cofins   =self._cast_decimal(c[36]) if len(c) > 36 else 0.0,
            ))
            existentes.add((chv, num))
            criados += 1
        return criados

    def _processar_c190(self, registros: list, existentes: set, doc_cache: dict) -> int:
        criados = 0
        for reg in registros:
            c    = reg['campos']
            chv  = reg['chv_nfe']
            cst  = c[2] if len(c) > 2 else ''
            cfop = c[3] if len(c) > 3 else ''
            aliq = self._cast_decimal(c[4]) if len(c) > 4 else 0.0
            if not chv or (chv, cst, cfop, aliq) in existentes:
                continue
            self.session.add(IcmsC190(
                tenant_id    =self.tenant_id,
                chv_nfe      =chv,
                documento_id =doc_cache.get(chv),
                cst_icms     =cst,
                cfop         =cfop,
                aliq_icms    =aliq,
                vl_opr       =self._cast_decimal(c[5])  if len(c) > 5  else 0.0,
                vl_bc_icms   =self._cast_decimal(c[6])  if len(c) > 6  else 0.0,
                vl_icms      =self._cast_decimal(c[7])  if len(c) > 7  else 0.0,
                vl_bc_icms_st=self._cast_decimal(c[8])  if len(c) > 8  else 0.0,
                vl_icms_st   =self._cast_decimal(c[9])  if len(c) > 9  else 0.0,
                vl_red_bc    =self._cast_decimal(c[10]) if len(c) > 10 else 0.0,
                vl_pis       =self._cast_decimal(c[11]) if len(c) > 11 else 0.0,
                vl_cofins    =self._cast_decimal(c[12]) if len(c) > 12 else 0.0,
                cod_obs      =c[13] if len(c) > 13 else '',
            ))
            existentes.add((chv, cst, cfop, aliq))
            criados += 1
        return criados

    def _processar_0200(self, registros: list, existentes_cod: set) -> dict:
        criados = atualizados = 0

        for reg in registros:
            c   = reg['campos']
            cod = c[2] if len(c) > 2 else ''
            if not cod:
                continue

            descr_item   = c[3] if len(c) > 3 else ''
            cod_barra_raw = (c[4] if len(c) > 4 else '').strip()

            if (cod,) in existentes_cod:
                produto_obj = self.session.query(Produto).filter(
                    Produto.tenant_id == self.tenant_id,
                    Produto.cod_item  == cod
                ).first()
                if produto_obj:
                    produto_obj.descr_item = descr_item
                    produto_obj.cod_barra  = cod_barra_raw
                    produto_obj.unid_inv   = c[6]  if len(c) > 6  else ''
                    produto_obj.tipo_item  = c[7]  if len(c) > 7  else ''
                    produto_obj.cod_ncm    = c[8]  if len(c) > 8  else ''
                    produto_obj.aliq_icms  = self._cast_decimal(c[12]) if len(c) > 12 else 0.0
                    produto_obj.cest       = c[13] if len(c) > 13 else ''
                    atualizados += 1
            else:
                produto_obj = Produto(
                    tenant_id =self.tenant_id,
                    cod_item  =cod,
                    descr_item=descr_item,
                    cod_barra =cod_barra_raw,
                    unid_inv  =c[6]  if len(c) > 6  else '',
                    tipo_item =c[7]  if len(c) > 7  else '',
                    cod_ncm   =c[8]  if len(c) > 8  else '',
                    aliq_icms =self._cast_decimal(c[12]) if len(c) > 12 else 0.0,
                    cest      =c[13] if len(c) > 13 else '',
                )
                self.session.add(produto_obj)
                existentes_cod.add((cod,))
                criados += 1

            if _CATALOGO_DISPONIVEL and ean_valido(cod_barra_raw):
                catalogo_repo   = CatalogoProdutoRepository(self.session)
                entrada_catalogo = catalogo_repo.buscar_por_ean(cod_barra_raw)
                if entrada_catalogo and _esta_classificado_catalogo(entrada_catalogo):
                    if produto_obj.origem_padronizacao not in ('manual', 'manual_sem_cat'):
                        _copiar_do_catalogo(produto_obj, entrada_catalogo)
                else:
                    self._aplicar_padronizacao(produto_obj, descr_item)
                    if _esta_classificado_produto(produto_obj):
                        catalogo_repo.upsert_from_produto(produto_obj, cod_barra_raw)
            else:
                self._aplicar_padronizacao(produto_obj, descr_item)

        return {"criados": criados, "atualizados": atualizados}

    def _aplicar_padronizacao(self, produto: Produto, descr_item: str) -> None:
        if not _PADRONIZACAO_DISPONIVEL or not descr_item:
            return
        try:
            resultado = processar_descricao(descr_item, session=self.session)
            produto.descricao_padrao    = resultado.descricao_padrao
            produto.tipo_produto        = resultado.tipo_produto
            produto.tipo_embalagem      = resultado.tipo_embalagem
            produto.peso_volume_valor   = resultado.peso_volume_valor
            produto.peso_volume_unidade = resultado.peso_volume_unidade
            produto.score_padronizacao  = resultado.score_confianca
            produto.origem_padronizacao = resultado.origem
            produto.revisao_necessaria  = resultado.revisao_necessaria
            produto.categoria_id        = resultado.categoria_id
            produto.grupo_id            = resultado.grupo_id
            produto.departamento_id     = resultado.departamento_id
            produto.score_categoria     = resultado.score_categoria
            if resultado.marca:
                marca_obj = self.session.query(Marca).filter(Marca.nome == resultado.marca).first()
                if marca_obj:
                    produto.marca_id = marca_obj.id
        except Exception:
            pass

    def _processar_h005(self, registros: list, existentes: set) -> int:
        criados = 0
        for reg in registros:
            c       = reg['campos']
            dt_inv  = self._cast_data(c[2]) if len(c) > 2 else None
            mot_inv = c[4] if len(c) > 4 else ''
            if not dt_inv:
                continue
            if (dt_inv, mot_inv) in existentes:
                h = self.session.query(InventarioH005).filter(
                    InventarioH005.tenant_id == self.tenant_id,
                    InventarioH005.dt_inv    == dt_inv,
                    InventarioH005.mot_inv   == mot_inv,
                ).first()
                if h:
                    h.vl_inv = self._cast_decimal(c[3]) if len(c) > 3 else 0.0
                continue
            self.session.add(InventarioH005(
                tenant_id=self.tenant_id,
                dt_inv   =dt_inv,
                vl_inv   =self._cast_decimal(c[3]) if len(c) > 3 else 0.0,
                mot_inv  =mot_inv,
            ))
            existentes.add((dt_inv, mot_inv))
            criados += 1
        return criados

    def _build_h005_cache(self) -> dict:
        """Retorna dict {(dt_inv, mot_inv): h005_id} após flush do H005."""
        rows = self.session.query(
            InventarioH005.dt_inv, InventarioH005.mot_inv, InventarioH005.id
        ).filter(InventarioH005.tenant_id == self.tenant_id).all()
        return {(r.dt_inv, r.mot_inv): r.id for r in rows}

    def _processar_h010(self, registros: list, existentes: set, h005_cache: dict) -> int:
        criados = 0
        for reg in registros:
            c        = reg['campos']
            dt_inv   = self._cast_data(reg.get('dt_inv')) if reg.get('dt_inv') else None
            cod_item = c[2] if len(c) > 2 else ''
            ind_prop = c[7] if len(c) > 7 else '0'
            if not dt_inv or not cod_item or (dt_inv, cod_item, ind_prop) in existentes:
                continue
            pai_id = next((v for (d, m), v in h005_cache.items() if d == dt_inv), None)
            self.session.add(InventarioH010(
                tenant_id   =self.tenant_id,
                inventario_id=pai_id,
                dt_inv      =dt_inv,
                cod_item    =cod_item,
                unid        =c[3]  if len(c) > 3  else '',
                qtd         =self._cast_decimal(c[4]) if len(c) > 4 else 0.0,
                vl_unit     =self._cast_decimal(c[5]) if len(c) > 5 else 0.0,
                vl_item     =self._cast_decimal(c[6]) if len(c) > 6 else 0.0,
                ind_prop    =ind_prop,
                cod_part    =c[8]  if len(c) > 8  else '',
                txt_compl   =c[9]  if len(c) > 9  else '',
                cod_cta     =c[10] if len(c) > 10 else '',
            ))
            existentes.add((dt_inv, cod_item, ind_prop))
            criados += 1
        return criados

    def _processar_k200(self, registros: list, existentes: set) -> int:
        criados = 0
        for reg in registros:
            c        = reg['campos']
            dt_est   = self._cast_data(c[2]) if len(c) > 2 else None
            cod_item = c[3] if len(c) > 3 else ''
            ind_est  = c[5] if len(c) > 5 else '0'
            if not dt_est or not cod_item or (dt_est, cod_item, ind_est) in existentes:
                continue
            self.session.add(EstoqueK200(
                tenant_id=self.tenant_id,
                dt_est   =dt_est,
                cod_item =cod_item,
                qt_est   =self._cast_decimal(c[4]) if len(c) > 4 else 0.0,
                ind_est  =ind_est,
            ))
            existentes.add((dt_est, cod_item, ind_est))
            criados += 1
        return criados

    # ------------------------------------------------------------------
    # Ponto de entrada
    # ------------------------------------------------------------------

    def processar_conteudo(self, conteudo: str) -> dict:
        """Processa diretamente o conteúdo do arquivo EFD (sem passar pelo efd_raw)."""
        linhas_raw = [l.strip() for l in conteudo.splitlines() if l.strip()]
        if not linhas_raw:
            return {"status": "erro", "motivo": "arquivo vazio"}
        return self._processar(linhas_raw)

    def processar(self, file_path: str) -> dict:
        """Mantido para compatibilidade — lê do efd_raw."""
        from app.models.efd_raw import EfdRaw
        linhas = (
            self.session.query(EfdRaw.conteudo_linha)
            .filter(EfdRaw.tenant_id == self.tenant_id, EfdRaw.file_path == file_path)
            .order_by(EfdRaw.num_linha)
            .all()
        )
        linhas_raw = [l.conteudo_linha for l in linhas]
        if not linhas_raw:
            return {"status": "erro", "motivo": "arquivo não encontrado no bronze"}
        return self._processar(linhas_raw)

    def _processar(self, linhas_raw: list) -> dict:
        registros = self._parse_linhas(linhas_raw)

        # Pré-carrega chaves existentes (1 query por tabela)
        ex_0150 = self._chaves_existentes(Participante, 'cod_part')
        ex_c100 = self._chaves_existentes(DocumentoFiscal, 'chv_nfe')
        ex_c170 = self._chaves_existentes(ItemFiscal, 'chv_nfe', 'num_item')
        ex_c190 = self._chaves_existentes(IcmsC190, 'chv_nfe', 'cst_icms', 'cfop', 'aliq_icms')
        ex_0200 = self._chaves_existentes(Produto, 'cod_item')
        ex_h005 = self._chaves_existentes(InventarioH005, 'dt_inv', 'mot_inv')
        ex_h010 = self._chaves_existentes(InventarioH010, 'dt_inv', 'cod_item', 'ind_prop')
        ex_k200 = self._chaves_existentes(EstoqueK200, 'dt_est', 'cod_item', 'ind_est')

        # 1. Participantes e C100
        participantes = self._processar_0150(registros['0150'], ex_0150)
        docs          = self._processar_c100(registros['c100'], ex_c100)

        # Flush para obter IDs dos documentos recém-inseridos
        self.session.flush()
        doc_cache = self._build_doc_cache()

        # 2. Itens e fiscal (dependem dos IDs de C100)
        itens              = self._processar_c170(registros['c170'], ex_c170, doc_cache)
        c190               = self._processar_c190(registros['c190'], ex_c190, doc_cache)
        resultado_produtos = self._processar_0200(registros['0200'], ex_0200)

        # 3. Inventário H005 → flush → H010
        h005 = self._processar_h005(registros['h005'], ex_h005)
        self.session.flush()
        h005_cache = self._build_h005_cache()
        h010       = self._processar_h010(registros['h010'], ex_h010, h005_cache)

        # 4. Estoque
        k200 = self._processar_k200(registros['k200'], ex_k200)

        # Commit único
        self.session.commit()

        return {
            "status"            : "concluido",
            "participantes"     : participantes,
            "documentos"        : docs,
            "itens"             : itens,
            "c190"              : c190,
            "produtos_criados"  : resultado_produtos['criados'],
            "produtos_atualizados": resultado_produtos['atualizados'],
            "h005"              : h005,
            "h010"              : h010,
            "k200"              : k200,
        }
