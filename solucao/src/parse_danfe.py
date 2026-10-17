"""Extracao defensiva da DANFE (PDF) e gate de reconciliacao por nota.

Estrategia (endossada por caralhoo.md 2.2):
  1. filtro de ruido: removes os caracteres-marca d'agua (size grande, cinza);
  2. ancoragem do corpo na tripla NCM(8) + O/CST(3) + CFOP(4) + UN;
  3. continuacao de descricao (linhas sem NCM) unida ao item anterior;
  4. valores em pt-BR convertidos via Decimal (nunca float);
  5. reconciliacao por nota contra os totais impressos.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Optional

import pdfplumber

from .caminhos import CNPJ_FOCO, DANFE_DIR

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Modelo de dados
# --------------------------------------------------------------------------- #


@dataclass
class Item:
    chave: str
    nItem: int
    cProd: str
    xProd: str
    NCM: str
    CST: str
    CFOP: str
    un: str
    qtd: Decimal
    vUnit: Decimal
    vProd: Decimal
    vICMS: Decimal
    bCalcICMS: Decimal
    emitente_cnpj: str = ""
    destinatario_cnpj: str = ""
    perspectiva: str = ""
    arquivo: str = ""

    def xprod_norm(self) -> str:
        return normalizar_xprod(self.xProd)


@dataclass
class Totais:
    v_produtos: Decimal = Decimal("0")
    v_icms: Decimal = Decimal("0")
    v_pis: Decimal = Decimal("0")
    v_cofins: Decimal = Decimal("0")
    b_calc_icms: Decimal = Decimal("0")


@dataclass
class Nota:
    chave: str
    emitente_cnpj: str
    destinatario_cnpj: str
    cfop_nota: str
    perspectiva: str
    itens: list = field(default_factory=list)
    totais: Totais = field(default_factory=Totais)
    arquivo: str = ""
    tratamento: dict = field(default_factory=dict)

    def reconciliacao(self) -> "Reconciliacao":
        soma_prod = sum((i.vProd for i in self.itens), Decimal("0"))
        soma_icms = sum((i.vICMS for i in self.itens), Decimal("0"))
        soma_pis = Decimal("0")
        soma_cofins = Decimal("0")
        for it in self.itens:
            p, c = pis_cofins_item(
                it.vProd, it.vICMS, it.CFOP, self.tratamento.get(it.cProd), modo="impresso"
            )
            soma_pis += p
            soma_cofins += c
        return Reconciliacao(
            chave=self.chave,
            n_itens=len(self.itens),
            soma_produtos=soma_prod,
            totais_produtos=self.totais.v_produtos,
            soma_icms=soma_icms,
            totais_icms=self.totais.v_icms,
            soma_pis=soma_pis,
            totais_pis=self.totais.v_pis,
            soma_cofins=soma_cofins,
            totais_cofins=self.totais.v_cofins,
        )


@dataclass
class Reconciliacao:
    chave: str
    n_itens: int
    soma_produtos: Decimal
    totais_produtos: Decimal
    soma_icms: Decimal
    totais_icms: Decimal
    soma_pis: Decimal
    totais_pis: Decimal
    soma_cofins: Decimal
    totais_cofins: Decimal

    TOL = Decimal("0.05")

    def divergencias(self, tol: Optional[Decimal] = None) -> list:
        tol = tol or self.TOL
        d = []
        for nome, a, b in (
            ("vProd", self.soma_produtos, self.totais_produtos),
            ("vICMS", self.soma_icms, self.totais_icms),
            ("PIS", self.soma_pis, self.totais_pis),
            ("COFINS", self.soma_cofins, self.totais_cofins),
        ):
            if abs(a - b) > tol:
                d.append((nome, a, b, a - b))
        return d

    @property
    def ok(self) -> bool:
        return len(self.divergencias()) == 0


# --------------------------------------------------------------------------- #
# Utilitarios
# --------------------------------------------------------------------------- #

# A marca d'agua e composta de caracteres grandes e cinza (0.6, 0.6, 0.6).
def _filtrar_ruido(page):
    return page.filter(
        lambda o: (o.get("object_type") != "char") or (o.get("size", 0) < 20)
    )


_RE_ITEM = re.compile(
    r"^(?P<desc>.+?)\s+"
    r"(?P<ncm>\d{8})\s+"
    r"(?P<cst>\d{3})\s+"
    r"(?P<cfop>\d{4})\s+"
    r"(?P<un>[A-Z]{1,4})\s+"
    r"(?P<nums>(?:\d[\d.]*,\d{2,4})(?:\s+\d[\d.]*,\d{2,4}){7})\s*$"
)

_RE_CNPJ = re.compile(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}")


def parse_br(s: str) -> Decimal:
    """Converte um numero pt-BR em Decimal. Ignora letras/artefatos colados."""
    if s is None:
        return Decimal("0")
    limpo = re.sub(r"[^\d.,]", "", str(s))
    if limpo == "":
        return Decimal("0")
    # remove separadores de milhar (pontos) e troca virgula por ponto
    limpo = limpo.replace(".", "").replace(",", ".")
    # protege contra multiplos pontos residuais
    if limpo.count(".") > 1:
        partes = limpo.split(".")
        limpo = "".join(partes[:-1]) + "." + partes[-1]
    try:
        return Decimal(limpo)
    except Exception as e:  # noqa: BLE001
        logger.warning("parse_br falhou para %r (%s); usando 0.00", s, e)
        return Decimal("0")


def normalizar_xprod(x: str) -> str:
    """Maiusculas, sem acento, sem -BONIFICACAO, espacos colapsados."""
    import unicodedata

    s = unicodedata.normalize("NFKD", str(x))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.upper()
    s = re.sub(r"\s*-\s*BONIFICACA(?:O|AO)\s*$", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def r2(x: Decimal) -> Decimal:
    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def pis_cofins_item(
    vProd: Decimal,
    vICMS: Decimal,
    cfop: str,
    tratamento: Optional[str],
    modo: str = "lei",
) -> tuple:
    """Regra de PIS/Cofins de hoje por item. Devolve (PIS, COFINS) arredondados.

    modo="lei"      -> regra do enunciado: exportacao (CFOP 7xxx) = zero.
    modo="impresso" -> regra usada pelo sistema que gerou os totais da DANFE:
                       so a bonificacao (5910) zera; a exportacao usa a regra do
                       produto. Com este modo as 1.387 notas reconciliam (o
                       gerador sintetico nao aplicou a excecao de exportacao nos
                       totais impressos -- artefato documentado em DECISOES.md).

    P10: o modo "impresso" e um workaround de reconciliacao do dataset sintetico.
    Em producao (XML real) a reconciliacao deve usar modo="lei"; o gate atual
    valida contra totais que contem esse erro conhecido do gerador.
    """
    if tratamento != "tributado":
        return Decimal("0"), Decimal("0")
    if str(cfop) == "5910":
        return Decimal("0"), Decimal("0")
    if modo == "lei" and str(cfop).startswith("7"):
        return Decimal("0"), Decimal("0")
    base = vProd - vICMS
    pis = r2(base * Decimal("0.0165"))
    cofins = r2(base * Decimal("0.076"))
    return pis, cofins


# --------------------------------------------------------------------------- #
# Extracao dos totais
# --------------------------------------------------------------------------- #


def _numeros(linha: str) -> list:
    return re.findall(r"-?\d[\d.]*,\d{2,4}", linha)


def _extrair_totais(texto: str) -> Totais:
    t = Totais()
    linhas = [l.strip() for l in texto.split("\n")]
    for i, ln in enumerate(linhas):
        up = ln.upper()
        if "V. TOTAL PRODUTOS" in up and "VALOR DO PIS" in up:
            if i + 1 < len(linhas):
                nums = _numeros(linhas[i + 1])
                if len(nums) >= 2:
                    t.v_icms = parse_br(nums[1])
                    t.b_calc_icms = parse_br(nums[0])
                    t.v_pis = parse_br(nums[-2])
                    t.v_produtos = parse_br(nums[-1])
        if "VALOR DA COFINS" in up and "V. TOTAL DA NOTA" in up:
            if i + 1 < len(linhas):
                nums = _numeros(linhas[i + 1])
                if len(nums) >= 2:
                    t.v_cofins = parse_br(nums[-2])
    return t


# --------------------------------------------------------------------------- #
# Extração dos itens
# --------------------------------------------------------------------------- #


def _extrair_itens(texto: str, chave: str, arquivo: str) -> list:
    linhas = texto.split("\n")
    dentro = False
    itens: list = []
    atual: Optional[dict] = None

    for ln in linhas:
        raw = ln.rstrip()
        up = raw.upper()
        if "DADOS DOS PRODUTOS" in up:
            dentro = True
            continue
        if "DADOS ADICIONAIS" in up:
            break
        if not dentro:
            continue
        if raw.strip() == "":
            continue

        m = _RE_ITEM.match(raw.strip())
        if m:
            d = m.groupdict()
            if atual is not None:
                itens.append(_fechar_item(atual, len(itens) + 1, chave, arquivo))
            nums = _numeros(d["nums"])
            atual = {
                "cProd": d["desc"].split()[0] if d["desc"].split() else "",
                "xProd": d["desc"],
                "NCM": d["ncm"],
                "CST": d["cst"],
                "CFOP": d["cfop"],
                "un": d["un"],
                "nums": nums,
            }
        else:
            # linha de continuacao da descricao (sem NCM): une ao item atual
            if atual is not None:
                token = raw.strip()
                # ignora linhas que sao claramente cabecalho/rodape
                if _e_continuacao_valida(token, up):
                    atual["xProd"] = (atual["xProd"] + " " + token).strip()
    if atual is not None:
        itens.append(_fechar_item(atual, len(itens) + 1, chave, arquivo))
    return itens


def _e_continuacao_valida(token: str, up: str) -> bool:
    if not token:
        return False
    proibidos = (
        "CÓDIGO",
        "CODIGO",
        "DESCRIÇÃO",
        "DESCRICAO",
        "DADOS",
        "INFORMA",
        "RESERVADO",
        "DOCUMENTO",
        "CÁLCULO",
        "CALCULO",
        "TRANSPORTADOR",
        "NOME /",
        "MUNICÍPIO",
        "MUNICIPIO",
        "ENDEREÇO",
        "ENDERECO",
        "NATUREZA",
        "INSCRI",
        "CNPJ",
        "CHAVE",
    )
    if any(p in up for p in proibidos):
        return False
    # nao deve conter um NCM/CFOP solto
    if re.search(r"\d{4,}", token):
        return False
    return True


def _fechar_item(d: dict, nItem: int, chave: str, arquivo: str) -> Item:
    nums = d["nums"]
    # ordem: QUANT, V.UNIT, V.TOTAL, B.CALC.ICMS, VALOR ICMS, VALOR IPI, ALIQ ICMS, ALIQ IPI
    qtd = parse_br(nums[0]) if len(nums) > 0 else Decimal("0")
    vUnit = parse_br(nums[1]) if len(nums) > 1 else Decimal("0")
    vProd = parse_br(nums[2]) if len(nums) > 2 else Decimal("0")
    bCalc = parse_br(nums[3]) if len(nums) > 3 else Decimal("0")
    vICMS = parse_br(nums[4]) if len(nums) > 4 else Decimal("0")
    return Item(
        chave=chave,
        nItem=nItem,
        cProd=d["cProd"],
        xProd=re.sub(r"\s+", " ", d["xProd"]).strip(),
        NCM=d["NCM"],
        CST=d["CST"],
        CFOP=d["CFOP"],
        un=d["un"],
        qtd=qtd,
        vUnit=vUnit,
        vProd=vProd,
        vICMS=vICMS,
        bCalcICMS=bCalc,
        arquivo=arquivo,
    )


def _extrair_cnpjs(texto: str) -> tuple:
    """Extrai CNPJ do emitente e do destinatario.

    O bloco do destinatario comeca em 'DESTINATARIO / REMETENTE'; o primeiro
    CNPJ impresso apos 'REMETENTE' e o do destinatario. O emitente e obtido da
    propria chave de acesso (posicoes 6..20), entao aqui so precisamos do
    destinatario para os joins de tipo_cliente.
    """
    cs = _RE_CNPJ.findall(texto)
    emit = re.sub(r"\D", "", cs[0]) if cs else ""
    dest = ""
    idx = texto.upper().find("REMETENTE")
    if idx >= 0:
        cs2 = _RE_CNPJ.findall(texto[idx:])
        if cs2:
            dest = re.sub(r"\D", "", cs2[0])
    if not dest and cs:
        dest = re.sub(r"\D", "", cs[0])
    return emit, dest


# --------------------------------------------------------------------------- #
# API principal
# --------------------------------------------------------------------------- #


def parse_pdf(path: Path, tratamento_por_produto: Optional[dict] = None) -> Nota:
    path = Path(path)
    chave = path.stem
    with pdfplumber.open(str(path)) as pdf:
        pagina = _filtrar_ruido(pdf.pages[0])
        texto = pagina.extract_text() or ""

    itens = _extrair_itens(texto, chave, path.name)
    totais = _extrair_totais(texto)
    emit, dest = _extrair_cnpjs(texto)

    emitente_chave = chave[6:20] if len(chave) >= 20 else ""
    emitente = emitente_chave or emit
    perspectiva = "venda" if emitente_chave == CNPJ_FOCO else "compra"

    for it in itens:
        it.emitente_cnpj = emitente
        it.destinatario_cnpj = dest
        it.perspectiva = perspectiva

    cfop_nota = itens[0].CFOP if itens else ""
    nota = Nota(
        chave=chave,
        emitente_cnpj=emitente,
        destinatario_cnpj=dest,
        cfop_nota=cfop_nota,
        perspectiva=perspectiva,
        itens=itens,
        totais=totais,
        arquivo=path.name,
    )
    if tratamento_por_produto:
        nota.tratamento = tratamento_por_produto
    return nota


def parse_todas(
    danfe_dir: Optional[Path] = None,
    tratamento_por_produto: Optional[dict] = None,
    limite: Optional[int] = None,
) -> list:
    danfe_dir = Path(danfe_dir or DANFE_DIR)
    arquivos = sorted(danfe_dir.glob("*.pdf"))
    if limite:
        arquivos = arquivos[:limite]
    notas = []
    for p in arquivos:
        notas.append(parse_pdf(p, tratamento_por_produto))
    return notas


if __name__ == "__main__":
    import sys

    import pandas as pd

    from .caminhos import data_path

    limite = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    pis = pd.read_csv(data_path("pis_cofins_hoje.csv"), sep=";", encoding="utf-8-sig", dtype=str)
    trat = dict(zip(pis["cProd"], pis["tratamento"]))
    notas = parse_todas(tratamento_por_produto=trat, limite=limite)
    ok = 0
    for n in notas:
        rec = n.reconciliacao()
        if rec.ok:
            ok += 1
        else:
            print("DIVERGENCIA", n.chave, rec.divergencias())
    print(f"reconciliadas {ok}/{len(notas)}")
