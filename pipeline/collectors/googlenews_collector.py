"""Coletor Google News (RSS) -- usado para (1) rotação de queries genéricas do nicho e (2)
fallback por empresa quando ela não expõe RSS estável próprio. Uso "melhor esforço" -- ver
spec 2026-08-17, risco 1: Google não documenta SLA público para este endpoint; uma falha aqui
nunca derruba o pipeline inteiro (outros coletores continuam).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from urllib.parse import quote

from . import common


def _query_url(query: str, hl: str, gl: str, ceid: str) -> str:
    return f"https://news.google.com/rss/search?q={quote(query)}&hl={hl}&gl={gl}&ceid={ceid}"


def fetch_query(query: str, hl: str = "en-US", gl: str = "US", ceid: str = "US:en") -> list[dict]:
    url = _query_url(query, hl, gl, ceid)
    raw = common.http_get(url, timeout=20)
    root = ET.fromstring(raw)
    channel = root.find("channel")
    if channel is None:
        return []
    out = []
    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = item.findtext("pubDate") or ""
        source_el = item.find("source")
        outlet = source_el.text.strip() if source_el is not None and source_el.text else "Google News"
        description = item.findtext("description") or ""
        if not title or not link:
            continue
        out.append(
            {
                "title": title,
                "url": link,
                "published_date": common.parse_date_safe(pub_date),
                "summary": common.strip_html(description)[:600],
                "outlet": outlet,
            }
        )
    return out


def collect_general() -> list[dict]:
    """Rotação de queries genéricas do nicho (não ligadas a uma empresa), en + pt-BR."""
    sources = common.load_sources()
    cfg = sources.get("google_news_general", {})
    if not cfg.get("enabled", True):
        return []
    keywords = common.load_keywords()

    items: list[dict] = []
    for combo in cfg.get("hl_gl", []):
        query_set_name = combo["query_set"]
        queries = keywords.get(query_set_name, [])
        for query in queries:
            common.log(f"Google News ({combo['hl']}): '{query}'...")
            try:
                entries = fetch_query(query, combo["hl"], combo["gl"], combo["ceid"])
            except Exception as exc:  # noqa: BLE001
                common.log(f"Google News: query '{query}' falhou -- {exc}")
                continue
            for e in entries:
                items.append(
                    common.Item(
                        kind="news",
                        title=e["title"],
                        url=e["url"],
                        source=e["outlet"],
                        source_type="news",
                        published_date=e["published_date"],
                        summary=e["summary"],
                        keywords_matched=[query.strip('"')],
                        extra={"query": query, "via": "google_news"},
                    ).to_dict()
                )
    common.log(f"Google News (geral): {len(items)} itens coletados.")
    return items


if __name__ == "__main__":
    result = collect_general()
    print(f"Coletados: {len(result)}")
    for it in result[:8]:
        print("-", it["title"][:100], "|", it["source"])
