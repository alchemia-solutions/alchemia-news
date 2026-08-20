#!/usr/bin/env python
"""Sincroniza articles.json/news.json com a tabela `items` no Supabase.

Não substitui os JSONs locais -- eles continuam sendo a fonte de verdade que o
pipeline escreve (ver run_all.py) e que o dashboard já sabe ler como rede de
segurança. Este script só espelha o resultado já mesclado para o Postgres
gerenciado, via upsert em lote pela API REST (`on_conflict=dedupe_key`,
`Prefer: resolution=merge-duplicates`) -- requests já é dependência do pipeline
(requirements.txt), sem driver novo (psycopg2 etc.) para uma escrita 3x/dia.

Uso:
    python -m pipeline.sync_supabase              # sincroniza articles.json + news.json
    python -m pipeline.sync_supabase --dry-run     # mostra quantos itens sincronizaria, não escreve

Credencial: SUPABASE_SERVICE_ROLE_KEY (variável de ambiente de usuário do Windows,
configurada manualmente pelo fundador -- nunca por um agente, nunca hardcoded).
Sem ela, a sincronização é pulada com aviso e o script sai 0 -- é uma integração
opcional que espelha o dado real, nunca pode derrubar a cadeia do cron (mesmo
princípio já usado pela Etapa 2/research_export em run_alchemia_news.cmd).
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from collectors import common  # noqa: E402

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://texszxmvolbiduhrrdsq.supabase.co")
SUPABASE_TABLE = "items"
BATCH_SIZE = 500

# Colunas reais da tabela (migração supabase/migrations/*_create_items_table.sql),
# na mesma ordem de Item.to_dict() (common.py) -- id/inserted_at ficam de fora de
# propósito: omitidos do payload, o upsert (`ON CONFLICT ... DO UPDATE`) não os
# toca, então inserted_at preserva a data do primeiro insert e id nunca é reescrito.
_COLUMNS = (
    "dedupe_key",
    "kind",
    "title",
    "url",
    "source",
    "source_type",
    "published_date",
    "collected_at",
    "authors",
    "summary",
    "doi",
    "company_slug",
    "keywords_matched",
    "extra",
)


def _to_row(item: dict, now_iso: str) -> dict:
    row = {col: item.get(col) for col in _COLUMNS}
    row["updated_at"] = now_iso
    return row


def _upsert_batch(rows: list[dict], service_role_key: str) -> None:
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}",
        params={"on_conflict": "dedupe_key"},
        json=rows,
        headers={
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
        timeout=60,
    )
    if resp.status_code >= 300:
        raise RuntimeError(
            f"Upsert falhou ({resp.status_code}): {resp.text[:500]}"
        )


def sync(dry_run: bool = False) -> int:
    service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not service_role_key and not dry_run:
        common.log(
            "SUPABASE_SERVICE_ROLE_KEY não configurada -- pulando sincronização com Supabase "
            "(configure como variável de ambiente de usuário do Windows para ativar; ver AGENTS.md "
            "deste setor)."
        )
        return 0

    articles = common.load_json(common.DATA_DIR / "articles.json", [])
    news = common.load_json(common.DATA_DIR / "news.json", [])
    items = articles + news

    if not items:
        common.log("Nada para sincronizar (articles.json + news.json vazios).")
        return 0

    now_iso = datetime.now(timezone.utc).isoformat()
    rows = [_to_row(item, now_iso) for item in items]

    if dry_run:
        common.log(f"[dry-run] sincronizaria {len(rows)} itens ({len(articles)} artigos + {len(news)} notícias).")
        return 0

    synced = 0
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start : start + BATCH_SIZE]
        _upsert_batch(batch, service_role_key)
        synced += len(batch)
        common.log(f"Supabase: {synced}/{len(rows)} itens sincronizados...")

    common.log(f"Supabase: sincronização concluída -- {synced} itens ({len(articles)} artigos + {len(news)} notícias).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sincroniza articles.json/news.json com a tabela `items` no Supabase")
    parser.add_argument("--dry-run", action="store_true", help="Não escreve no Supabase, só reporta quantos itens sincronizaria")
    args = parser.parse_args()
    return sync(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
