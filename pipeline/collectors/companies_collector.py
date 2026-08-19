"""Coletor de empresas/instituições (pipeline/config/companies.yaml) -- página "Empresas" do
dashboard. Cada empresa usa method=rss (feed real) ou method=google_news (fallback por busca).
"""
from __future__ import annotations

from . import common, feed_collector, googlenews_collector


def _collect_one(company: dict, topics: list[str]) -> list[dict]:
    slug = company["slug"]
    name = company["name"]
    method = company.get("method", "google_news")
    filter_relevance = company.get("filter_relevance", False)
    items: list[dict] = []

    if method == "rss":
        feed_url = company.get("feed_url")
        try:
            entries = feed_collector.fetch_feed(feed_url)
        except Exception as exc:  # noqa: BLE001
            common.log(f"Empresa '{name}': RSS falhou -- {exc}")
            entries = []
        for e in entries:
            hits = common.match_keywords(f"{e['title']} {e['summary']}", topics)
            if filter_relevance and not hits:
                continue
            items.append(
                common.Item(
                    kind="news",
                    title=e["title"],
                    url=e["url"],
                    source=name,
                    source_type="company_blog",
                    published_date=e["published_date"],
                    summary=e["summary"],
                    company_slug=slug,
                    keywords_matched=hits,
                ).to_dict()
            )
    else:
        query = company.get("query", f'"{name}"')
        hl_gl = company.get("hl_gl", {"hl": "en-US", "gl": "US", "ceid": "US:en"})
        try:
            entries = googlenews_collector.fetch_query(
                query, hl_gl.get("hl", "en-US"), hl_gl.get("gl", "US"), hl_gl.get("ceid", "US:en")
            )
        except Exception as exc:  # noqa: BLE001
            common.log(f"Empresa '{name}': Google News falhou -- {exc}")
            entries = []
        for e in entries:
            hits = common.match_keywords(f"{e['title']} {e['summary']}", topics)
            if filter_relevance and not hits:
                continue
            items.append(
                common.Item(
                    kind="news",
                    title=e["title"],
                    url=e["url"],
                    source=e["outlet"],
                    source_type="press",
                    published_date=e["published_date"],
                    summary=e["summary"],
                    company_slug=slug,
                    keywords_matched=hits or [name],
                    extra={"query": query, "via": "google_news"},
                ).to_dict()
            )
    return items


def collect() -> list[dict]:
    companies = common.load_companies()
    topics = common.load_keywords()["topics"]
    all_items: list[dict] = []
    for company in companies:
        common.log(f"Empresa '{company['name']}' ({company.get('method')})...")
        try:
            items = _collect_one(company, topics)
        except Exception as exc:  # noqa: BLE001
            common.log(f"Empresa '{company['name']}': falhou por completo -- {exc}")
            items = []
        common.log(f"  -> {len(items)} itens")
        all_items.extend(items)
    common.log(f"Empresas: {len(all_items)} itens no total, {len(companies)} empresas.")
    return all_items


if __name__ == "__main__":
    result = collect()
    print(f"Coletados: {len(result)}")
    for it in result[:10]:
        print("-", it["company_slug"], "|", it["title"][:80])
