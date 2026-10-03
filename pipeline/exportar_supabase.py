#!/usr/bin/env python
"""Exporta as sete tabelas do Supabase do Radar antes do desligamento (spec 2026-10-02-radar-na-vm-postgres, D4).

QUEM RODA É O FUNDADOR, com a credencial dele: nenhum agente lê, imprime ou usa a `SUPABASE_SERVICE_ROLE_KEY`.
O script só lê (GET na API REST, paginação por chave), grava um JSON por tabela e um `manifesto.json` com a
contagem de linhas e o sha256 de cada arquivo. A contagem do manifesto é a que o critério 14 pede registrar antes
de desligar o projeto, e o `migrar_para_postgres.py --supabase <pasta>` confere o sha256 antes de usar o export.

O export leva nomes de autores (dado pessoal tornado público pelo titular): guarde-o FORA do Drive e fora do
vault, em `alchemia-workdata`, e apague-o depois da conferência (spec, lente LGPD). O script recusa uma pasta de
destino dentro da pasta da empresa.

    # PowerShell, na raiz do repositório do Radar
    $env:SUPABASE_SERVICE_ROLE_KEY = "<cole aqui, nunca num arquivo>"
    pipeline\\.venv\\Scripts\\python.exe -m pipeline.exportar_supabase --destino C:\\Users\\AryelBezerra\\alchemia-workdata\\radar-supabase-export
    Remove-Item Env:SUPABASE_SERVICE_ROLE_KEY

Sai 0 com o manifesto gravado; 1 se uma tabela falhar (nada é dado como exportado pela metade); 2 sem a chave.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import requests

# (tabela, coluna de ordem e paginação); a lista é a das migrações em supabase/migrations/
TABELAS = (
    ("items", "dedupe_key"),
    ("newsletters", "date"),
    ("companies", "slug"),
    ("resources", "slug"),
    ("funding_channels", "slug"),
    ("corporate_programs", "slug"),
    ("pipeline_meta", "id"),
)
PAGINA = 1000
URL_PADRAO = "https://texszxmvolbiduhrrdsq.supabase.co"  # o mesmo padrão de sync_supabase.py


class ExportFalhou(RuntimeError):
    pass


def dentro_da_empresa(destino: Path) -> bool:
    """A pasta da empresa é a que tem `alchemia-brain/` e `alchemia-ai/` lado a lado (o Drive sincroniza tudo ali)."""
    for p in (destino.resolve(), *destino.resolve().parents):
        if (p / "alchemia-brain").is_dir() and (p / "alchemia-ai").is_dir():
            return True
    return False


def baixar_tabela(sessao: Any, base: str, chave_api: str, tabela: str, coluna: str) -> list[dict]:
    """Todas as linhas, em páginas de `PAGINA`, por chave (`coluna > último`), na ordem da coluna."""
    linhas: list[dict] = []
    ultimo = None
    total = None
    cab = {"apikey": chave_api, "Authorization": f"Bearer {chave_api}", "Accept": "application/json"}
    while True:
        params = {"select": "*", "order": f"{coluna}.asc", "limit": str(PAGINA)}
        if ultimo is not None:
            params[coluna] = f"gt.{ultimo}"
        # a primeira página pede a contagem exata (Content-Range: 0-999/<total>), conferida no fim
        extra = {"Prefer": "count=exact"} if total is None else {}
        r = sessao.get(f"{base}/rest/v1/{tabela}", params=params, headers={**cab, **extra}, timeout=60)
        if r.status_code not in (200, 206):
            raise ExportFalhou(f"{tabela}: HTTP {r.status_code}")
        if total is None:
            faixa = r.headers.get("Content-Range", "")
            total = int(faixa.rsplit("/", 1)[1]) if "/" in faixa and faixa.rsplit("/", 1)[1].isdigit() else -1
        pagina = r.json()
        if not isinstance(pagina, list):
            raise ExportFalhou(f"{tabela}: resposta não é lista")
        linhas.extend(pagina)
        if len(pagina) < PAGINA:
            break
        novo = pagina[-1].get(coluna)
        if novo is None or novo == ultimo:
            raise ExportFalhou(f"{tabela}: paginação sem avanço em {coluna}")
        ultimo = novo
    chaves = [l.get(coluna) for l in linhas]
    if len(set(chaves)) != len(chaves):
        raise ExportFalhou(f"{tabela}: chave repetida no export")
    if total != len(linhas):
        # a coleta do Actions gravou durante o export, ou o servidor não mandou a contagem: rode de novo
        # longe dos horários da coleta (09:40, 15:40 e 21:40 UTC)
        raise ExportFalhou(f"{tabela}: {len(linhas)} linhas lidas, contagem do servidor {total}")
    return linhas


def exportar(destino: Path, chave_api: str, base: str, sessao: Any = None) -> dict:
    sessao = sessao or requests.Session()
    destino.mkdir(parents=True, exist_ok=True)
    manifesto = {"exportado_em": datetime.now(timezone.utc).isoformat(), "projeto": urlsplit(base).netloc, "tabelas": {}}
    for tabela, coluna in TABELAS:
        linhas = baixar_tabela(sessao, base, chave_api, tabela, coluna)
        bruto = json.dumps(linhas, ensure_ascii=False, indent=1).encode("utf-8")
        (destino / f"{tabela}.json").write_bytes(bruto)
        manifesto["tabelas"][tabela] = {"linhas": len(linhas), "sha256": hashlib.sha256(bruto).hexdigest()}
        print(f"{tabela}: {len(linhas)} linhas", flush=True)
    (destino / "manifesto.json").write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifesto


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Exporta as tabelas do Supabase do Radar (só leitura; quem roda é o fundador)")
    ap.add_argument("--destino", type=Path, required=True, help="Pasta FORA do Drive (alchemia-workdata)")
    args = ap.parse_args(argv)
    if dentro_da_empresa(args.destino):
        print("recusado: o destino está dentro da pasta da empresa (Drive). Use alchemia-workdata.", file=sys.stderr)
        return 2
    chave = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not chave:
        print("SUPABASE_SERVICE_ROLE_KEY ausente: nada exportado.", file=sys.stderr)
        return 2
    base = (os.environ.get("SUPABASE_URL") or URL_PADRAO).rstrip("/")
    try:
        man = exportar(args.destino, chave, base)
    except (ExportFalhou, requests.RequestException) as exc:
        # a mensagem nunca carrega a chave: só a tabela e o status (ou o tipo do erro de rede)
        msg = str(exc) if isinstance(exc, ExportFalhou) else type(exc).__name__
        print(f"export falhou: {msg}. O manifesto não foi gravado.", file=sys.stderr)
        return 1
    print(json.dumps({t: v["linhas"] for t, v in man["tabelas"].items()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
