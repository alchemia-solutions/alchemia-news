#!/usr/bin/env python
"""Orquestrador do pipeline Alchemia Radar. Roda todos os coletores e grava o resultado num de dois destinos:

- `json` (padrão enquanto o GitHub Actions for o escritor): funde com o estado persistido (dedupe por DOI/URL),
  grava os JSON de `pipeline/data/` e um snapshot de execução para auditoria;
- `postgres` (a VM, spec docs/specs/2026-10-02-radar-na-vm-postgres.md): grava no esquema `radar` do banco do
  System pelo papel `alchemia_radar` (`armazenamento_pg.executar`), com trava, contrato e uma transação.

Uso:
    python -m pipeline.run_all                  # execução incremental normal, destino de RADAR_DESTINO ou json
    python -m pipeline.run_all --destino postgres --origem agendada   # o que o agendador da VM chama
    python -m pipeline.run_all --biorxiv-days 60 # backfill bioRxiv mais profundo, sob demanda
    python -m pipeline.run_all --skip companies,scielo   # pula coletores específicos (debug)
"""
from __future__ import annotations

import argparse
import os
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

# A ordem é a de sempre; o terceiro campo diz em que arquivo JSON o item caía (article, news ou companies).
COLETORES = (
    ("pubmed", "PubMed", "article"),
    ("biorxiv", "bioRxiv", "article"),
    ("arxiv", "arXiv", "article"),
    ("chemrxiv", "ChemRxiv", "article"),
    ("scielo", "SciELO", "article"),
    ("nature", "Nature feeds", "news"),
    ("newsletters", "Newsletters do nicho", "news"),
    ("googlenews", "Google News (geral)", "news"),
    ("companies", "Empresas", "companies"),
)


def _funcao(chave: str, biorxiv_days: int | None):
    """A função de cada coletor, resolvida na hora da chamada (os testes trocam o módulo por um dublê sem rede)."""
    return {
        "pubmed": pubmed_collector.collect,
        "biorxiv": lambda: biorxiv_collector.collect(days_override=biorxiv_days),
        "arxiv": arxiv_collector.collect,
        "chemrxiv": chemrxiv_collector.collect,
        "scielo": scielo_collector.collect,
        "nature": feed_collector.collect_nature_feeds,
        "newsletters": feed_collector.collect_newsletter_feeds,
        "googlenews": googlenews_collector.collect_general,
        "companies": companies_collector.collect,
    }[chave]


def _run_collector(name: str, fn, *args, **kwargs) -> tuple[list[dict], float, str | None]:
    start = time.time()
    error = None
    try:
        items = fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        # Sanitizado antes de logar/retornar -- este `error` acaba em meta.json/
        # pipeline/data/runs/*.json, que são commitados de propósito (auditoria), e o
        # repositório é público. Ver common.sanitize_local_path.
        error = common.sanitize_local_path(traceback.format_exc(limit=4))
        common.log(f"[{name}] FALHOU:\n{error}")
        # Coleta PARCIAL de uma seção de feeds (feed_collector.ColetaParcial) carrega os itens
        # dos feeds que responderam. Zerar aqui descartava a colheita boa junto com a ruim --
        # era a causa estrutural dos "count: 0" da seção Nature. Ver ColetaParcial.
        items = list(getattr(exc, "itens", []))
        if items:
            common.log(f"[{name}] parcial: {len(items)} item(ns) preservados dos feeds que responderam")
    elapsed = time.time() - start
    common.log(f"[{name}] {len(items)} itens em {elapsed:.1f}s")
    return items, elapsed, error


def coletar(skip: set[str], biorxiv_days: int | None) -> tuple[dict[str, dict], list[tuple[str, list[dict]]]]:
    """Roda os coletores na ordem de `COLETORES`. Devolve o relatório por coletor e a colheita de cada um."""
    resultados: dict[str, dict] = {}
    colheitas: list[tuple[str, list[dict]]] = []
    for chave, rotulo, _ in COLETORES:
        if chave in skip:
            common.log(f"[{rotulo}] pulado (--skip)")
            resultados[chave] = {"skipped": True}
            continue
        items, elapsed, error = _run_collector(rotulo, _funcao(chave, biorxiv_days))
        colheitas.append((chave, items))
        resultados[chave] = {"count": len(items), "seconds": round(elapsed, 1), "error": error}
    return resultados, colheitas


def _gravar_json(run_started: datetime, collector_results: dict, colheitas: list[tuple[str, list[dict]]]) -> int:
    destino = {chave: arquivo for chave, _, arquivo in COLETORES}
    article_items = [it for c, its in colheitas if destino[c] == "article" for it in its]
    news_items = [it for c, its in colheitas if destino[c] == "news" for it in its]
    company_items = [it for c, its in colheitas if destino[c] == "companies" for it in its]

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pipeline de coleta Alchemia Radar")
    parser.add_argument("--biorxiv-days", type=int, default=None, help="Backfill bioRxiv em dias (default: incremental_days do sources.yaml)")
    parser.add_argument(
        "--skip",
        type=str,
        default="",
        help="Lista separada por vírgula de coletores a pular (pubmed,biorxiv,arxiv,chemrxiv,scielo,nature,newsletters,googlenews,companies)",
    )
    parser.add_argument(
        "--destino",
        choices=("json", "postgres"),
        default=os.environ.get("RADAR_DESTINO") or "json",
        help="json: pipeline/data/ (o Actions, até a virada); postgres: o esquema radar via DATABASE_URL_RADAR (a VM)",
    )
    parser.add_argument(
        "--origem",
        choices=("manual", "agendada"),
        default="manual",
        help="Só no destino postgres: o que vai em radar.execucao.origem",
    )
    args = parser.parse_args(argv)
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}

    if args.destino == "postgres":
        from armazenamento_pg import Colheita, evento, executar  # noqa: PLC0415 - psycopg só no modo postgres

        url = (os.environ.get("DATABASE_URL_RADAR") or "").strip()
        if not url:
            evento("radar.execucao.falhou", motivo="DATABASE_URL_RADAR ausente no ambiente")
            return 1
        return executar(
            url,
            lambda: Colheita(*coletar(skip, args.biorxiv_days)),
            origem=args.origem,
            versao=(os.environ.get("RADAR_VERSAO") or "").strip() or None,
        )

    run_started = datetime.now(timezone.utc)
    common.log(f"===== Alchemia Radar pipeline: iniciando execução ({run_started.isoformat()}) =====")
    collector_results, colheitas = coletar(skip, args.biorxiv_days)
    return _gravar_json(run_started, collector_results, colheitas)


if __name__ == "__main__":
    sys.exit(main())
