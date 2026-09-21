"""Coletor bioRxiv -- preprints recentes filtrados no cliente pelas keywords do nicho.

A API pública do bioRxiv (api.biorxiv.org) não aceita busca por palavra-chave -- só paginação por
intervalo de datas em TODAS as categorias de biologia. Por isso paginamos uma janela curta
(incremental_days, default 3) a cada execução (roda 3x/dia) e filtramos client-side. Um backfill
mais profundo (default_backfill_days) pode ser pedido explicitamente via --biorxiv-days.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from . import common


def _fetch_page(base_url: str, start: str, end: str, cursor: int) -> dict:
    url = f"{base_url}/{start}/{end}/{cursor}"
    return common.http_get_json(url)


def collect(days_override: int | None = None) -> list[dict]:
    sources = common.load_sources()
    cfg = sources.get("biorxiv", {})
    if not cfg.get("enabled", True):
        return []
    keywords = common.load_keywords()["topics"]

    days = days_override or int(cfg.get("incremental_days", 3))
    base_url = cfg["base_url"]
    max_pages = int(cfg.get("max_pages", 60))

    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=days)
    start = start_dt.strftime("%Y-%m-%d")
    end = end_dt.strftime("%Y-%m-%d")

    common.log(f"bioRxiv: paginando {start}..{end} (max {max_pages} páginas de ~30)...")

    items: list[dict] = []
    cursor = 0
    total_seen = 0
    pagina = 30          # tamanho real da pagina, confirmado na primeira resposta
    total_api: int | None = None   # a API DIZ quantos existem -- usar isso em vez de chutar
    pulados: list[str] = []

    for page in range(max_pages):
        try:
            data = _fetch_page(base_url, start, end, cursor)
        except Exception as exc:  # noqa: BLE001
            # Antes de 2026-08-31 isto era um `break` -- a falha ficava só no log e `meta.json`
            # gravava `count: 0, error: null`. Medido nas 47 execuções de `pipeline/data/runs/`:
            # aconteceu 3x de verdade (timeout em 21/08 09:41Z, HTTP 500 em 21/08 21:40Z,
            # conexão recusada em 27/08 11:17Z) e NENHUMA das três gerou aviso, porque o alarme
            # e a faixa do dashboard olham o campo `error`. Sobe como ColetaParcial: preserva o
            # que as páginas anteriores já trouxeram e registra a falha honestamente.
            # 2026-09-18: antes isto ABORTAVA a coleta inteira. Medido no incidente de
            # 2026-09-18: 25 paginas tinham passado (750 de 1043 na janela) e uma falha
            # transitoria no cursor=750 descartou as ~10 paginas restantes. `http_get_json`
            # ja tentou 3x antes de chegar aqui, entao insistir na mesma pagina nao ajuda --
            # o certo e PULAR o bloco e seguir. Custo de uma pagina ruim cai de "um terco da
            # janela" para "30 preprints".
            common.log(f"bioRxiv: página cursor={cursor} falhou, pulando -- {exc}")
            pulados.append(f"cursor={cursor} ({exc})")
            cursor += pagina
            if total_api is not None and cursor >= total_api:
                break
            continue
        messages = data.get("messages", [{}])
        status = messages[0].get("status", "") if messages else ""
        collection = data.get("collection", [])
        if not collection:
            break
        if total_api is None:
            # A API devolve `total` em `messages[0]` e o coletor ignorava. Sem isso o laco
            # depende de `max_pages` (60 = 1800 itens) para uma janela que tem ~1000.
            try:
                total_api = int(messages[0].get("total") or 0) or None
            except (TypeError, ValueError):
                total_api = None
            pagina = len(collection) or pagina
            if total_api:
                common.log(f"bioRxiv: a API declara {total_api} preprints na janela "
                           f"(~{-(-total_api // pagina)} páginas de {pagina}).")
        total_seen += len(collection)
        for entry in collection:
            title = entry.get("title", "")
            abstract = entry.get("abstract", "")
            haystack = f"{title} {abstract}"
            hits = common.match_keywords(haystack, keywords)
            if not hits:
                continue
            doi = entry.get("doi")
            items.append(
                common.Item(
                    kind="article",
                    title=common.strip_html(title),
                    url=f"https://doi.org/{doi}" if doi else "",
                    source="bioRxiv",
                    source_type="preprint",
                    published_date=common.parse_date_safe(entry.get("date")),
                    authors=[a.strip() for a in (entry.get("authors") or "").split(";") if a.strip()],
                    summary=common.strip_html(abstract)[:1200],
                    doi=doi,
                    keywords_matched=hits,
                    extra={"category": entry.get("category", "")},
                ).to_dict()
            )
        if "ok" not in status.lower() and page > 0:
            pass  # bioRxiv retorna status por página; seguimos até vir vazio
        # Bug corrigido em 2026-08-17: a API pagina em blocos de 30 itens (verificado ao vivo),
        # não 100 como assumido originalmente. O cursor precisa avançar pelo tamanho real da
        # página retornada, e o corte de "última página" é por coleção vazia, não por um
        # tamanho fixo -- do contrário a paginação para depois da primeira página (30 itens)
        # mesmo com milhares de preprints na janela, o que produzia falsos "0 relevantes".
        cursor += len(collection)
        if total_api is not None and cursor >= total_api:
            break

    resultado = [it for it in items if it["url"]]
    common.log(
        f"bioRxiv: {total_seen} preprints varridos"
        + (f" de {total_api} declarados" if total_api else "")
        + f", {len(resultado)} relevantes ao nicho."
        + (f" {len(pulados)} página(s) pulada(s)." if pulados else "")
    )
    # Pagina pulada NAO e silenciosa: sobe como ColetaParcial COM os itens que deram certo,
    # entao `run_all` aproveita a colheita boa e `meta.json` registra o buraco.
    if pulados:
        raise common.ColetaParcial(
            f"bioRxiv: {len(pulados)} página(s) pulada(s) de {page + 1} tentadas "
            f"({total_seen} preprints varridos): " + "; ".join(pulados),
            resultado,
        )
    return resultado


if __name__ == "__main__":
    result = collect()
    print(f"Coletados: {len(result)}")
    for it in result[:5]:
        print("-", it["title"][:100])
