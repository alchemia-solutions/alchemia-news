"""Um banco descartável com o esquema `radar` REAL do System, para os testes do escritor e da carga.

Só roda com PG_DESCARTAVEL_URL (superusuário de um cluster descartável; nunca o athanor_database, nunca o banco do
servidor de dev). O cluster sobe com o script do System, numa porta própria para não esbarrar noutra sessão:

    ALC_PG_PORTA=55431 bash ../alchemia-system/scripts/dev/pg-descartavel.sh up     # imprime a URL
    PG_DESCARTAVEL_URL=<a URL> pipeline/.venv/Scripts/python.exe -m unittest discover pipeline/tests -v
    ALC_PG_PORTA=55431 bash ../alchemia-system/scripts/dev/pg-descartavel.sh down

Cada `Banco()` cria um banco novo (`radar_teste_<hex>`) e o monta como o deploy monta produção
(alchemia-system/compose.yaml): papeis.sql do System como superusuário, as migrações do System ATÉ a 0024_radar como
`alchemia_owner`, papeis.sql de novo. Esquema e concessões vêm SEMPRE do System, nunca de fixture deste repositório:
sem a 0024 ou sem o `alchemia_radar` no papeis.sql, os testes com banco falham alto.
"""
from __future__ import annotations

import json
import os
import secrets
import unittest
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

try:
    import psycopg
    from psycopg import sql
except ImportError:  # pragma: no cover
    psycopg = None  # type: ignore[assignment]

URL_SUPER = os.environ.get("PG_DESCARTAVEL_URL", "").strip()
RAIZ_DO_REPO = Path(__file__).resolve().parents[2]
SISTEMA_CORE = RAIZ_DO_REPO.parent / "alchemia-system" / "packages" / "core"
MIGRACAO_DO_RADAR = "0024_radar"
PAPEIS = ("alchemia_owner", "alchemia_app", "alchemia_bridge", "alchemia_radar")

# Senhas aleatórias por processo: os papéis são do cluster, os bancos são por teste.
_SENHAS = {p: secrets.token_hex(12) for p in PAPEIS}
_PAPEIS_PRONTOS = False


def precisa_de_banco(cls):
    """Pula a classe sem PG_DESCARTAVEL_URL ou sem psycopg (o motivo aparece no relatório do unittest)."""
    if psycopg is None:
        return unittest.skip("psycopg ausente: pip install -r pipeline/requirements-pg.txt")(cls)
    if not URL_SUPER:
        return unittest.skip("sem PG_DESCARTAVEL_URL (cluster descartável; ver pipeline/tests/pg_descartavel.py)")(cls)
    if "athanor" in URL_SUPER.lower():
        raise RuntimeError("PG_DESCARTAVEL_URL aponta para o athanor: recusado")
    return cls


def _url(banco: str, papel: str | None = None) -> str:
    p = urlsplit(URL_SUPER)
    netloc = p.netloc
    if papel:
        netloc = f"{papel}:{_SENHAS[papel]}@{p.hostname}:{p.port}"
    return urlunsplit((p.scheme, netloc, f"/{banco}", "", ""))


def _migracoes_ate_o_radar() -> list[Path]:
    jornal = json.loads((SISTEMA_CORE / "drizzle" / "meta" / "_journal.json").read_text(encoding="utf-8"))
    tags = [e["tag"] for e in jornal["entries"]]
    if MIGRACAO_DO_RADAR not in tags:
        raise RuntimeError(f"o System ainda não tem a migração {MIGRACAO_DO_RADAR}: o esquema radar não existe para testar")
    return [SISTEMA_CORE / "drizzle" / f"{t}.sql" for t in tags[: tags.index(MIGRACAO_DO_RADAR) + 1]]


class Banco:
    """Um banco descartável montado como produção. `url(papel)` dá a URL de cada papel."""

    def __init__(self) -> None:
        global _PAPEIS_PRONTOS
        self.nome = f"radar_teste_{secrets.token_hex(4)}"
        with psycopg.connect(URL_SUPER, autocommit=True) as c:
            c.execute(sql.SQL("create database {}").format(sql.Identifier(self.nome)))
            if not _PAPEIS_PRONTOS:
                for papel, senha in _SENHAS.items():
                    c.execute(sql.SQL("do $$ begin if not exists (select 1 from pg_roles where rolname = {}) "
                                      "then create role {} login; end if; end $$").format(sql.Literal(papel), sql.Identifier(papel)))
                    c.execute(sql.SQL("alter role {} password {}").format(sql.Identifier(papel), sql.Literal(senha)))
                _PAPEIS_PRONTOS = True
        papeis_sql = (SISTEMA_CORE / "sql" / "papeis.sql").read_text(encoding="utf-8")
        if "alchemia_radar" not in papeis_sql:
            raise RuntimeError("o papeis.sql do System não concede nada ao alchemia_radar: gere-o de novo (npm run db:papeis)")
        self.como_super(papeis_sql)
        with psycopg.connect(self.url("alchemia_owner"), autocommit=True) as c:
            for arq in _migracoes_ate_o_radar():
                for stmt in arq.read_text(encoding="utf-8").split("--> statement-breakpoint"):
                    if stmt.strip():
                        c.execute(stmt)
        self.como_super(papeis_sql)
        self.fonte_das_concessoes = "papeis.sql do System"

    def url(self, papel: str | None = None) -> str:
        return _url(self.nome, papel)

    def como_super(self, texto: str, params=None):
        with psycopg.connect(self.url(), autocommit=True) as c:
            cur = c.execute(texto, params)
            return cur.fetchall() if cur.description else None

    def como(self, papel: str, texto: str, params=None):
        with psycopg.connect(self.url(papel), autocommit=True) as c:
            cur = c.execute(texto, params)
            return cur.fetchall() if cur.description else None

    def apagar(self) -> None:
        with psycopg.connect(URL_SUPER, autocommit=True) as c:
            c.execute(sql.SQL("drop database if exists {} with (force)").format(sql.Identifier(self.nome)))
