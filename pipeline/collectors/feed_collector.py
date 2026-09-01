"""Coletor de feeds RSS/Atom (Nature, empresas com feed real, etc). Parser próprio via
xml.etree -- evita depender de feedparser cravar formatos exóticos; feedparser fica como
fallback opcional para feeds malformados (chamado só se o parse manual falhar).
"""
from __future__ import annotations

import time
import xml.etree.ElementTree as ET

from . import common

_ATOM_NS = "{http://www.w3.org/2005/Atom}"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _texto(el) -> str:
    """Todo o texto do elemento, inclusive o que está dentro de filhos.

    `el.text` sozinho não basta: alguns feeds trazem markup ANINHADO dentro do <title> (o do
    Fierce Biotech, medido em 2026-08-18, tem um elemento filho dentro do título, deixando
    `el.text` vazio). Com `el.text`, os 25 itens daquele feed eram descartados por "título
    vazio" — 0 itens coletados, sem erro. Mesmo padrão de falha silenciosa do desafio anti-bot.
    """
    if el is None:
        return ""
    return "".join(el.itertext()).strip()


def _parse_rss2(root: ET.Element) -> list[dict]:
    """Cobre RSS 2.0 (item sob channel) e RSS 1.0/RDF (item como filho direto da raiz, ex. Nature)."""
    out = []
    candidates = [el for el in root.iter() if _local(el.tag) == "item"]
    for item in candidates:
        title = ""
        link = ""
        pub_date = ""
        description = ""
        for child in item:
            local = _local(child.tag)
            text = _texto(child)
            if local == "title" and not title:
                title = text
            elif local == "link" and not link:
                link = text or child.get("resource", "") or child.get(
                    "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource", ""
                )
            elif local in ("pubDate", "date") and not pub_date:
                pub_date = text
            elif local == "description" and not description:
                description = text
        if not link:
            link = item.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about", "")
        if not title or not link:
            continue
        out.append(
            {
                "title": title,
                "url": link,
                "published_date": common.parse_date_safe(pub_date),
                "summary": common.strip_html(description)[:1200],
            }
        )
    return out


def _parse_atom(root: ET.Element) -> list[dict]:
    out = []
    for entry in root.findall(f"{_ATOM_NS}entry"):
        title = _texto(entry.find(f"{_ATOM_NS}title"))
        link = ""
        for link_el in entry.findall(f"{_ATOM_NS}link"):
            if link_el.get("rel") in (None, "alternate"):
                link = link_el.get("href", "")
                break
        updated = _texto(entry.find(f"{_ATOM_NS}updated")) or _texto(entry.find(f"{_ATOM_NS}published"))
        summary = _texto(entry.find(f"{_ATOM_NS}summary")) or _texto(entry.find(f"{_ATOM_NS}content"))
        if not title or not link:
            continue
        out.append(
            {
                "title": title,
                "url": link,
                "published_date": common.parse_date_safe(updated),
                "summary": common.strip_html(summary)[:1200],
            }
        )
    return out


# Assinaturas de página anti-bot / interstitial. Um desafio desses volta **HTTP 200 com HTML** —
# o `http_get` não acusa nada, `ET.fromstring` quebra, o fallback do feedparser acha 0 entradas, e
# o coletor reporta `count: 0, error: null`. Foi exatamente o que aconteceu com os dois feeds da
# Nature em 2026-08-18 (38 -> 8 -> 0 ao longo do dia, sem um único erro registrado). Zero silencioso
# é pior que erro: a rotina do Baker é instruída a investigar `error`, e nunca via nenhum.
_DESAFIO_BOT = (
    b"Client Challenge",
    b"Just a moment...",
    b"Checking your browser",
    b"cf-browser-verification",
    b"Attention Required! | Cloudflare",
    b"Access Denied",
)


class FeedIndisponivel(RuntimeError):
    """O endpoint respondeu, mas não com um feed — bloqueio anti-bot, HTML, ou corpo vazio."""


# `ColetaParcial` nasceu aqui em 2026-08-31 (para a seção Nature) e no mesmo dia foi PROMOVIDA
# para `common`, ao se medir que o mesmo zero-silencioso existia em bioRxiv/arXiv/ChemRxiv/
# SciELO/PubMed — ver o docstring dela em `common.py`. Este alias mantém válido todo código e
# toda documentação que a chamam de `feed_collector.ColetaParcial`: é a MESMA classe, não uma
# cópia, então `isinstance` continua correto nos dois nomes.
ColetaParcial = common.ColetaParcial


def fetch_feed(url: str) -> list[dict]:
    raw = common.http_get(url, timeout=20)

    for marca in _DESAFIO_BOT:
        if marca in raw[:4000]:
            raise FeedIndisponivel(
                f"resposta é uma página anti-bot ({marca.decode('utf-8', 'replace')}), não um feed"
            )

    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        entradas = _fallback_feedparser(url)
        if not entradas:
            # Sem isto, HTML qualquer (página de erro, redirect logado, layout novo) vira "0 itens,
            # tudo bem". Distinguimos "feed válido e vazio" de "não é feed" pelo corpo bruto.
            corpo = raw[:2000].lstrip().lower()
            if corpo.startswith(b"<!doctype html") or corpo.startswith(b"<html"):
                raise FeedIndisponivel("resposta é HTML, não XML de feed") from None
            if not raw.strip():
                raise FeedIndisponivel("resposta vazia") from None
        return entradas

    tag = root.tag.lower()
    if tag.endswith("feed"):
        return _parse_atom(root)
    return _parse_rss2(root)


def _fallback_feedparser(url: str) -> list[dict]:
    try:
        import feedparser  # type: ignore
    except ImportError:
        return []
    parsed = feedparser.parse(url)
    out = []
    for entry in parsed.entries:
        title = getattr(entry, "title", "")
        link = getattr(entry, "link", "")
        if not title or not link:
            continue
        published = getattr(entry, "published", "") or getattr(entry, "updated", "")
        summary = getattr(entry, "summary", "")
        out.append(
            {
                "title": title,
                "url": link,
                "published_date": common.parse_date_safe(published),
                "summary": common.strip_html(summary)[:1200],
            }
        )
    return out


def _collect_section(secao: str, source_type_padrao: str) -> list[dict]:
    """Coleta uma seção de feeds do `sources.yaml`. Compartilhada por Nature e newsletters.

    Cada feed pode sobrescrever `filter_relevance` e `source_type` individualmente — um feed
    temático do nicho (Nature Reviews Drug Discovery, Drug Hunter) não precisa de filtro; um feed
    generalista (NVIDIA, Fierce Biotech, BioPharma Dive) precisa, senão inunda a base com conteúdo
    fora do nicho.

    **Falha de feed é reportada, nunca engolida.** Se algum feed da seção falhar, a exceção sobe
    depois de todos serem tentados — assim `meta.json` registra `error` de verdade em vez de um
    `count: 0` silencioso, e os feeds que funcionaram nesta rodada não são perdidos.
    """
    sources = common.load_sources()
    cfg = sources.get(secao, {})
    if not cfg.get("enabled", True):
        return []
    topics = common.load_keywords()["topics"]
    filtro_padrao = cfg.get("filter_relevance", False)
    # Espaçamento entre feeds do MESMO host. Sem isso, N feeds de nature.com em rajada disparam o
    # desafio anti-bot — causa provável da queda 38 -> 8 -> 0 observada em 2026-08-18.
    pausa = float(cfg.get("delay_seconds", 1.5))
    janela_padrao = int(cfg.get("window_days", 0))  # 0 = sem janela (feed de periódico)

    items: list[dict] = []
    falhas: list[str] = []
    feeds = cfg.get("feeds", [])

    for i, feed in enumerate(feeds):
        name = feed["name"]
        url = feed["url"]
        if i:
            time.sleep(pausa)
        common.log(f"Feed '{name}': buscando {url} ...")
        try:
            entries = fetch_feed(url)
        except Exception as exc:  # noqa: BLE001
            common.log(f"Feed '{name}': FALHOU -- {exc}")
            falhas.append(f"{name}: {exc}")
            continue

        filtrar = feed.get("filter_relevance", filtro_padrao)
        janela = int(feed.get("window_days", janela_padrao))
        antes = len(items)
        descartados_janela = 0
        for e in entries:
            # Janela de data. Feeds de periódico devolvem ~10-40 itens recentes, mas feed de
            # newsletter frequentemente serve o ARQUIVO INTEIRO: medido em 2026-08-18,
            # Longevity.Technology devolveu 1.500 entradas e Drug Hunter 284 numa única chamada —
            # sem janela, a primeira execução dobraria a base de notícias com conteúdo antigo.
            # `within_window` NÃO descarta item sem data (deixa outro filtro decidir), então isso
            # não perde conteúdo cuja fonte simplesmente não datou.
            if janela and not common.within_window(e["published_date"], janela):
                descartados_janela += 1
                continue
            hits = common.match_keywords(f"{e['title']} {e['summary']}", topics)
            if filtrar and not hits:
                continue
            items.append(
                common.Item(
                    kind="news",
                    title=e["title"],
                    url=e["url"],
                    source=name,
                    source_type=feed.get("source_type", source_type_padrao),
                    published_date=e["published_date"],
                    summary=e["summary"],
                    keywords_matched=hits,
                ).to_dict()
            )
        common.log(
            f"Feed '{name}': {len(entries)} entradas, {len(items) - antes} relevantes"
            + (f", {descartados_janela} fora da janela de {janela}d." if descartados_janela else ".")
        )

    if falhas:
        # Sobe COM os itens já coletados: o erro precisa aparecer em meta.json (nunca um zero
        # silencioso), mas os feeds que responderam não podem ser perdidos por causa dos que não.
        raise ColetaParcial(
            f"{len(falhas)}/{len(feeds)} feed(s) de '{secao}' falharam: " + " | ".join(falhas),
            items,
        )
    return items


def collect_nature_feeds() -> list[dict]:
    return _collect_section("nature_feeds", "journal")


def collect_newsletter_feeds() -> list[dict]:
    """Newsletters e veículos editoriais do nicho (Drug Hunter, Longevity.Technology, etc)."""
    return _collect_section("newsletter_feeds", "newsletter")


if __name__ == "__main__":
    for fn in (collect_nature_feeds, collect_newsletter_feeds):
        try:
            result = fn()
        except Exception as exc:  # noqa: BLE001
            print(f"{fn.__name__}: ERRO -- {exc}")
            continue
        print(f"{fn.__name__}: {len(result)} itens")
        for it in result[:5]:
            print("  -", it["source"], "|", it["title"][:80])
