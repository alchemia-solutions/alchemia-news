"""Coletor arXiv -- preprints em categorias q-bio relevantes, via API Atom pública."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from urllib.parse import quote

from . import common

ATOM_NS = "{http://www.w3.org/2005/Atom}"


def _build_query(categories: list[str], terms: list[str]) -> str:
    cat_clause = " OR ".join(f"cat:{c}" for c in categories)
    term_clause = " OR ".join(f'abs:"{t}"' for t in terms)
    return f"({cat_clause}) AND ({term_clause})"


def collect() -> list[dict]:
    sources = common.load_sources()
    cfg = sources.get("arxiv", {})
    if not cfg.get("enabled", True):
        return []
    keywords = common.load_keywords()
    base_url = cfg["base_url"]
    max_results = int(cfg.get("max_results", 60))
    window_days = int(cfg.get("window_days", 200))

    query = _build_query(keywords["arxiv_categories"], keywords["arxiv_query_terms"])
    url = (
        f"{base_url}?search_query={quote(query)}&sortBy=submittedDate&sortOrder=descending"
        f"&max_results={max_results}"
    )
    common.log(f"arXiv: consultando ({max_results} resultados max)...")
    try:
        raw = common.http_get(url, timeout=25)
    except Exception as exc:  # noqa: BLE001
        # 2026-08-31: era `return []` -- a falha ficava so no log e `meta.json` gravava
        # `count: 0, error: null` (zero silencioso, invisivel para o alarme e para a faixa
        # do dashboard, que olham o campo `error`). Ver `common.ColetaParcial`.
        common.log(f"arXiv: falhou -- {exc}")
        raise common.ColetaParcial(f"arXiv: falhou -- {exc}") from exc

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        common.log(f"arXiv: XML inválido -- {exc}")
        return []

    items: list[dict] = []
    for entry in root.findall(f"{ATOM_NS}entry"):
        title = (entry.findtext(f"{ATOM_NS}title") or "").strip()
        summary = (entry.findtext(f"{ATOM_NS}summary") or "").strip()
        published_raw = entry.findtext(f"{ATOM_NS}published") or ""
        published = common.parse_date_safe(published_raw)
        if not common.within_window(published, window_days):
            continue
        link = ""
        for link_el in entry.findall(f"{ATOM_NS}link"):
            if link_el.get("rel") == "alternate" or link_el.get("type") == "text/html":
                link = link_el.get("href", "")
                break
        if not link:
            link = entry.findtext(f"{ATOM_NS}id") or ""
        authors = [
            (a.findtext(f"{ATOM_NS}name") or "").strip()
            for a in entry.findall(f"{ATOM_NS}author")
        ]
        arxiv_id = (entry.findtext(f"{ATOM_NS}id") or "").rsplit("/", 1)[-1]
        hits = common.match_keywords(f"{title} {summary}", keywords["topics"])
        items.append(
            common.Item(
                kind="article",
                title=common.strip_html(title).replace("\n", " "),
                url=link,
                source="arXiv",
                source_type="preprint",
                published_date=published,
                authors=[a for a in authors if a],
                summary=common.strip_html(summary)[:1200],
                doi=None,
                keywords_matched=hits,
                extra={"arxiv_id": arxiv_id},
            ).to_dict()
        )

    common.log(f"arXiv: {len(items)} preprints coletados.")
    return items


if __name__ == "__main__":
    result = collect()
    print(f"Coletados: {len(result)}")
    for it in result[:5]:
        print("-", it["title"][:100])
