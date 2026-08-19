"""Coletor SciELO -- via proxy Crossref (prefixo DOI 10.1590, SciELO Brasil).

search.scielo.org responde 403 diretamente nesta rede (confirmado ao vivo, ver spec 2026-08-17).
Usamos o mesmo proxy Crossref do ChemRxiv, com uma query textual (Crossref suporta `query=` além
do filtro de prefixo) para reduzir ruído antes mesmo do filtro local de keywords -- o prefixo
10.1590 cobre TODAS as revistas SciELO Brasil (todas as áreas), não só saúde/química.
"""
from __future__ import annotations

from . import common


def collect() -> list[dict]:
    sources = common.load_sources()
    cfg = sources.get("scielo_via_crossref", {})
    if not cfg.get("enabled", True):
        return []
    topics = common.load_keywords()["topics"]

    base_url = cfg["base_url"]
    doi_prefix = cfg["doi_prefix"]
    rows = int(cfg.get("rows", 60))
    window_days = int(cfg.get("window_days", 200))
    filter_relevance = cfg.get("filter_relevance", True)
    query = cfg.get("crossref_query")

    common.log(f"SciELO (via Crossref, prefixo {doi_prefix}): buscando {rows} itens recentes...")
    try:
        entries = common.crossref_works_by_prefix(
            base_url, doi_prefix, rows, query=query, days_back=window_days
        )
    except Exception as exc:  # noqa: BLE001
        common.log(f"SciELO/Crossref: falhou -- {exc}")
        return []

    items: list[dict] = []
    for entry in entries:
        parsed = common.crossref_item_to_dict(entry, source="SciELO", source_type="journal", topics=topics)
        if not parsed:
            continue
        if filter_relevance and not parsed["keywords_matched"]:
            continue
        items.append(parsed)

    common.log(f"SciELO: {len(entries)} obras varridas, {len(items)} relevantes ao nicho.")
    return items


if __name__ == "__main__":
    result = collect()
    print(f"Coletados: {len(result)}")
    for it in result[:5]:
        print("-", it["title"][:100])
