#!/usr/bin/env python
"""Orquestrador do pipeline Alchemia News. Roda todos os coletores, funde com o estado
persistido (dedupe por DOI/URL), grava os JSONs consumidos pelo dashboard, e produz um snapshot
de execução para auditoria (o que rodou, quanto tempo levou, quantos itens novos).

Uso:
    python -m pipeline.run_all                  # execução incremental normal (chamada pelo cron)
    python -m pipeline.run_all --biorxiv-days 60 # backfill bioRxiv mais profundo, sob demanda
    python -m pipeline.run_all --skip companies,scielo   # pula coletores específicos (debug)
"""
from __future__ import annotations

import argparse
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Aponta para o próprio diretório `pipeline/` (onde `collectors/` vive), não para o pai.
# Com `.parent.parent` o import abaixo só funcionava ao invocar o arquivo por caminho
# (`python pipeline/run_all.py`, que já põe `pipeline/` no sys.path) e quebrava no modo
# documentado no docstring acima (`python -m pipeline.run_all`) com ModuleNotFoundError.
# Corrigido em 2026-08-17, ao ligar o cron do Hermes — que invoca justamente pelo modo -m.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from collectors import (  # noqa: E402
    arxiv_collector,
    biorxiv_collector,
    chemrxiv_collector,
    common,
    companies_collector,
    feed_collector,
    googlenews_collector,
    pubmed_collector,
    scielo_collector,
)

DATA_DIR = common.DATA_DIR
NEWS_PATH = DATA_DIR / "news.json"
ARTICLES_PATH = DATA_DIR / "articles.json"
COMPANIES_ACTIVITY_PATH = DATA_DIR / "companies_activity.json"
META_PATH = DATA_DIR / "meta.json"


def _run_collector(name: str, fn, *args, **kwargs) -> tuple[list[dict], float, str | None]:
    start = time.time()
    error = None
    try:
        items = fn(*args, **kwargs)
    except Exception:  # noqa: BLE001
        # Sanitizado antes de logar/retornar -- este `error` acaba em meta.json/
        # pipeline/data/runs/*.json, que são commitados de propósito (auditoria), e o
        # repositório é público. Ver common.sanitize_local_path.
        error = common.sanitize_local_path(traceback.format_exc(limit=4))
        common.log(f"[{name}] FALHOU:\n{error}")
        items = []
    elapsed = time.time() - start
    common.log(f"[{name}] {len(items)} itens em {elapsed:.1f}s")
    return items, elapsed, error


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline de coleta Alchemia News")
    parser.add_argument("--biorxiv-days", type=int, default=None, help="Backfill bioRxiv em dias (default: incremental_days do sources.yaml)")
    parser.add_argument(
        "--skip",
        type=str,
        default="",
        help="Lista separada por vírgula de coletores a pular (pubmed,biorxiv,arxiv,chemrxiv,scielo,nature,newsletters,googlenews,companies)",
    )
    args = parser.parse_args()
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}

    run_started = datetime.now(timezone.utc)
    common.log(f"===== Alchemia News pipeline: iniciando execução ({run_started.isoformat()}) =====")

    collector_results: dict[str, dict] = {}
    article_items: list[dict] = []
    news_items: list[dict] = []
    company_items: list[dict] = []

    def maybe_run(key: str, label: str, fn, *fn_args, bucket: list[dict], **fn_kwargs):
        if key in skip:
            common.log(f"[{label}] pulado (--skip)")
            collector_results[key] = {"skipped": True}
            return
        items, elapsed, error = _run_collector(label, fn, *fn_args, **fn_kwargs)
        bucket.extend(items)
        collector_results[key] = {"count": len(items), "seconds": round(elapsed, 1), "error": error}

    maybe_run("pubmed", "PubMed", pubmed_collector.collect, bucket=article_items)
    maybe_run(
        "biorxiv",
        "bioRxiv",
        biorxiv_collector.collect,
        days_override=args.biorxiv_days,
        bucket=article_items,
    )
    maybe_run("arxiv", "arXiv", arxiv_collector.collect, bucket=article_items)
    maybe_run("chemrxiv", "ChemRxiv", chemrxiv_collector.collect, bucket=article_items)
    maybe_run("scielo", "SciELO", scielo_collector.collect, bucket=article_items)
    maybe_run("nature", "Nature feeds", feed_collector.collect_nature_feeds, bucket=news_items)
    maybe_run("newsletters", "Newsletters do nicho", feed_collector.collect_newsletter_feeds, bucket=news_items)
    maybe_run("googlenews", "Google News (geral)", googlenews_collector.collect_general, bucket=news_items)
    maybe_run("companies", "Empresas", companies_collector.collect, bucket=company_items)

    # Merge incremental contra o estado persistido (dedupe por DOI/URL -- ver common.merge_items)
    existing_articles = common.load_json(ARTICLES_PATH, [])
    existing_news = common.load_json(NEWS_PATH, [])
    existing_companies = common.load_json(COMPANIES_ACTIVITY_PATH, [])

    merged_articles, new_articles, upd_articles = common.merge_items(existing_articles, article_items)
    # Notícias de empresa entram tanto em news.json (feed cronológico único) quanto em
    # companies_activity.json (agrupado por empresa, para a página Empresas).
    merged_news, new_news, upd_news = common.merge_items(existing_news, news_items + company_items)
    merged_companies, new_comp, upd_comp = common.merge_items(existing_companies, company_items)

    common.save_json(ARTICLES_PATH, merged_articles)
    common.save_json(NEWS_PATH, merged_news)
    common.save_json(COMPANIES_ACTIVITY_PATH, merged_companies)

    finished = datetime.now(timezone.utc)
    meta = {
        "last_run_started": run_started.isoformat(),
        "last_run_finished": finished.isoformat(),
        "duration_seconds": round((finished - run_started).total_seconds(), 1),
        "collectors": collector_results,
        "totals": {
            "articles": len(merged_articles),
            "news": len(merged_news),
            "companies_activity": len(merged_companies),
            "new_articles_this_run": new_articles,
            "new_news_this_run": new_news,
            "new_companies_activity_this_run": new_comp,
        },
    }
    common.save_json(META_PATH, meta)
    common.write_run_snapshot("pipeline_run", meta)

    common.log(
        f"===== Concluído em {meta['duration_seconds']}s. "
        f"Artigos: {len(merged_articles)} (+{new_articles}) | "
        f"Notícias: {len(merged_news)} (+{new_news}) | "
        f"Empresas: {len(merged_companies)} (+{new_comp}) ====="
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
