#!/usr/bin/env python
"""Sincroniza o dado local do pipeline com o Supabase -- fonte que o dashboard lê.

Não substitui os arquivos locais -- eles continuam sendo a fonte de verdade que o
pipeline escreve (ver run_all.py) e que o dashboard ainda sabe ler como rede de
segurança (`dashboard/lib/data.ts`, fallback quando o Supabase não responde). Este
script só espelha o resultado já mesclado/curado para o Postgres gerenciado, via
upsert em lote pela API REST -- `requests` já é dependência do pipeline
(requirements.txt), sem driver novo (psycopg2 etc.) para uma escrita 3x/dia.

Fase 1 (2026-08-20): só articles.json/news.json -> tabela `items`.
Fase 2 (2026-08-20, mais tarde, a pedido do fundador -- "quero tudo... sem
precisar commitar nada depois"): expande para os catálogos e o meta.json.
`companies_activity.json` propositalmente NÃO tem sincronização própria -- seus
itens já são o mesmo formato de `items` (kind='news', company_slug preenchido) e
já chegam via news.json (o pipeline deposita todo item de empresa nos dois
arquivos, de propósito). Ver supabase/migrations/*_expand_remaining_tables.sql.

A newsletter (pipeline/data/newsletter/*.md) também NÃO é sincronizada aqui --
é conteúdo gerado pela Tarefa Agendada do Axel, mais tarde no dia que este
script roda (Etapa 3 do cron roda logo após a coleta, antes do Axel existir o
conteúdo do dia). Ver alchemia-ai/alchemia-bots/scripts/sync_newsletter.py.

Uso:
    python -m pipeline.sync_supabase              # sincroniza tudo (items + catálogos + meta)
    python -m pipeline.sync_supabase --dry-run     # mostra quantos itens sincronizaria, não escreve
    python -m pipeline.sync_supabase --only items  # só uma tabela (items|companies|resources|funding_channels|corporate_programs|meta)

Credencial: SUPABASE_SERVICE_ROLE_KEY (variável de ambiente de usuário do Windows,
configurada manualmente pelo fundador -- nunca por um agente, nunca hardcoded).
Sem ela, a sincronização inteira é pulada com aviso e o script sai 0 -- é uma
integração opcional que espelha o dado real, nunca pode derrubar a cadeia do cron
(mesmo princípio já usado pela Etapa 2/research_export em run_alchemia_news.cmd).
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from collectors import common  # noqa: E402

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://texszxmvolbiduhrrdsq.supabase.co")
BATCH_SIZE = 500

ALL_TARGETS = ("items", "companies", "resources", "funding_channels", "corporate_programs", "meta")


def _upsert(table: str, rows: list[dict], on_conflict: str, service_role_key: str) -> None:
    if not rows:
        return
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start : start + BATCH_SIZE]
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            params={"on_conflict": on_conflict},
            json=batch,
            headers={
                "apikey": service_role_key,
                "Authorization": f"Bearer {service_role_key}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
            timeout=60,
        )
        if resp.status_code >= 300:
            raise RuntimeError(f"Upsert em `{table}` falhou ({resp.status_code}): {resp.text[:500]}")


# --- items (articles.json + news.json) --------------------------------------

_ITEM_COLUMNS = (
    "dedupe_key", "kind", "title", "url", "source", "source_type", "published_date",
    "collected_at", "authors", "summary", "doi", "company_slug", "keywords_matched", "extra",
)


def _sync_items(service_role_key: str, now_iso: str, dry_run: bool) -> str:
    articles = common.load_json(common.DATA_DIR / "articles.json", [])
    news = common.load_json(common.DATA_DIR / "news.json", [])
    items = articles + news
    if not items:
        return "items: nada para sincronizar (articles.json + news.json vazios)."
    rows = [{**{col: item.get(col) for col in _ITEM_COLUMNS}, "updated_at": now_iso} for item in items]
    if dry_run:
        return f"items: [dry-run] sincronizaria {len(rows)} ({len(articles)} artigos + {len(news)} notícias)."
    _upsert("items", rows, "dedupe_key", service_role_key)
    return f"items: {len(rows)} sincronizados ({len(articles)} artigos + {len(news)} notícias)."


# --- catálogos estáticos (companies/resources/funding_channels/corporate_programs) ---

_COMPANY_COLUMNS = ("slug", "name", "url", "category", "method", "query", "filter_relevance", "logo_hint")
_RESOURCE_COLUMNS = ("slug", "name", "full_name", "url", "type", "description", "license_note")
_FUNDING_COLUMNS = (
    "slug", "name", "full_name", "scope", "portal_url", "calls_url", "programs",
    "priority_alchemia", "priority_note", "requires", "source_guide", "last_reviewed",
)
_PROGRAM_COLUMNS = (
    "slug", "name", "category", "region", "portal_url", "benefit_summary",
    "eligibility_summary", "priority_alchemia", "priority_note", "source_guide", "last_reviewed",
)


# Colunas array/jsonb com `not null default` na migração -- se o campo faltar no YAML
# (ex.: `requires` não é obrigatório em todo canal de fomento), `entry.get(col)` devolve
# `None`, que vira `null` explícito no payload JSON. Um `null` explícito **sobrescreve**
# o default da coluna (o default só se aplica quando a chave está ausente, não quando
# vem `null`) -- achado real (2026-08-20): upsert de `funding_channels` falhava com
# `null value in column "requires" violates not-null constraint` no primeiro canal sem
# `requires` no YAML (`sebrae`). Corrigido substituindo `None` por `[]` só nessas colunas.
_ARRAY_DEFAULT_COLUMNS = ("programs", "requires")


def _sync_catalog(table: str, yaml_file: str, root_key: str, columns: tuple[str, ...],
                   service_role_key: str, now_iso: str, dry_run: bool) -> str:
    parsed = common.load_yaml(yaml_file) or {}
    entries = parsed.get(root_key, []) if isinstance(parsed, dict) else parsed
    if not entries:
        return f"{table}: nada para sincronizar ({yaml_file} vazio ou sem chave '{root_key}')."
    rows = []
    for entry in entries:
        row = {}
        for col in columns:
            value = entry.get(col)
            if value is None and col in _ARRAY_DEFAULT_COLUMNS:
                value = []
            row[col] = value
        row["updated_at"] = now_iso
        rows.append(row)
    if dry_run:
        return f"{table}: [dry-run] sincronizaria {len(rows)} entradas."
    _upsert(table, rows, "slug", service_role_key)
    return f"{table}: {len(rows)} entradas sincronizadas."


# --- meta.json (singleton) ---------------------------------------------------

def _sync_meta(service_role_key: str, now_iso: str, dry_run: bool) -> str:
    meta = common.load_json(common.DATA_DIR / "meta.json", None)
    if not meta:
        return "meta: nada para sincronizar (meta.json ausente/vazio)."
    row = {
        "id": "singleton",
        "last_run_started": meta.get("last_run_started"),
        "last_run_finished": meta.get("last_run_finished"),
        "duration_seconds": meta.get("duration_seconds"),
        "collectors": meta.get("collectors", {}),
        "totals": meta.get("totals", {}),
        "updated_at": now_iso,
    }
    if dry_run:
        return "meta: [dry-run] sincronizaria a linha singleton."
    _upsert("pipeline_meta", [row], "id", service_role_key)
    return "meta: linha singleton sincronizada."


def sync(dry_run: bool = False, only: tuple[str, ...] = ALL_TARGETS) -> int:
    service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not service_role_key and not dry_run:
        common.log(
            "SUPABASE_SERVICE_ROLE_KEY não configurada -- pulando sincronização com Supabase "
            "(configure como variável de ambiente de usuário do Windows para ativar; ver AGENTS.md "
            "deste setor)."
        )
        return 0

    now_iso = datetime.now(timezone.utc).isoformat()
    results: list[str] = []
    try:
        if "items" in only:
            results.append(_sync_items(service_role_key, now_iso, dry_run))
        if "companies" in only:
            results.append(_sync_catalog(
                "companies", "companies.yaml", "companies", _COMPANY_COLUMNS,
                service_role_key, now_iso, dry_run,
            ))
        if "resources" in only:
            results.append(_sync_catalog(
                "resources", "resources.yaml", "resources", _RESOURCE_COLUMNS,
                service_role_key, now_iso, dry_run,
            ))
        if "funding_channels" in only:
            results.append(_sync_catalog(
                "funding_channels", "funding_channels.yaml", "funding_channels", _FUNDING_COLUMNS,
                service_role_key, now_iso, dry_run,
            ))
        if "corporate_programs" in only:
            results.append(_sync_catalog(
                "corporate_programs", "corporate_programs.yaml", "corporate_programs", _PROGRAM_COLUMNS,
                service_role_key, now_iso, dry_run,
            ))
        if "meta" in only:
            results.append(_sync_meta(service_role_key, now_iso, dry_run))
    except Exception as exc:  # noqa: BLE001 -- reportar e sair !=0, nunca engolir erro de sync
        common.log(f"Supabase: sincronização falhou -- {exc}")
        for line in results:
            common.log(f"Supabase: {line}")
        return 1

    for line in results:
        common.log(f"Supabase: {line}")
    common.log("Supabase: sincronização concluída.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sincroniza o dado local do pipeline com o Supabase")
    parser.add_argument("--dry-run", action="store_true", help="Não escreve no Supabase, só reporta quantos itens sincronizaria")
    parser.add_argument(
        "--only",
        choices=ALL_TARGETS,
        action="append",
        help="Sincronizar só esta tabela (repetível). Sem esta flag, sincroniza todas.",
    )
    args = parser.parse_args()
    only = tuple(args.only) if args.only else ALL_TARGETS
    return sync(dry_run=args.dry_run, only=only)


if __name__ == "__main__":
    sys.exit(main())
