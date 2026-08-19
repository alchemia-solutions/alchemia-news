"""Coletor ChemRxiv -- via proxy Crossref (prefixo DOI 10.26434, Cambridge Open Engage).

O endpoint público v1 do ChemRxiv (chemrxiv.org/engage/.../public-api/v1/items) responde 403
diretamente nesta rede -- confirmado ao vivo nesta empresa (ver spec 2026-08-17). O Crossref
indexa normalmente os DOIs do ChemRxiv, então usamos a busca por prefixo de editora como fonte
real de metadado (título, autores, resumo, data de criação) sem depender do endpoint bloqueado.
"""
from __future__ import annotations

from . import common


def collect() -> list[dict]:
    sources = common.load_sources()
    cfg = sources.get("chemrxiv_via_crossref", {})
    if not cfg.get("enabled", True):
        return []
    topics = common.load_keywords()["topics"]

    base_url = cfg["base_url"]
    doi_prefix = cfg["doi_prefix"]
    rows = int(cfg.get("rows", 60))
    window_days = int(cfg.get("window_days", 200))
    filter_relevance = cfg.get("filter_relevance", True)

    common.log(f"ChemRxiv (via Crossref, prefixo {doi_prefix}): buscando {rows} itens recentes...")
    try:
        entries = common.crossref_works_by_prefix(base_url, doi_prefix, rows, days_back=window_days)
    except Exception as exc:  # noqa: BLE001
        common.log(f"ChemRxiv/Crossref: falhou -- {exc}")
        return []

    items: list[dict] = []
    for entry in entries:
        parsed = common.crossref_item_to_dict(entry, source="ChemRxiv", source_type="preprint", topics=topics)
        if not parsed:
            continue
        if filter_relevance and not parsed["keywords_matched"]:
            continue
        items.append(parsed)

    common.log(f"ChemRxiv: {len(entries)} obras varridas, {len(items)} relevantes ao nicho.")
    return items


if __name__ == "__main__":
    result = collect()
    print(f"Coletados: {len(result)}")
    for it in result[:5]:
        print("-", it["title"][:100])
