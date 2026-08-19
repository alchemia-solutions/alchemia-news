"""Coletor PubMed (NCBI E-utils) -- artigos publicados nos últimos ~6 meses no nicho de CADD/AI
Drug Discovery. Usa esearch (busca IDs) + efetch (metadado XML), API pública, sem chave
obrigatória -- identificamos com tool/email educados no User-Agent e nos parâmetros, respeitando
o rate limit recomendado (sem chave: até ~3 req/s; usamos bem menos que isso).
"""
from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from urllib.parse import quote

from . import common


def _esearch(base_url: str, query: str, reldate_days: int, retmax: int) -> list[str]:
    url = (
        f"{base_url}/esearch.fcgi?db=pubmed&retmode=json&retmax={retmax}"
        f"&datetype=pdat&reldate={reldate_days}&term={quote(query)}"
        f"&tool=AlchemiaNewsBot&email=company%40alchemia.solutions"
    )
    data = common.http_get_json(url)
    return data.get("esearchresult", {}).get("idlist", [])


def _efetch(base_url: str, pmids: list[str]) -> bytes:
    ids = ",".join(pmids)
    url = (
        f"{base_url}/efetch.fcgi?db=pubmed&retmode=xml&id={ids}"
        f"&tool=AlchemiaNewsBot&email=company%40alchemia.solutions"
    )
    return common.http_get(url, timeout=30)


def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return "".join(el.itertext()).strip()


def _parse_article(article_el: ET.Element, topics: list[str] | None = None) -> dict | None:
    medline = article_el.find("MedlineCitation")
    if medline is None:
        return None
    pmid_el = medline.find("PMID")
    pmid = _text(pmid_el)
    art = medline.find("Article")
    if art is None:
        return None
    title = _text(art.find("ArticleTitle"))
    if not title:
        return None

    abstract_parts = [
        _text(t) for t in art.findall("Abstract/AbstractText")
    ]
    summary = " ".join(p for p in abstract_parts if p)

    journal = _text(art.find("Journal/Title")) or _text(art.find("Journal/ISOAbbreviation"))

    authors = []
    for author in art.findall("AuthorList/Author"):
        last = _text(author.find("LastName"))
        fore = _text(author.find("ForeName")) or _text(author.find("Initials"))
        if last:
            authors.append(f"{fore} {last}".strip())

    pub_date_el = art.find("Journal/JournalIssue/PubDate")
    year = _text(pub_date_el.find("Year")) if pub_date_el is not None else ""
    month = _text(pub_date_el.find("Month")) if pub_date_el is not None else ""
    day = _text(pub_date_el.find("Day")) if pub_date_el is not None else ""
    raw_date = " ".join(p for p in (year, month, day) if p)
    published = common.parse_date_safe(raw_date) or common.parse_date_safe(year)

    doi = None
    for eid in article_el.findall("PubmedData/ArticleIdList/ArticleId"):
        if eid.get("IdType") == "doi":
            doi = _text(eid)

    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else (f"https://doi.org/{doi}" if doi else "")
    if not url:
        return None

    # Proveniência do termo (adicionado em 2026-08-18). A `pubmed_query` já é do nicho, então o
    # PubMed não precisa de filtro de relevância no cliente — mas por isso mesmo os itens dele
    # eram os ÚNICOS a chegar com `keywords_matched` vazio, e a spec deste setor exige que "toda
    # entrada carregue o termo que a trouxe". Sem isso, um artigo de PubMed no radar não tem como
    # ser justificado a posteriori: quem lê não sabe se entrou por docking, por ADMET ou por acaso.
    # Casar os tópicos contra título+resumo não filtra nada (nenhum item é descartado por não
    # casar) — só devolve a rastreabilidade que faltava.
    hits = common.match_keywords(f"{title} {summary}", topics or [])

    return common.Item(
        kind="article",
        title=title,
        url=url,
        source="PubMed",
        source_type="journal",
        published_date=published,
        authors=authors,
        summary=summary,
        doi=doi,
        keywords_matched=hits,
        extra={"pmid": pmid, "journal": journal},
    ).to_dict()


def collect() -> list[dict]:
    sources = common.load_sources()
    cfg = sources.get("pubmed", {})
    if not cfg.get("enabled", True):
        return []
    keywords = common.load_keywords()
    query = keywords["pubmed_query"]
    topics = keywords.get("topics") or []
    base_url = cfg["base_url"]
    reldate_days = int(cfg.get("reldate_days", 200))
    retmax = int(cfg.get("retmax", 60))

    common.log(f"PubMed: buscando IDs (janela {reldate_days}d, retmax={retmax})...")
    try:
        pmids = _esearch(base_url, query, reldate_days, retmax)
    except Exception as exc:  # noqa: BLE001
        common.log(f"PubMed: esearch falhou -- {exc}")
        return []

    if not pmids:
        common.log("PubMed: nenhum ID retornado.")
        return []

    common.log(f"PubMed: {len(pmids)} IDs encontrados, buscando metadado...")
    items: list[dict] = []
    batch_size = 20
    for i in range(0, len(pmids), batch_size):
        batch = pmids[i : i + batch_size]
        try:
            raw = _efetch(base_url, batch)
            root = ET.fromstring(raw)
        except Exception as exc:  # noqa: BLE001
            common.log(f"PubMed: efetch/parse falhou para lote {i}-{i+batch_size} -- {exc}")
            continue
        for article_el in root.findall("PubmedArticle"):
            parsed = _parse_article(article_el, topics)
            if parsed:
                items.append(parsed)
        time.sleep(0.4)  # gentileza com o rate limit da NCBI sem api_key

    common.log(f"PubMed: {len(items)} artigos normalizados.")
    return items


if __name__ == "__main__":
    result = collect()
    print(f"Coletados: {len(result)}")
    for it in result[:5]:
        print("-", it["title"][:100])
