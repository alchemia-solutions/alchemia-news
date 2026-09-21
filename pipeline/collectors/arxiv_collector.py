"""Coletor arXiv -- preprints em categorias q-bio relevantes, via RSS por categoria.

2026-09-18: MIGRADO da API Atom (`export.arxiv.org/api/query`) para o RSS por
categoria (`rss.arxiv.org/rss/<cat>`). Spec: `docs/specs/2026-09-18-coletor-arxiv-via-rss.md`.

Por que: a API Atom passou a responder **HTTP 406 Not Acceptable** a qualquer
`search_query` contendo HIFEN -- e as tres categorias monitoradas (`q-bio.BM`,
`q-bio.QM`, `q-bio.MN`) tem hifen todas. Medido ao vivo: `cat:cs.AI` devolve 200,
`cat:q-bio.BM` devolve 406. Nao e header, nao e limite de taxa, nao e escape e nao
e host -- os quatro foram testados e descartados (detalhe na spec). Resultado: o
coletor devolveu **0 itens nas ultimas 6 execucoes seguidas** e ninguem viu, porque
`ColetaParcial` e absorvida e o pipeline continua reportando sucesso.

Diferenca de comportamento, declarada: o RSS entrega **o lote de anuncio do dia**,
nao uma janela de `window_days`. Com execucao 3x/dia e deduplicacao, nenhum anuncio
escapa -- o que se perde e backfill de historico, que de todo modo estava morto.

Invariantes do setor preservados: nenhum LLM; toda entrada carrega o termo que a
trouxe (o filtro saiu do servidor para o cliente, entao os termos casados agora sao
REGISTRADOS em vez de implicitos na URL); forma de saida identica (`common.Item`).
"""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET

from . import common

DC_NS = "{http://purl.org/dc/elements/1.1/}"
# 2026-09-18: `announce_type` e NAMESPACED. Buscar sem o namespace devolve None e o
# filtro de tipo nunca aplica -- pego no teste contra cs.LG, onde 106 dos 304 itens
# eram `replace`/`replace-cross` (revisao de preprint ja anunciado) e passavam todos.
ARXIV_NS = "{http://arxiv.org/schemas/atom}"

# O RSS do arXiv e publicado nestes dois hosts, com corpo identico (verificado
# byte a byte em 2026-09-18). O segundo e fallback, nao redundancia decorativa.
RSS_HOSTS = ("https://rss.arxiv.org/rss", "https://export.arxiv.org/rss")

# `description` vem como "arXiv:ID Announce Type: tipo  Abstract: <texto>".
_ABSTRACT = re.compile(r"Abstract:\s*(.*)", re.S)
_ARXIV_ID = re.compile(r"arXiv:(\S+)")
# `dc:creator` traz afiliacao entre parenteses: "Fulano (Univ X), Beltrano (Dept Y)"
_AFILIACAO = re.compile(r"\s*\([^)]*\)")

# O RSS traz nome com escape LaTeX (`Adri\'an Rodr\'iguez-Mu\~noz`); a API Atom antiga
# devolvia UTF-8 limpo. Sem desfazer isto, a migracao REGRIDE a qualidade do dado.
_ACENTOS = {
    "'": {"a": "á", "e": "é", "i": "í", "o": "ó", "u": "ú", "c": "ć", "n": "ń",
          "A": "Á", "E": "É", "I": "Í", "O": "Ó", "U": "Ú"},
    "`": {"a": "à", "e": "è", "i": "ì", "o": "ò", "u": "ù",
          "A": "À", "E": "È", "O": "Ò"},
    "^": {"a": "â", "e": "ê", "i": "î", "o": "ô", "u": "û",
          "A": "Â", "E": "Ê", "O": "Ô"},
    "~": {"a": "ã", "n": "ñ", "o": "õ", "A": "Ã", "N": "Ñ", "O": "Õ"},
    '"': {"a": "ä", "e": "ë", "i": "ï", "o": "ö", "u": "ü",
          "A": "Ä", "O": "Ö", "U": "Ü"},
}
# A barra invertida e OBRIGATORIA (\\, nao \\?). Com ela opcional, "McCarthy" vira
# "M<cedilha>arthy" e "O'Brien" perde o apostrofo -- pego em TESTE, nao em revisao.
_TEX_ACENTO = re.compile(r"\\(['`^~\"])\{?([A-Za-z])\}?")
_TEX_CEDILHA = re.compile(r"\\c\s*\{?([cC])\}?")

# Formas raras que sobreviviam a primeira versao (9 de 304 autores reais medidos em
# cs.LG, 2026-09-18): caron, duplo agudo hungaro, ligaduras e letras sem ponto.
_ACENTOS["v"] = {"s": "š", "S": "Š", "c": "č", "C": "Č", "r": "ř", "R": "Ř",
                 "z": "ž", "Z": "Ž", "e": "ě", "E": "Ě", "n": "ň", "N": "Ň",
                 "t": "ť", "d": "ď", "g": "ǧ"}
_ACENTOS["k"] = {"a": "ą", "A": "Ą", "e": "ę", "E": "Ę",
                 "i": "į", "u": "ų"}
_ACENTOS["H"] = {"o": "ő", "O": "Ő", "u": "ű", "U": "Ű"}

# Comandos que NAO levam letra-argumento. Ordem importa: os de duas letras primeiro,
# senao "SS" casaria "S" e sobraria lixo.
_TEX_COMANDOS = [
    ("ae", "æ"), ("AE", "Æ"), ("oe", "œ"), ("OE", "Œ"),
    ("ss", "ß"), ("aa", "å"), ("AA", "Å"),
    ("o", "ø"), ("O", "Ø"), ("l", "ł"), ("L", "Ł"),
    ("i", "i"), ("j", "j"),
]
# _TEX_ACENTO so casa acento de PONTUACAO. Caron e duplo agudo sao comando-LETRA
# (barra + v + S, barra + H + o) e precisam de regex proprio.
_TEX_LETRA = re.compile("\\\\([vHk])\\{?([A-Za-z])\\}?")
_TEX_CMD_RE = re.compile("\\\\(" + "|".join(c for c, _ in _TEX_COMANDOS) + ")(?![A-Za-z])")
_TEX_CMD_MAP = dict(_TEX_COMANDOS)


def _desescapar_tex(texto: str) -> str:
    texto = _TEX_CEDILHA.sub(lambda m: "ç" if m.group(1) == "c" else "Ç", texto)
    texto = _TEX_ACENTO.sub(lambda m: _ACENTOS.get(m.group(1), {}).get(m.group(2), m.group(2)), texto)
    texto = _TEX_LETRA.sub(lambda m: _ACENTOS.get(m.group(1), {}).get(m.group(2), m.group(2)), texto)
    texto = _TEX_CMD_RE.sub(lambda m: _TEX_CMD_MAP[m.group(1)], texto)
    return texto.replace("\\\\", "").replace("{", "").replace("}", "")

# Os quatro tipos reais do feed, medidos em cs.LG (2026-09-18): `new` 107, `cross` 91,
# `replace` 58, `replace-cross` 48. `replace*` e REVISAO de preprint ja anunciado --
# entra no radar como repeticao. Ficamos com anuncio de verdade. Configuravel.
TIPOS_PADRAO = ("new", "cross")


def _buscar_feed(categoria: str, timeout: int) -> bytes:
    """Tenta os hosts em ordem. So levanta se TODOS falharem."""
    ultimo: Exception | None = None
    for host in RSS_HOSTS:
        try:
            return common.http_get(f"{host}/{categoria}", timeout=timeout)
        except Exception as exc:  # noqa: BLE001
            ultimo = exc
    raise ultimo if ultimo else RuntimeError(f"arXiv RSS: {categoria} sem host disponivel")


def _autores(texto: str | None) -> list[str]:
    if not texto:
        return []
    limpo = _desescapar_tex(_AFILIACAO.sub("", texto))
    return [a.strip() for a in limpo.split(",") if a.strip()]


def _parse_item(item: ET.Element, categoria: str, keywords: dict, tipos: tuple[str, ...]) -> dict | None:
    tipo = (item.findtext(f"{ARXIV_NS}announce_type") or "").strip().lower()
    if tipos and tipo and tipo not in tipos:
        return None

    title = common.strip_html(item.findtext("title") or "").replace("\n", " ").strip()
    link = (item.findtext("link") or "").strip()
    if not title or not link:
        return None

    bruto = item.findtext("description") or ""
    m = _ABSTRACT.search(bruto)
    abstract = common.strip_html(m.group(1) if m else bruto).replace("\n", " ").strip()

    guid = item.findtext("guid") or ""
    mid = _ARXIV_ID.search(bruto) or re.search(r"arXiv\.org:(\S+)", guid)
    arxiv_id = mid.group(1) if mid else guid.rsplit(":", 1)[-1]

    texto = f"{title} {abstract}"

    # O filtro de termo saiu do servidor (`abs:"termo"`) para ca. Guardamos QUAIS
    # termos casaram -- e isso que sustenta a regra do setor de que toda entrada
    # carrega o termo que a trouxe.
    termos = common.match_keywords(texto, keywords.get("arxiv_query_terms") or [])
    if not termos:
        return None

    topicos = common.match_keywords(texto, keywords.get("topics") or [])
    # uniao preservando ordem, sem duplicata
    casados = list(dict.fromkeys(termos + topicos))

    return common.Item(
        kind="article",
        title=title,
        url=link,
        source="arXiv",
        source_type="preprint",
        published_date=common.parse_date_safe(item.findtext("pubDate")),
        authors=_autores(item.findtext(f"{DC_NS}creator")),
        summary=abstract[:1200],
        doi=None,
        keywords_matched=casados,
        extra={
            "arxiv_id": arxiv_id,
            "arxiv_categoria_feed": categoria,
            "arxiv_announce_type": tipo or None,
        },
    ).to_dict()


def collect() -> list[dict]:
    sources = common.load_sources()
    cfg = sources.get("arxiv", {})
    if not cfg.get("enabled", True):
        return []

    keywords = common.load_keywords()
    categorias = keywords.get("arxiv_categories") or []
    timeout = int(cfg.get("timeout", 25))
    pausa = float(cfg.get("rss_delay_seconds", 3))
    tipos = tuple(cfg.get("announce_types", TIPOS_PADRAO))

    itens: list[dict] = []
    vistos: set[str] = set()
    falhas: list[str] = []
    ok: list[str] = []

    for i, cat in enumerate(categorias):
        if i:
            time.sleep(pausa)  # o arXiv pede cadencia; 3s e a recomendacao deles
        try:
            raw = _buscar_feed(cat, timeout)
        except Exception as exc:  # noqa: BLE001
            common.log(f"arXiv RSS: {cat} falhou -- {exc}")
            falhas.append(f"{cat} ({exc})")
            continue

        try:
            canal = ET.fromstring(raw).find("channel")
        except ET.ParseError as exc:
            common.log(f"arXiv RSS: {cat} XML invalido -- {exc}")
            falhas.append(f"{cat} (XML invalido: {exc})")
            continue
        if canal is None:
            falhas.append(f"{cat} (sem <channel>)")
            continue

        ok.append(cat)
        n_cat = 0
        for item in canal.findall("item"):
            d = _parse_item(item, cat, keywords, tipos)
            if not d:
                continue
            # Um preprint aparece em varias categorias (`cross`). Emitir uma vez.
            chave = common.dedupe_key(d)
            if chave in vistos:
                continue
            vistos.add(chave)
            itens.append(d)
            n_cat += 1
        common.log(f"arXiv RSS: {cat} -- {n_cat} preprint(s) relevante(s) de {len(canal.findall('item'))} anunciado(s).")

    # `0` deixa de ser ambiguo: feed buscado e vazio e resultado legitimo (categoria
    # pequena sem anuncio no dia); feed que NAO respondeu e ColetaParcial, com o nome
    # da categoria. Sem esta distincao, dia quieto e coletor morto tem a mesma
    # assinatura -- que foi exatamente como este defeito sobreviveu 6 execucoes.
    if falhas:
        raise common.ColetaParcial(
            f"arXiv RSS: {len(falhas)}/{len(categorias)} feed(s) falharam: " + "; ".join(falhas)
        )

    common.log(
        f"arXiv RSS: {len(itens)} preprints coletados de {len(ok)}/{len(categorias)} feed(s) "
        f"({', '.join(ok) if ok else 'nenhum'})."
    )
    return itens


if __name__ == "__main__":
    result = collect()
    print(f"Coletados: {len(result)}")
    for it in result[:5]:
        print("-", it["title"][:100])
        print("   termos:", ", ".join(it["keywords_matched"][:6]))
