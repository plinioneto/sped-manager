"""
Importacao em lote de NFC-e / NF-e XML — versao bulk (raw SQL, sem ORM).

Estrutura esperada:
  XML DE NFCE/
    CAIXA01/
      2025/
        01/
          Transmitidos/     <- importa
          *.xml             <- importa (XMLs soltos na pasta do mes)
          Contingencia/     <- ignora
          ErroTransmissao/  <- ignora

Uso:
    python scripts/importar_xmls_pasta.py --pasta "..." --cnpj 68514439000176 --ano 2025 --mes 01
    python scripts/importar_xmls_pasta.py --pasta "..." --cnpj 68514439000176 --ano 2025
    python scripts/importar_xmls_pasta.py --pasta "..." --cnpj 68514439000176

Flags:
    --dry-run   mostra contagem por mes sem importar
"""

import argparse
import re
import sqlite3
import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import os
from dotenv import load_dotenv
load_dotenv()

# ---------------------------------------------------------------------------
# Configuracao do banco
# ---------------------------------------------------------------------------

def _db_path() -> str:
    url = os.getenv("DATABASE_URL", "sqlite:///./sped_manager.db")
    if url.startswith("sqlite:///"):
        path = url[10:]
        if path.startswith("./"):
            path = str(ROOT / path[2:])
        return path
    raise RuntimeError(f"Este script suporta apenas SQLite. DATABASE_URL={url}")


def _conectar() -> sqlite3.Connection:
    path = _db_path()
    conn = sqlite3.connect(path, timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=15000")
    conn.execute("BEGIN")
    return conn


# ---------------------------------------------------------------------------
# Parsing de XML (sem dependencias do projeto)
# ---------------------------------------------------------------------------

def _rm_ns(conteudo: bytes) -> bytes:
    return re.sub(rb'\s*xmlns[^=]*="[^"]*"', b"", conteudo)

def _text(elem, *path, default=""):
    node = elem
    for tag in path:
        if node is None:
            return default
        node = node.find(tag)
    if node is not None and node.text:
        return node.text.strip()
    return default

def _float(elem, *path):
    t = _text(elem, *path)
    try:
        return float(t.replace(",", ".")) if t else 0.0
    except ValueError:
        return 0.0

def _cnpj(valor):
    return re.sub(r"\D", "", valor or "")

def _dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s[:19]).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

def _chave_icms(det):
    icms_group = det.find("imposto/ICMS") if det.find("imposto") is not None else None
    if icms_group is None:
        return "", "0", 0.0, 0.0
    for child in icms_group:
        cst_node = child.find("CST") or child.find("CSOSN")
        cst = cst_node.text.strip() if (cst_node is not None and cst_node.text) else ""
        aliq_node = child.find("pICMS")
        aliq = aliq_node.text.strip() if (aliq_node is not None and aliq_node.text) else "0"
        vbc = _float(child, "vBC")
        vicms = _float(child, "vICMS")
        return cst, aliq, vbc, vicms
    return "", "0", 0.0, 0.0

def _chave_piscofins(det):
    v_pis = v_cofins = 0.0
    imp = det.find("imposto")
    if imp is None:
        return 0.0, 0.0
    pis = imp.find("PIS")
    if pis is not None:
        for c in pis:
            v_pis = _float(c, "vPIS")
            break
    cof = imp.find("COFINS")
    if cof is not None:
        for c in cof:
            v_cofins = _float(c, "vCOFINS")
            break
    return v_pis, v_cofins

_RE_CHAVE = re.compile(r"(\d{44})")

def chave_do_nome(nome: str):
    m = _RE_CHAVE.search(nome)
    return m.group(1) if m else None

def parsear_xml(conteudo: bytes, tenant_id: int, tenant_cnpj: str):
    """
    Parseia um XML e retorna dicts prontos para insert, ou None se invalido/duplicata.
    Retorna: (doc_dict, itens_list, c190_list, produtos_list, participante_dict | None)
    """
    try:
        root = ET.fromstring(_rm_ns(conteudo))
    except ET.ParseError:
        return None

    inf = None
    if root.tag == "infNFe":
        inf = root
    else:
        for e in root.iter("infNFe"):
            inf = e
            break
    if inf is None:
        return None

    # Chave NF-e
    id_attr = inf.get("Id", "")
    if id_attr.startswith("NFe") and len(id_attr) == 47:
        chv = id_attr[3:]
    elif len(id_attr) == 44:
        chv = id_attr
    else:
        chv = ""
        for e in root.iter("chNFe"):
            if e.text and len(e.text.strip()) == 44:
                chv = e.text.strip()
                break
    if len(chv) != 44:
        return None

    mod   = _text(inf, "ide", "mod")
    tp_nf = _text(inf, "ide", "tpNF")
    ind_oper = "1" if (tp_nf == "1" or mod == "65") else "0"

    # Valida CNPJ
    if ind_oper == "1":
        cnpj_xml = _cnpj(_text(inf, "emit", "CNPJ"))
    else:
        cnpj_xml = _cnpj(_text(inf, "dest", "CNPJ"))
        if not cnpj_xml:
            cnpj_xml = _cnpj(_text(inf, "dest", "CPF"))

    if cnpj_xml and cnpj_xml != tenant_cnpj:
        return None  # CNPJ divergente

    # Participante
    part = None
    if ind_oper == "0":
        cnpj_p = _cnpj(_text(inf, "emit", "CNPJ"))
        nome_p = _text(inf, "emit", "xNome")
        cod_p  = cnpj_p or "FORNECEDOR"
    else:
        cnpj_p = _cnpj(_text(inf, "dest", "CNPJ"))
        nome_p = _text(inf, "dest", "xNome")
        cod_p  = cnpj_p if cnpj_p else "CONSUMIDOR"

    if cnpj_p:
        part = {"tenant_id": tenant_id, "cod_part": cod_p, "nome": nome_p, "cnpj": cnpj_p,
                "criado_em": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")}

    # Documento
    tot = inf.find("total/ICMSTot")
    dt  = _dt(_text(inf, "ide", "dhEmi"))
    doc = {
        "tenant_id":     tenant_id,
        "chv_nfe":       chv,
        "ind_oper":      ind_oper,
        "ind_emit":      "1" if ind_oper == "1" else "0",
        "cod_part":      cod_p,
        "cod_mod":       mod,
        "cod_sit":       "00",
        "ser":           _text(inf, "ide", "serie"),
        "num_doc":       _text(inf, "ide", "nNF"),
        "dt_doc":        dt,
        "dt_e_s":        dt,
        "vl_doc":        _float(tot, "vNF")     if tot is not None else 0.0,
        "vl_desc":       _float(tot, "vDesc")   if tot is not None else 0.0,
        "vl_merc":       _float(tot, "vProd")   if tot is not None else 0.0,
        "vl_bc_icms":    _float(tot, "vBC")     if tot is not None else 0.0,
        "vl_icms":       _float(tot, "vICMS")   if tot is not None else 0.0,
        "vl_bc_icms_st": _float(tot, "vBCST")   if tot is not None else 0.0,
        "vl_icms_st":    _float(tot, "vST")     if tot is not None else 0.0,
        "vl_pis":        _float(tot, "vPIS")    if tot is not None else 0.0,
        "vl_cofins":     _float(tot, "vCOFINS") if tot is not None else 0.0,
        "criado_em":     datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # Itens + agregacao C190
    itens = []
    agg: dict[tuple, dict] = defaultdict(lambda: {
        "vl_opr": 0.0, "vl_bc_icms": 0.0, "vl_icms": 0.0,
        "vl_pis": 0.0, "vl_cofins": 0.0,
    })
    produtos = []

    for det in inf.findall("det"):
        nitem = det.get("nItem", "0")
        num_item = int(nitem) if nitem.isdigit() else 0
        prod_el = det.find("prod")
        if prod_el is None:
            continue

        c_prod = _text(prod_el, "cProd")
        c_ean  = _text(prod_el, "cEAN")
        xprod  = _text(prod_el, "xProd")
        cfop   = _text(prod_el, "CFOP")
        u_com  = _text(prod_el, "uCom")
        q_com  = _float(prod_el, "qCom")
        v_prod = _float(prod_el, "vProd")
        v_desc = _float(prod_el, "vDesc")
        ncm    = _text(prod_el, "NCM")
        cest   = _text(prod_el, "CEST")
        ean    = c_ean if c_ean not in ("SEM GTIN", "0", "") else ""

        cod_item = c_prod if (mod == "65" or ind_oper == "1") else (ean or c_prod)
        if not cod_item:
            continue

        cst, aliq, vbc_icms, v_icms = _chave_icms(det)
        v_pis, v_cofins = _chave_piscofins(det)

        try:
            aliq_float = float(aliq.replace(",", "."))
        except (ValueError, AttributeError):
            aliq_float = 0.0

        itens.append({
            "tenant_id":   tenant_id,
            "chv_nfe":     chv,
            "documento_id": None,
            "num_item":    num_item,
            "cod_item":    cod_item,
            "descr_compl": xprod,
            "qtd":         q_com,
            "unid":        u_com,
            "vl_item":     v_prod,
            "vl_desc":     v_desc,
            "cst_icms":    cst,
            "cfop":        cfop,
            "vl_bc_icms":  vbc_icms,
            "aliq_icms":   aliq_float,
            "vl_icms":     v_icms,
            "vl_pis":      v_pis,
            "vl_cofins":   v_cofins,
        })

        produtos.append({
            "tenant_id":  tenant_id,
            "cod_item":   cod_item,
            "descr_item": xprod,
            "cod_barra":  ean,
            "unid_inv":   u_com,
            "cod_ncm":    ncm,
            "cest":       cest,
            "criado_em":  datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        })

        key = (cst, cfop, aliq)
        agg[key]["vl_opr"]     += v_prod
        agg[key]["vl_bc_icms"] += vbc_icms
        agg[key]["vl_icms"]    += v_icms
        agg[key]["vl_pis"]     += v_pis
        agg[key]["vl_cofins"]  += v_cofins

    c190 = []
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    for (cst, cfop, aliq), vals in agg.items():
        c190.append({
            "tenant_id":   tenant_id,
            "chv_nfe":     chv,
            "documento_id": None,
            "cst_icms":    cst,
            "cfop":        cfop,
            "aliq_icms":   aliq,
            "vl_opr":      round(vals["vl_opr"], 2),
            "vl_bc_icms":  round(vals["vl_bc_icms"], 2),
            "vl_icms":     round(vals["vl_icms"], 2),
            "vl_pis":      round(vals["vl_pis"], 2),
            "vl_cofins":   round(vals["vl_cofins"], 2),
            "criado_em":   now,
        })

    return doc, itens, c190, produtos, part


# ---------------------------------------------------------------------------
# Coleta de arquivos
# ---------------------------------------------------------------------------

PASTAS_IGNORADAS = {"contingencia", "errotransmissao", "cancelados", "canceladas"}

def coletar_xmls_mes(pasta_mes: Path) -> list[Path]:
    xmls = []
    for item in pasta_mes.iterdir():
        if item.is_file() and item.suffix.lower() == ".xml":
            xmls.append(item)
        elif item.is_dir() and item.name.lower() not in PASTAS_IGNORADAS:
            for xml in item.iterdir():
                if xml.is_file() and xml.suffix.lower() == ".xml":
                    xmls.append(xml)
    return xmls

def listar_periodos(pasta_raiz: Path, ano_filtro, mes_filtro):
    periodos: dict[tuple, list[Path]] = {}
    for caixa in sorted(pasta_raiz.iterdir()):
        if not caixa.is_dir():
            continue
        for ano_dir in sorted(caixa.iterdir()):
            if not ano_dir.is_dir():
                continue
            if ano_filtro and ano_dir.name != ano_filtro:
                continue
            for mes_dir in sorted(ano_dir.iterdir()):
                if not mes_dir.is_dir():
                    continue
                if mes_filtro and mes_dir.name != mes_filtro:
                    continue
                periodos.setdefault((ano_dir.name, mes_dir.name), []).append(mes_dir)
    return sorted(periodos.items())


# ---------------------------------------------------------------------------
# Insercao em lote (raw SQL)
# ---------------------------------------------------------------------------

SQL_DOC = """
INSERT INTO documentos_fiscais
  (tenant_id, chv_nfe, ind_oper, ind_emit, cod_part, cod_mod, cod_sit,
   ser, num_doc, dt_doc, dt_e_s,
   vl_doc, vl_desc, vl_merc, vl_bc_icms, vl_icms,
   vl_bc_icms_st, vl_icms_st, vl_pis, vl_cofins, criado_em)
VALUES
  (:tenant_id,:chv_nfe,:ind_oper,:ind_emit,:cod_part,:cod_mod,:cod_sit,
   :ser,:num_doc,:dt_doc,:dt_e_s,
   :vl_doc,:vl_desc,:vl_merc,:vl_bc_icms,:vl_icms,
   :vl_bc_icms_st,:vl_icms_st,:vl_pis,:vl_cofins,:criado_em)
"""

SQL_ITEM = """
INSERT OR IGNORE INTO itens_fiscais
  (tenant_id, chv_nfe, documento_id, num_item, cod_item, descr_compl,
   qtd, unid, vl_item, vl_desc,
   cst_icms, cfop, vl_bc_icms, aliq_icms, vl_icms, vl_pis, vl_cofins)
VALUES
  (:tenant_id,:chv_nfe,:documento_id,:num_item,:cod_item,:descr_compl,
   :qtd,:unid,:vl_item,:vl_desc,
   :cst_icms,:cfop,:vl_bc_icms,:aliq_icms,:vl_icms,:vl_pis,:vl_cofins)
"""

SQL_C190 = """
INSERT OR IGNORE INTO icms_c190
  (tenant_id, chv_nfe, documento_id, cst_icms, cfop, aliq_icms,
   vl_opr, vl_bc_icms, vl_icms, vl_pis, vl_cofins, criado_em)
VALUES
  (:tenant_id,:chv_nfe,:documento_id,:cst_icms,:cfop,:aliq_icms,
   :vl_opr,:vl_bc_icms,:vl_icms,:vl_pis,:vl_cofins,:criado_em)
"""

SQL_PROD = """
INSERT OR IGNORE INTO produtos
  (tenant_id, cod_item, descr_item, cod_barra, unid_inv, cod_ncm, cest, criado_em)
VALUES
  (:tenant_id,:cod_item,:descr_item,:cod_barra,:unid_inv,:cod_ncm,:cest,:criado_em)
"""

SQL_PART = """
INSERT OR IGNORE INTO participantes (tenant_id, cod_part, nome, cnpj, criado_em)
VALUES (:tenant_id, :cod_part, :nome, :cnpj, :criado_em)
"""

def inserir_lote(conn, docs, itens, c190s, produtos, participantes):
    cur = conn.cursor()
    cur.executemany(SQL_DOC,   docs)
    cur.executemany(SQL_ITEM,  itens)
    cur.executemany(SQL_C190,  c190s)
    cur.executemany(SQL_PROD,  produtos)
    if participantes:
        cur.executemany(SQL_PART, participantes)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pasta",  required=True)
    ap.add_argument("--cnpj",   required=True)
    ap.add_argument("--ano",    default=None)
    ap.add_argument("--mes",    default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    pasta_raiz = Path(args.pasta)
    if not pasta_raiz.exists():
        print(f"[ERRO] Pasta nao encontrada: {pasta_raiz}")
        sys.exit(1)

    tenant_cnpj = re.sub(r"\D", "", args.cnpj)

    conn = _conectar()
    cur  = conn.cursor()

    # Busca tenant
    cur.execute("SELECT id, nome FROM tenants WHERE cnpj = ?", (tenant_cnpj,))
    row = cur.fetchone()
    if not row:
        print(f"[ERRO] Tenant {tenant_cnpj} nao encontrado. Cadastre pelo painel admin.")
        sys.exit(1)
    tenant_id, tenant_nome = row

    print(f"\nTenant : {tenant_nome} ({tenant_cnpj})")
    print(f"Pasta  : {pasta_raiz}\n")

    # Carrega chaves existentes em memoria
    print("Carregando chaves ja importadas...", end=" ", flush=True)
    cur.execute("SELECT chv_nfe FROM documentos_fiscais WHERE tenant_id = ?", (tenant_id,))
    chaves = {r[0] for r in cur.fetchall()}
    print(f"{len(chaves)} encontradas.\n")

    periodos = listar_periodos(pasta_raiz, args.ano, args.mes)
    if not periodos:
        print("Nenhum periodo encontrado.")
        return

    if args.dry_run:
        print("Contagem por periodo (dry-run):")
        for (ano, mes), pastas in periodos:
            xmls = []
            for p in pastas:
                xmls.extend(coletar_xmls_mes(p))
            novos = sum(1 for x in xmls if chave_do_nome(x.name) not in chaves)
            print(f"  {ano}/{mes}: {len(xmls)} arquivos ({novos} novos)")
        conn.close()
        return

    totais = {"ok": 0, "dup": 0, "err": 0}

    for (ano, mes), pastas in periodos:
        xmls = []
        for p in pastas:
            xmls.extend(coletar_xmls_mes(p))

        docs, itens_all, c190_all, prods_all, parts_all = [], [], [], [], []
        ok = dup = err = 0
        inicio = time.time()

        for caminho in xmls:
            chave = chave_do_nome(caminho.name)
            if chave and chave in chaves:
                dup += 1
                continue

            resultado = parsear_xml(caminho.read_bytes(), tenant_id, tenant_cnpj)
            if resultado is None:
                err += 1
                continue

            doc, itens, c190, produtos, part = resultado
            docs.append(doc)
            itens_all.extend(itens)
            c190_all.extend(c190)
            prods_all.extend(produtos)
            if part:
                parts_all.append(part)
            chaves.add(doc["chv_nfe"])
            ok += 1

        if docs:
            inserir_lote(conn, docs, itens_all, c190_all, prods_all, parts_all)
            conn.execute("COMMIT")
            conn.execute("BEGIN")

        decorrido = time.time() - inicio
        total = ok + dup + err
        vel = total / decorrido if decorrido > 0 else 0
        print(
            f"  {ano}/{mes}: {total} arq | "
            f"ok:{ok} dup:{dup} err:{err} | "
            f"{vel:.0f} arq/s | {decorrido:.1f}s"
        )
        totais["ok"] += ok
        totais["dup"] += dup
        totais["err"] += err

    conn.execute("COMMIT")
    conn.close()

    print(
        f"\n{'='*50}\n"
        f"  Importados : {totais['ok']}\n"
        f"  Duplicatas : {totais['dup']}\n"
        f"  Erros      : {totais['err']}\n"
        f"{'='*50}"
    )


if __name__ == "__main__":
    main()
