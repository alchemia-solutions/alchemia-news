#!/usr/bin/env python
"""Digest determinístico do Alchemia News — a saída que o cron do Hermes entrega no Discord.

Roda o pipeline de coleta e imprime um resumo COMPACTO do que é novo. Nunca despeja a base
inteira (1.700+ notícias): o Discord recebe contagem por coletor e os títulos/links dos itens
novos mais relevantes, sempre com a fonte e o termo que trouxe cada item.

Contrato com o cron do Hermes (`--no-agent --script`):
  - stdout É a mensagem entregue, verbatim. Sem LLM envolvido — custo zero de token, e nenhuma
    chance de fabricar relevância (a spec de alchemia-news proíbe LLM na coleta).
  - **stdout vazio = tick silencioso.** Se nada novo entrou, o Discord não recebe nada. É o
    padrão watchdog documentado pelo Hermes, e evita três mensagens diárias dizendo "nada mudou".
  - Saída em erro (exceção/exit != 0) vira alerta de erro do cron.
  - Timeout de script do Hermes é 3600 s (contra o hard interrupt de 3 min de um job com agente),
    então um backfill profundo cabe aqui.

Uso:
    python -m pipeline.digest                 # roda a coleta e resume o delta
    python -m pipeline.digest --no-collect    # só resume o estado atual, sem coletar
    python -m pipeline.digest --top 8         # nº de destaques por seção (default 5)

Ver `alchemia-ai/alchemia-bots/docs/specs/2026-08-17-hermes-ecosystem-architecture.md`.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "pipeline" / "data"

# Limite duro de caracteres — o Discord corta mensagem em 2000. Ficamos bem abaixo.
MAX_CHARS = 1800


def _load(name: str):
    try:
        return json.loads((DATA / name).read_text(encoding="utf-8"))
    except Exception:
        return None


def _snapshot() -> dict[str, int]:
    """Contagem atual de cada arquivo de dado, para medir o delta de forma confiável."""
    out = {}
    for key, fname in (("articles", "articles.json"), ("news", "news.json"),
                       ("companies", "companies_activity.json")):
        d = _load(fname)
        out[key] = len(d) if isinstance(d, list) else 0
    return out


def _ids(fname: str) -> set[str]:
    d = _load(fname)
    if not isinstance(d, list):
        return set()
    ids = set()
    for it in d:
        if isinstance(it, dict):
            key = it.get("doi") or it.get("url") or it.get("title")
            if key:
                ids.add(str(key))
    return ids


def _fmt(items: list[dict], limit: int) -> list[str]:
    lines = []
    for it in items[:limit]:
        title = (it.get("title") or "sem título").strip().replace("\n", " ")
        if len(title) > 110:
            title = title[:107] + "..."
        src = it.get("source") or it.get("collector") or "?"
        url = it.get("url") or it.get("doi") or ""
        kw = it.get("keywords_matched")
        kwtxt = ""
        if isinstance(kw, list) and kw:
            kwtxt = f" _[{', '.join(str(k) for k in kw[:2])}]_"
        lines.append(f"• **{title}**{kwtxt}\n  {src} — {url}".rstrip(" —"))
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description="Digest compacto do Alchemia News")
    ap.add_argument("--no-collect", action="store_true", help="Não roda a coleta, só resume o estado atual")
    ap.add_argument("--top", type=int, default=5, help="Destaques por seção (default 5)")
    ap.add_argument("--biorxiv-days", type=int, default=None, help="Repassado ao run_all para backfill")
    args = ap.parse_args()

    before_ids = {f: _ids(f) for f in ("articles.json", "news.json", "companies_activity.json")}
    before = _snapshot()

    if not args.no_collect:
        cmd = [sys.executable, "-m", "pipeline.run_all"]
        if args.biorxiv_days is not None:
            cmd += ["--biorxiv-days", str(args.biorxiv_days)]
        # stderr do pipeline não vai para o stdout entregue — só o digest vai.
        proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
        if proc.returncode != 0:
            # Falha real precisa virar alerta de erro do cron, não silêncio.
            sys.stderr.write(proc.stderr[-2000:] or "run_all falhou sem stderr\n")
            print(f"⚠️ **Alchemia News — falha na coleta** (exit {proc.returncode}). Ver logs do pipeline.")
            return 1

    after = _snapshot()
    meta = _load("meta.json") or {}

    delta = {k: after.get(k, 0) - before.get(k, 0) for k in after}
    total_new = sum(v for v in delta.values() if v > 0)

    # Tick silencioso: nada novo, nada entregue.
    if total_new <= 0:
        return 0

    parts: list[str] = ["📡 **Alchemia News** — coleta automática"]

    dur = meta.get("duration_seconds")
    cols = meta.get("collectors") or {}
    errs = [n for n, c in cols.items() if isinstance(c, dict) and c.get("error")]
    head = (f"{delta.get('articles',0):+d} artigos · {delta.get('news',0):+d} notícias · "
            f"{delta.get('companies',0):+d} atividade de empresas")
    if dur:
        head += f" · {dur}s"
    parts.append(head)
    if errs:
        parts.append(f"⚠️ coletores com erro: {', '.join(errs)}")

    for label, fname, key in (("📄 Artigos/preprints", "articles.json", "articles"),
                              ("📰 Notícias", "news.json", "news"),
                              ("🏢 Empresas", "companies_activity.json", "companies")):
        if delta.get(key, 0) <= 0:
            continue
        d = _load(fname) or []
        old = before_ids.get(fname, set())
        fresh = [it for it in d if isinstance(it, dict)
                 and str(it.get("doi") or it.get("url") or it.get("title") or "") not in old]
        if not fresh:
            continue
        block = _fmt(fresh, args.top)
        if block:
            extra = len(fresh) - len(block)
            parts.append(f"\n{label} ({len(fresh)} novos)")
            parts.extend(block)
            if extra > 0:
                parts.append(f"  _…mais {extra}. Dashboard: `npm run dev` em alchemia-news/dashboard_")

    out = "\n".join(parts)
    if len(out) > MAX_CHARS:
        out = out[:MAX_CHARS].rsplit("\n", 1)[0] + "\n… _(truncado — ver dashboard)_"
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
