"""
XmlParser — importação de NF-e (mod 55) e NFC-e (mod 65).

Suporta:
  - NF-e de entrada (compras de fornecedores)
      tpNF=0 → CNPJ do <dest> deve ser do tenant
  - NFC-e de saída (vendas ao consumidor)
      mod=65 ou tpNF=1 → CNPJ do <emit> deve ser do tenant

Fluxo por XML:
  1. Remove namespace → parse com ElementTree (stdlib)
  2. Valida chave NF-e (44 dígitos) e CNPJ do tenant
  3. Checa duplicata por chv_nfe
  4. Upsert Participante (emit ou dest conforme tipo)
  5. Cria DocumentoFiscal
  6. Para cada <det>: upsert Produto + cria ItemFiscal
  7. Deriva IcmsC190 por agregação CST/CFOP/alíquota
  8. commit() único ao final

Bronze ignorado: XML não é linha-a-linha como EFD → vai direto para silver.
Schema não muda: todos os models já existem com os campos necessários.
"""

import io
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.documento_fiscal import DocumentoFiscal
from app.models.itens_fiscal_c170 import ItemFiscal
from app.models.icms_c190 import IcmsC190
from app.models.produto import Produto
from app.models.participante import Participante
from app.models.marca import Marca

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


# ---------------------------------------------------------------------------
# Helpers de parsing (sem namespace)
# ---------------------------------------------------------------------------

_RE_XMLNS = re.compile(rb'\s*xmlns[^=]*="[^"]*"')


def _limpar_namespace(conteudo: bytes) -> bytes:
    """Remove declarações xmlns para simplificar o parsing com ElementTree."""
    return _RE_XMLNS.sub(b"", conteudo)


def _parse_xml(conteudo: bytes) -> ET.Element:
    limpo = _limpar_namespace(conteudo)
    return ET.fromstring(limpo)


def _find(elem: ET.Element, *path) -> ET.Element | None:
    """Navega caminho de tags filhas (sem namespace)."""
    node = elem
    for tag in path:
        if node is None:
            return None
        node = node.find(tag)
    return node


def _text(elem: ET.Element, *path, default: str = "") -> str:
    """Retorna texto do nó no caminho, ou default."""
    node = _find(elem, *path)
    if node is not None and node.text:
        return node.text.strip()
    return default


def _float_val(elem: ET.Element, *path, default: float = 0.0) -> float:
    """Retorna float do nó no caminho, ou default."""
    t = _text(elem, *path, default="")
    if not t:
        return default
    try:
        return float(t.replace(",", "."))
    except ValueError:
        return default


def _limpar_cnpj(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def _parse_data(dh_emi: str) -> datetime | None:
    """Converte dhEmi ISO-8601 para datetime (trunca nos segundos)."""
    if not dh_emi:
        return None
    try:
        return datetime.fromisoformat(dh_emi[:19])
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Extração de tributos por item
# ---------------------------------------------------------------------------

def _extrair_icms_item(det: ET.Element) -> tuple[str, str, float, float]:
    """
    Retorna (cst, aliq_str, vbc_icms, v_icms) do <det>.
    aliq_str é string para compatibilidade com IcmsC190.aliq_icms.
    O filho de <ICMS> pode ser ICMS00, ICMS10, ICMSSN101, etc.
    """
    icms_group = _find(det, "imposto", "ICMS")
    if icms_group is None:
        return "", "0", 0.0, 0.0

    for child in icms_group:  # primeiro (e único) filho
        # Atenção: ET elements sem filhos são falsy — usar "is not None" obrigatório
        cst_node = child.find("CST")
        if cst_node is None:
            cst_node = child.find("CSOSN")
        cst = cst_node.text.strip() if (cst_node is not None and cst_node.text) else ""

        aliq_node = child.find("pICMS")
        aliq_str = aliq_node.text.strip() if (aliq_node is not None and aliq_node.text) else "0"

        vbc   = _float_val(child, "vBC")
        vicms = _float_val(child, "vICMS")
        return cst, aliq_str, vbc, vicms

    return "", "0", 0.0, 0.0


def _extrair_pis_cofins_item(det: ET.Element) -> tuple[float, float]:
    """Retorna (v_pis, v_cofins) do <det>."""
    v_pis = v_cofins = 0.0

    pis_group = _find(det, "imposto", "PIS")
    if pis_group is not None:
        for child in pis_group:
            v_pis = _float_val(child, "vPIS")
            break

    cofins_group = _find(det, "imposto", "COFINS")
    if cofins_group is not None:
        for child in cofins_group:
            v_cofins = _float_val(child, "vCOFINS")
            break

    return v_pis, v_cofins


# ---------------------------------------------------------------------------
# Parser principal
# ---------------------------------------------------------------------------

class XmlParser:
    """
    Processa NF-e / NFC-e XML e persiste no banco.

    Uso:
        parser = XmlParser(session, tenant_id, tenant_cnpj)
        resultado = parser.processar(conteudo_bytes, "NFC001.xml")
    """

    def __init__(self, session: Session, tenant_id: int, tenant_cnpj: str, skip_padronizacao: bool = False):
        self.session = session
        self.tenant_id = tenant_id
        self.tenant_cnpj = _limpar_cnpj(tenant_cnpj)
        self.skip_padronizacao = skip_padronizacao
        # Caches em memória — None = cache desativado (usa DB); set/dict = cache ativo
        self._cache_chaves: set | None = None
        self._cache_produtos: set | None = None
        self._cache_participantes: set | None = None
        self._cache_marcas: dict[str, int] = {}  # nome → id (sempre dict, mesmo sem warmup)

    def warmup(self) -> tuple[int, int]:
        """
        Pré-carrega caches de chaves NF-e, cod_item e participantes em memória.
        Reduz drasticamente o número de queries ao banco em importações em lote.
        Retorna (n_chaves, n_produtos) carregados.
        """
        self._cache_chaves = set(
            r[0] for r in
            self.session.query(DocumentoFiscal.chv_nfe)
            .filter(DocumentoFiscal.tenant_id == self.tenant_id)
            .all()
        )
        self._cache_produtos = set(
            r[0] for r in
            self.session.query(Produto.cod_item)
            .filter(Produto.tenant_id == self.tenant_id)
            .all()
        )
        self._cache_participantes = set(
            r[0] for r in
            self.session.query(Participante.cod_part)
            .filter(Participante.tenant_id == self.tenant_id)
            .all()
        )
        # Cache de marcas: nome → id (evita SELECT por produto categorizado)
        self._cache_marcas: dict[str, int] = {
            nome: mid
            for nome, mid in self.session.query(Marca.nome, Marca.id).all()
            if nome
        }
        return len(self._cache_chaves), len(self._cache_produtos)

    # ── Ponto de entrada — lote (importação em massa) ─────────────────────────

    def processar_lote(self, lote: list[tuple[bytes, str]]) -> dict:
        """
        Processa uma lista de (conteudo_bytes, nome_arquivo) com 1 flush por lote.

        Fluxo otimizado:
          1. Parse + validação + dedup via cache  (zero round trips)
          2. Upsert participantes novos            (cache-first)
          3. session.add_all(docs) + flush()       (1 round trip para N docs)
          4. Itens + C190 + Produtos               (sem flush extra)

        O chamador deve fazer session.commit() + expunge_all() ao final.
        Retorna dict com: concluidos, duplicatas, invalidos, prod_criados.
        """
        concluidos = duplicatas = invalidos = 0
        prod_criados = 0

        # ── Fase 1: parse + filtragem (puro Python) ───────────────────────────
        pendentes: list[tuple] = []  # (inf_nfe, chv_nfe, mod, ind_oper)

        for conteudo, nome in lote:
            try:
                root = _parse_xml(conteudo)
            except ET.ParseError:
                invalidos += 1
                continue

            inf_nfe = self._localizar_inf_nfe(root)
            if inf_nfe is None:
                invalidos += 1
                continue

            chv_nfe = self._extrair_chave(root, inf_nfe)
            if not chv_nfe or len(chv_nfe) != 44:
                invalidos += 1
                continue

            mod     = _text(inf_nfe, "ide", "mod")
            tp_nf   = _text(inf_nfe, "ide", "tpNF")
            ind_oper = "1" if (tp_nf == "1" or mod == "65") else "0"

            ok, _ = self._validar_cnpj(inf_nfe, mod, ind_oper)
            if not ok:
                invalidos += 1
                continue

            if self._chave_existe(chv_nfe):
                duplicatas += 1
                continue

            # Marca no cache imediatamente — evita dup dentro do mesmo lote
            if self._cache_chaves is not None:
                self._cache_chaves.add(chv_nfe)

            pendentes.append((inf_nfe, chv_nfe, mod, ind_oper))

        if not pendentes:
            return {"concluidos": 0, "duplicatas": duplicatas,
                    "invalidos": invalidos, "prod_criados": 0}

        # ── Fase 2: upsert participantes (cache-first, sem flush) ─────────────
        for inf_nfe, chv_nfe, mod, ind_oper in pendentes:
            if ind_oper == "0":
                cnpj_part = _limpar_cnpj(_text(inf_nfe, "emit", "CNPJ"))
                nome_part = _text(inf_nfe, "emit", "xNome")
                cod_part  = cnpj_part or "FORNECEDOR"
            else:
                cnpj_part = _limpar_cnpj(_text(inf_nfe, "dest", "CNPJ"))
                nome_part = _text(inf_nfe, "dest", "xNome")
                cod_part  = cnpj_part if cnpj_part else "CONSUMIDOR"
            if cnpj_part:
                self._upsert_participante(cod_part, nome_part, cnpj_part)

        # ── Fase 3: criar todos os DocumentoFiscal → 1 flush para o lote ─────
        doc_objs = [self._criar_documento_obj(inf, chv, mod, op)
                    for inf, chv, mod, op in pendentes]
        self.session.add_all(doc_objs)
        self.session.flush()  # 1 round trip para N documentos — obtém todos os IDs

        # ── Fase 4: itens + C190 + produtos (sem flush extra) ─────────────────
        for (inf_nfe, chv_nfe, mod, ind_oper), doc in zip(pendentes, doc_objs):
            agg, pc = self._processar_itens(inf_nfe, chv_nfe, doc, mod, ind_oper)
            self._derivar_c190(chv_nfe, doc.id, agg)
            prod_criados += pc
            concluidos   += 1

        return {
            "concluidos":    concluidos,
            "duplicatas":    duplicatas,
            "invalidos":     invalidos,
            "prod_criados":  prod_criados,
        }

    # ── Ponto de entrada — arquivo único ──────────────────────────────────────

    def processar(self, conteudo: bytes, nome_arquivo: str, auto_commit: bool = True) -> dict:
        """
        Processa um único XML.

        Retorna dict com:
          status: "concluido" | "duplicata" | "cnpj_divergente" | "invalido"
          documentos, itens, produtos_criados — preenchidos em caso de sucesso
          erro — mensagem em caso de falha

        auto_commit=False: não faz commit (use para importação em lote; o chamador
        deve fazer session.commit() periodicamente).
        """
        try:
            root = _parse_xml(conteudo)
        except ET.ParseError as e:
            return {"status": "invalido", "erro": f"XML malformado: {e}", "chv_nfe": ""}

        inf_nfe = self._localizar_inf_nfe(root)
        if inf_nfe is None:
            return {"status": "invalido", "erro": "Elemento <infNFe> não encontrado", "chv_nfe": ""}

        chv_nfe = self._extrair_chave(root, inf_nfe)
        if not chv_nfe or len(chv_nfe) != 44:
            return {"status": "invalido", "erro": f"Chave NF-e inválida: {chv_nfe!r}", "chv_nfe": chv_nfe or ""}

        mod   = _text(inf_nfe, "ide", "mod")   # "55"=NF-e  "65"=NFC-e
        tp_nf = _text(inf_nfe, "ide", "tpNF")  # "0"=entrada "1"=saída
        ind_oper = "1" if (tp_nf == "1" or mod == "65") else "0"

        # Validação de CNPJ
        ok, cnpj_xml = self._validar_cnpj(inf_nfe, mod, ind_oper)
        if not ok:
            return {
                "status": "cnpj_divergente",
                "chv_nfe": chv_nfe,
                "cnpj_xml": cnpj_xml,
                "erro": f"CNPJ do XML ({cnpj_xml}) ≠ tenant ({self.tenant_cnpj})",
            }

        # Duplicata
        if self._chave_existe(chv_nfe):
            return {
                "status": "duplicata",
                "chv_nfe": chv_nfe,
                "documentos": 0, "itens": 0, "produtos_criados": 0,
            }

        # Persiste tudo em uma transação
        doc = self._criar_documento(inf_nfe, chv_nfe, mod, ind_oper)
        agg, prod_criados = self._processar_itens(inf_nfe, chv_nfe, doc, mod, ind_oper)
        self._derivar_c190(chv_nfe, doc.id, agg)
        if self._cache_chaves is not None:
            self._cache_chaves.add(chv_nfe)
        if auto_commit:
            self.session.commit()

        total_itens = sum(v["qtd_itens"] for v in agg.values())
        return {
            "status": "concluido",
            "chv_nfe": chv_nfe,
            "documentos": 1,
            "itens": total_itens,
            "produtos_criados": prod_criados,
        }

    # ── Ponto de entrada — ZIP ────────────────────────────────────────────────

    @staticmethod
    def processar_zip(
        conteudo_zip: bytes,
        nome_zip: str,
        session: Session,
        tenant_id: int,
        tenant_cnpj: str,
    ) -> list[dict]:
        """
        Processa todos os XMLs dentro de um ZIP.
        Retorna lista de resultados, um por XML encontrado.
        """
        resultados = []
        parser = XmlParser(session, tenant_id, tenant_cnpj)

        try:
            with zipfile.ZipFile(io.BytesIO(conteudo_zip)) as zf:
                xml_names = [n for n in zf.namelist() if n.lower().endswith(".xml")]
                for nome in xml_names:
                    with zf.open(nome) as f:
                        conteudo = f.read()
                    resultado = parser.processar(conteudo, nome)
                    resultado["arquivo"] = nome
                    resultados.append(resultado)
        except zipfile.BadZipFile:
            resultados.append({
                "status": "invalido",
                "arquivo": nome_zip,
                "erro": "Arquivo ZIP corrompido ou inválido",
            })

        return resultados

    # ── Metadados (preview sem escrita no banco) ──────────────────────────────

    @staticmethod
    def extrair_metadados(conteudo: bytes) -> dict:
        """
        Extrai metadados do XML sem tocar no banco.
        Útil para exibir preview antes de processar.
        """
        try:
            root = _parse_xml(conteudo)
        except ET.ParseError as e:
            return {"valido": False, "erro": str(e)}

        inf_nfe = XmlParser._localizar_inf_nfe_static(root)
        if inf_nfe is None:
            return {"valido": False, "erro": "Elemento <infNFe> não encontrado"}

        chv_nfe = XmlParser._extrair_chave_static(root, inf_nfe)
        mod     = _text(inf_nfe, "ide", "mod")
        tp_nf   = _text(inf_nfe, "ide", "tpNF")
        dh_emi  = _text(inf_nfe, "ide", "dhEmi")
        n_nf    = _text(inf_nfe, "ide", "nNF")
        serie   = _text(inf_nfe, "ide", "serie")

        ind_oper = "1" if (tp_nf == "1" or mod == "65") else "0"
        tipo_doc = "NFC-e" if mod == "65" else ("NF-e entrada" if ind_oper == "0" else "NF-e saída")

        cnpj_emit = _limpar_cnpj(_text(inf_nfe, "emit", "CNPJ"))
        nome_emit = _text(inf_nfe, "emit", "xNome")
        cnpj_dest = _limpar_cnpj(_text(inf_nfe, "dest", "CNPJ"))
        nome_dest = _text(inf_nfe, "dest", "xNome")

        num_itens = len(inf_nfe.findall("det"))
        dt = _parse_data(dh_emi)

        return {
            "valido":    len(chv_nfe) == 44,
            "chv_nfe":   chv_nfe,
            "tipo":      tipo_doc,
            "ind_oper":  ind_oper,
            "mod":       mod,
            "num_doc":   n_nf,
            "serie":     serie,
            "dt_emissao": dt.strftime("%d/%m/%Y") if dt else "—",
            "dt_obj":    dt,
            "cnpj_emit": cnpj_emit,
            "nome_emit": nome_emit,
            "cnpj_dest": cnpj_dest,
            "nome_dest": nome_dest,
            "num_itens": num_itens,
        }

    # ── Localização e extração (estáticos + instância) ────────────────────────

    @staticmethod
    def _localizar_inf_nfe_static(root: ET.Element) -> ET.Element | None:
        if root.tag == "infNFe":
            return root
        for elem in root.iter("infNFe"):
            return elem
        return None

    def _localizar_inf_nfe(self, root: ET.Element) -> ET.Element | None:
        return self._localizar_inf_nfe_static(root)

    @staticmethod
    def _extrair_chave_static(root: ET.Element, inf_nfe: ET.Element) -> str:
        """
        Extrai chave NF-e de 44 dígitos:
        1. Atributo Id do <infNFe> (sem prefixo "NFe")
        2. Elemento <chNFe> em <protNFe>
        """
        id_attr = inf_nfe.get("Id", "")
        if id_attr.startswith("NFe") and len(id_attr) == 47:
            return id_attr[3:]
        if len(id_attr) == 44 and id_attr.isdigit():
            return id_attr
        for elem in root.iter("chNFe"):
            if elem.text and len(elem.text.strip()) == 44:
                return elem.text.strip()
        return id_attr

    def _extrair_chave(self, root: ET.Element, inf_nfe: ET.Element) -> str:
        return self._extrair_chave_static(root, inf_nfe)

    def _validar_cnpj(
        self, inf_nfe: ET.Element, mod: str, ind_oper: str
    ) -> tuple[bool, str]:
        """
        Valida que o XML pertence ao tenant.
        Saída → emitente deve ser o tenant.
        Entrada → destinatário deve ser o tenant.
        Retorna (ok, cnpj_encontrado).
        """
        if ind_oper == "1":
            cnpj_xml = _limpar_cnpj(_text(inf_nfe, "emit", "CNPJ"))
        else:
            cnpj_xml = _limpar_cnpj(_text(inf_nfe, "dest", "CNPJ"))
            if not cnpj_xml:
                # NF-e para pessoa física — aceitar sem validação de CNPJ
                cnpj_xml = _limpar_cnpj(_text(inf_nfe, "dest", "CPF"))

        if not cnpj_xml:
            return True, ""  # sem CNPJ identificável — aceita
        return cnpj_xml == self.tenant_cnpj, cnpj_xml

    def _chave_existe(self, chv_nfe: str) -> bool:
        if self._cache_chaves is not None:
            return chv_nfe in self._cache_chaves
        return (
            self.session.query(DocumentoFiscal)
            .filter(
                DocumentoFiscal.tenant_id == self.tenant_id,
                DocumentoFiscal.chv_nfe == chv_nfe,
            )
            .first()
        ) is not None

    # ── Persistência ──────────────────────────────────────────────────────────

    def _criar_documento_obj(
        self, inf_nfe: ET.Element, chv_nfe: str, mod: str, ind_oper: str
    ) -> DocumentoFiscal:
        """Cria objeto DocumentoFiscal sem session.add/flush — para processar_lote()."""
        ide = _find(inf_nfe, "ide")
        tot = _find(inf_nfe, "total", "ICMSTot")
        dt_doc = _parse_data(_text(inf_nfe, "ide", "dhEmi"))

        if ind_oper == "0":
            cnpj_part = _limpar_cnpj(_text(inf_nfe, "emit", "CNPJ"))
            cod_part  = cnpj_part or "FORNECEDOR"
        else:
            cnpj_part = _limpar_cnpj(_text(inf_nfe, "dest", "CNPJ"))
            cod_part  = cnpj_part if cnpj_part else "CONSUMIDOR"

        # Resolve cod_part pelo CNPJ (participante pode já existir do EFD com cod_part diferente)
        cod_part = self._resolver_cod_part(cnpj_part, cod_part)

        return DocumentoFiscal(
            tenant_id     = self.tenant_id,
            chv_nfe       = chv_nfe,
            ind_oper      = ind_oper,
            ind_emit      = "1" if ind_oper == "1" else "0",
            cod_part      = cod_part,
            cod_mod       = mod,
            cod_sit       = "00",
            ser           = _text(ide, "serie") if ide is not None else "",
            num_doc       = _text(ide, "nNF")   if ide is not None else "",
            dt_doc        = dt_doc,
            dt_e_s        = dt_doc,
            vl_doc        = _float_val(tot, "vNF")     if tot is not None else 0.0,
            vl_desc       = _float_val(tot, "vDesc")   if tot is not None else 0.0,
            vl_merc       = _float_val(tot, "vProd")   if tot is not None else 0.0,
            vl_bc_icms    = _float_val(tot, "vBC")     if tot is not None else 0.0,
            vl_icms       = _float_val(tot, "vICMS")   if tot is not None else 0.0,
            vl_bc_icms_st = _float_val(tot, "vBCST")   if tot is not None else 0.0,
            vl_icms_st    = _float_val(tot, "vST")     if tot is not None else 0.0,
            vl_pis        = _float_val(tot, "vPIS")    if tot is not None else 0.0,
            vl_cofins     = _float_val(tot, "vCOFINS") if tot is not None else 0.0,
            fonte         = 'xml',
        )

    def _criar_documento(
        self, inf_nfe: ET.Element, chv_nfe: str, mod: str, ind_oper: str
    ) -> DocumentoFiscal:
        ide = _find(inf_nfe, "ide")
        tot = _find(inf_nfe, "total", "ICMSTot")
        dt_doc = _parse_data(_text(inf_nfe, "ide", "dhEmi"))

        # Participante relevante
        if ind_oper == "0":  # entrada — emitente é o fornecedor
            cnpj_part = _limpar_cnpj(_text(inf_nfe, "emit", "CNPJ"))
            nome_part = _text(inf_nfe, "emit", "xNome")
            cod_part  = cnpj_part or "FORNECEDOR"
        else:                # saída — destinatário é o cliente (quando houver)
            cnpj_part = _limpar_cnpj(_text(inf_nfe, "dest", "CNPJ"))
            nome_part = _text(inf_nfe, "dest", "xNome")
            cod_part  = cnpj_part if cnpj_part else "CONSUMIDOR"

        if cnpj_part:
            self._upsert_participante(cod_part, nome_part, cnpj_part)
        cod_part = self._resolver_cod_part(cnpj_part, cod_part)

        doc = DocumentoFiscal(
            tenant_id     = self.tenant_id,
            chv_nfe       = chv_nfe,
            ind_oper      = ind_oper,
            ind_emit      = "1" if ind_oper == "1" else "0",
            cod_part      = cod_part,
            cod_mod       = mod,
            cod_sit       = "00",
            ser           = _text(ide, "serie")  if ide is not None else "",
            num_doc       = _text(ide, "nNF")    if ide is not None else "",
            dt_doc        = dt_doc,
            dt_e_s        = dt_doc,
            vl_doc        = _float_val(tot, "vNF")     if tot is not None else 0.0,
            vl_desc       = _float_val(tot, "vDesc")   if tot is not None else 0.0,
            vl_merc       = _float_val(tot, "vProd")   if tot is not None else 0.0,
            vl_bc_icms    = _float_val(tot, "vBC")     if tot is not None else 0.0,
            vl_icms       = _float_val(tot, "vICMS")   if tot is not None else 0.0,
            vl_bc_icms_st = _float_val(tot, "vBCST")   if tot is not None else 0.0,
            vl_icms_st    = _float_val(tot, "vST")     if tot is not None else 0.0,
            vl_pis        = _float_val(tot, "vPIS")    if tot is not None else 0.0,
            vl_cofins     = _float_val(tot, "vCOFINS") if tot is not None else 0.0,
            fonte         = 'xml',
        )
        self.session.add(doc)
        self.session.flush()  # flush necessário para obter doc.id (FK dos itens)
        return doc

    def _processar_itens(
        self,
        inf_nfe: ET.Element,
        chv_nfe: str,
        doc: DocumentoFiscal,
        mod: str,
        ind_oper: str,
    ) -> tuple[dict, int]:
        """
        Itera sobre os <det> do XML.
        Retorna (agg_c190, qtd_produtos_criados).
        """
        agg: dict[tuple, dict] = defaultdict(lambda: {
            "vl_opr": 0.0, "vl_bc_icms": 0.0, "vl_icms": 0.0,
            "vl_pis": 0.0, "vl_cofins":  0.0, "qtd_itens": 0,
        })
        prod_criados = 0

        for det in inf_nfe.findall("det"):
            num_item_str = det.get("nItem", "0")
            num_item = int(num_item_str) if num_item_str.isdigit() else 0

            prod_elem = _find(det, "prod")
            if prod_elem is None:
                continue

            c_prod  = _text(prod_elem, "cProd")
            c_ean   = _text(prod_elem, "cEAN")
            xprod   = _text(prod_elem, "xProd")
            cfop    = _text(prod_elem, "CFOP")
            u_com   = _text(prod_elem, "uCom")
            q_com   = _float_val(prod_elem, "qCom")
            v_prod  = _float_val(prod_elem, "vProd")
            v_desc  = _float_val(prod_elem, "vDesc")
            ncm     = _text(prod_elem, "NCM")
            cest    = _text(prod_elem, "CEST")

            ean_limpo = c_ean if c_ean not in ("SEM GTIN", "0", "") else ""

            # cod_item:
            #   NFC-e (mod=65) ou NF-e saída → cProd é código interno da loja
            #   NF-e entrada → usa EAN quando disponível (cruza com catálogo global)
            #                  senão usa cProd do fornecedor
            if mod == "65" or ind_oper == "1":
                cod_item = c_prod
            else:
                cod_item = ean_limpo if ean_limpo else c_prod

            if not cod_item:
                continue

            cst, aliq_str, vbc_icms, v_icms = _extrair_icms_item(det)
            v_pis, v_cofins = _extrair_pis_cofins_item(det)

            # Upsert produto
            criado = self._upsert_produto(cod_item, xprod, ean_limpo, u_com, ncm, cest)
            if criado:
                prod_criados += 1

            # Documento é novo (verificado via cache de chaves) →
            # itens desta chave não podem existir no banco; INSERT direto.
            try:
                aliq_float = float(aliq_str.replace(",", "."))
            except (ValueError, AttributeError):
                aliq_float = 0.0

            self.session.add(ItemFiscal(
                tenant_id    = self.tenant_id,
                chv_nfe      = chv_nfe,
                documento_id = doc.id,
                num_item     = num_item,
                cod_item     = cod_item,
                descr_compl  = xprod,
                qtd          = q_com,
                unid         = u_com,
                vl_item      = v_prod,
                vl_desc      = v_desc,
                cst_icms     = cst,
                cfop         = cfop,
                vl_bc_icms   = vbc_icms,
                aliq_icms    = aliq_float,
                vl_icms      = v_icms,
                vl_pis       = v_pis,
                vl_cofins    = v_cofins,
            ))

            # Acumula para C190
            chave_c190 = (cst, cfop, aliq_str)
            agg[chave_c190]["vl_opr"]     += v_prod
            agg[chave_c190]["vl_bc_icms"] += vbc_icms
            agg[chave_c190]["vl_icms"]    += v_icms
            agg[chave_c190]["vl_pis"]     += v_pis
            agg[chave_c190]["vl_cofins"]  += v_cofins
            agg[chave_c190]["qtd_itens"]  += 1

        return agg, prod_criados

    def _derivar_c190(self, chv_nfe: str, documento_id: int, agg: dict) -> None:
        """Cria IcmsC190 derivado da agregação CST/CFOP/alíquota dos itens.
        Documento é garantidamente novo → INSERT direto sem SELECT de existência."""
        for (cst, cfop, aliq), vals in agg.items():
            self.session.add(IcmsC190(
                tenant_id    = self.tenant_id,
                chv_nfe      = chv_nfe,
                documento_id = documento_id,
                cst_icms     = cst,
                cfop         = cfop,
                aliq_icms    = aliq,
                vl_opr       = round(vals["vl_opr"],     2),
                vl_bc_icms   = round(vals["vl_bc_icms"], 2),
                vl_icms      = round(vals["vl_icms"],    2),
                vl_pis       = round(vals["vl_pis"],     2),
                vl_cofins    = round(vals["vl_cofins"],  2),
            ))

    # ── Helpers de persistência ───────────────────────────────────────────────

    def _resolver_cod_part(self, cnpj: str, cod_part_fallback: str) -> str:
        """Retorna o cod_part canônico para o CNPJ — usa o do EFD se já existir."""
        if not cnpj:
            return cod_part_fallback
        existente = (
            self.session.query(Participante)
            .filter(
                Participante.tenant_id == self.tenant_id,
                Participante.cnpj      == cnpj,
            )
            .first()
        )
        return existente.cod_part if existente else cod_part_fallback

    def _upsert_participante(self, cod_part: str, nome: str, cnpj: str) -> None:
        # Lookup por CNPJ para reusar cod_part do EFD quando o mesmo fornecedor já existe
        if cnpj:
            existente_por_cnpj = (
                self.session.query(Participante)
                .filter(
                    Participante.tenant_id == self.tenant_id,
                    Participante.cnpj      == cnpj,
                )
                .first()
            )
            if existente_por_cnpj:
                existente_por_cnpj.nome = nome or existente_por_cnpj.nome
                if self._cache_participantes is not None:
                    self._cache_participantes.add(existente_por_cnpj.cod_part)
                return

        # Cache hit pelo cod_part
        if self._cache_participantes is not None and cod_part in self._cache_participantes:
            return

        existente = (
            self.session.query(Participante)
            .filter(
                Participante.tenant_id == self.tenant_id,
                Participante.cod_part  == cod_part,
            )
            .first()
        )
        if existente:
            existente.nome = nome or existente.nome
            existente.cnpj = cnpj or existente.cnpj
        else:
            self.session.add(Participante(
                tenant_id=self.tenant_id,
                cod_part=cod_part,
                nome=nome,
                cnpj=cnpj,
            ))
        if self._cache_participantes is not None:
            self._cache_participantes.add(cod_part)

    def _upsert_produto(
        self,
        cod_item: str,
        descr_item: str,
        cod_barra: str,
        unid_inv: str,
        cod_ncm: str,
        cest: str,
    ) -> bool:
        """Cria ou atualiza Produto. Retorna True se criou."""
        # Cache hit — produto já existe, pula query e update
        if self._cache_produtos is not None and cod_item in self._cache_produtos:
            return False

        existente = (
            self.session.query(Produto)
            .filter(
                Produto.tenant_id == self.tenant_id,
                Produto.cod_item  == cod_item,
            )
            .first()
        )

        if existente:
            # Atualiza metadados sem sobrescrever padronização existente
            existente.descr_item = descr_item or existente.descr_item
            existente.cod_barra  = cod_barra  or existente.cod_barra
            existente.unid_inv   = unid_inv   or existente.unid_inv
            existente.cod_ncm    = cod_ncm    or existente.cod_ncm
            existente.cest       = cest       or existente.cest
            # Roda padronização se o produto ainda não foi classificado
            if (
                existente.origem_padronizacao not in ("manual", "manual_sem_cat")
                and not (existente.categoria_id or existente.grupo_id)
            ):
                self._aplicar_padronizacao(existente, descr_item)
            return False

        produto = Produto(
            tenant_id  = self.tenant_id,
            cod_item   = cod_item,
            descr_item = descr_item,
            cod_barra  = cod_barra,
            unid_inv   = unid_inv,
            cod_ncm    = cod_ncm,
            cest       = cest,
        )
        self.session.add(produto)
        # Não faz flush aqui — produto.id não é usado como FK em importação XML
        if self._cache_produtos is not None:
            self._cache_produtos.add(cod_item)

        # EAN catalog + padronização — mesmo fluxo do silver.py
        # Com skip_padronizacao=True, pula tudo: evita SELECT que dispara autoflush
        # (a query do catálogo forçaria flush de todos os objetos pendentes na sessão).
        # O backfill_padronizacao.py classificará esses produtos depois.
        if not self.skip_padronizacao:
            if _CATALOGO_DISPONIVEL and ean_valido(cod_barra):
                catalogo_repo = CatalogoProdutoRepository(self.session)
                with self.session.no_autoflush:
                    entrada = catalogo_repo.buscar_por_ean(cod_barra)
                if entrada and (entrada.categoria_id or entrada.grupo_id):
                    _copiar_do_catalogo(produto, entrada)
                else:
                    self._aplicar_padronizacao(produto, descr_item)
                    if produto.categoria_id or produto.grupo_id:
                        with self.session.no_autoflush:
                            catalogo_repo.upsert_from_produto(produto, cod_barra)
            else:
                self._aplicar_padronizacao(produto, descr_item)

        return True

    def _aplicar_padronizacao(self, produto: Produto, descr_item: str) -> None:
        """Enriquece produto com pipeline de padronização (falha silenciosa)."""
        if self.skip_padronizacao or not _PADRONIZACAO_DISPONIVEL or not descr_item:
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
                # Cache de marcas evita SELECT por produto — carregado no warmup()
                mid = self._cache_marcas.get(resultado.marca)
                if mid is None and not self._cache_marcas:
                    # fallback quando warmup não foi chamado
                    marca_obj = (
                        self.session.query(Marca)
                        .filter(Marca.nome == resultado.marca)
                        .first()
                    )
                    mid = marca_obj.id if marca_obj else None
                if mid:
                    produto.marca_id = mid
        except Exception:
            pass  # padronização é enriquecimento, não dado primário


# ---------------------------------------------------------------------------
# Helper — cópia de atributos do catálogo (evita importar silver.py)
# ---------------------------------------------------------------------------

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
