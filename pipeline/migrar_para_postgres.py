#!/usr/bin/env python
"""A carga inicial do acervo do Radar no esquema `radar` (spec docs/specs/2026-10-02-radar-na-vm-postgres.md,
"A migração do dado atual", critérios 1 a 4).

Origens, unidas e conferidas por contagem (nunca uma escolha de um lado):

| Origem | O que entra |
|---|---|
| os três JSON no `--ref` (padrão `origin/main`) | a base; o registro de hoje vence |
| toda versão desses três arquivos no histórico do git | as chaves que sumiram, como as de 2026-09-07 (D3) |
| o export do Supabase (`--supabase DIR`, de `exportar_supabase.py`) | só chave ausente e campo vazio |
| `pipeline/data/runs/*-pipeline_run.json` no `--ref` | `radar.execucao` com `origem = 'importada'` |
| `pipeline/data/newsletter/AAAA-MM-DD.md` no `--ref` | `radar.newsletter` |
| os quatro YAML de `pipeline/config/` no `--ref` | `radar.catalogo` |

Fusão da mesma chave vinda de mais de uma versão: `collected_at` é o mais antigo visto; `company_slug` não nulo
vence; `keywords_matched` é a união; os demais campos são os do registro mais recente que os tem preenchidos.
Versão que não parseia é contada e relatada pelo commit, nunca silenciada. `.axel_seen.json` e `discord/` não migram.

Duas metades, porque o histórico do git mora na estação e o banco de produção só na rede interna da VM:

    # na estação (lê o git; não toca banco nenhum)
    python -m pipeline.migrar_para_postgres --dry-run
    python -m pipeline.migrar_para_postgres --salvar-pacote <alchemia-workdata>/radar-carga.json.gz
    # onde há banco (o contêiner da VM, ou o system_dev local), com o papel alchemia_radar
    python -m pipeline.migrar_para_postgres --pacote radar-carga.json.gz [--dry-run]
    # local, tudo de uma vez (git + DATABASE_URL_RADAR)
    python -m pipeline.migrar_para_postgres

Idempotente: a segunda carga do mesmo pacote dá 0 inserções e 0 atualizações (o upsert só grava mudança real).
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402

import armazenamento_pg as apg  # noqa: E402
from collectors import common  # noqa: E402

FORMATO_DO_PACOTE = 1
ARQUIVOS_DE_ITEM = (  # a ordem importa: dentro de um commit, o registro de empresa (mais específico) vem por último
    ("pipeline/data/articles.json", "article"),
    ("pipeline/data/news.json", "news"),
    ("pipeline/data/companies_activity.json", "news"),
)
CAMPOS_MAIS_RECENTE = ("kind", "title", "url", "source", "source_type", "published_date", "authors", "summary", "doi", "extra")
NEWSLETTER_RE = re.compile(r"^pipeline/data/newsletter/(\d{4}-\d{2}-\d{2})\.md$")
# 2026-09-07: `6800a38` é a última coleta do Actions antes do truncamento (spec, "O acervo perdido"); `9bdfbd8` é a
# coleta local do mesmo dia, o outro lado do merge `d5eb59a` que não parseia, com itens que nenhum dos dois lados tem hoje.
COMMITS_A_CONFERIR = ("6800a38", "9bdfbd8")


# --- git, só leitura ------------------------------------------------------------------------------

class Git:
    def __init__(self, repo: Path) -> None:
        self.repo = repo
        self._batch: subprocess.Popen | None = None

    def run(self, *args: str) -> str:
        r = subprocess.run(["git", *args], cwd=self.repo, capture_output=True, check=True)
        return r.stdout.decode("utf-8", errors="replace")

    def blob(self, sha: str) -> bytes:
        if self._batch is None:
            self._batch = subprocess.Popen(["git", "cat-file", "--batch"], cwd=self.repo,
                                           stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        assert self._batch.stdin and self._batch.stdout
        self._batch.stdin.write(f"{sha}\n".encode())
        self._batch.stdin.flush()
        cab = self._batch.stdout.readline().decode().split()
        if len(cab) < 3 or cab[1] != "blob":
            raise RuntimeError(f"git cat-file: {sha} não é blob ({' '.join(cab)})")
        dado = self._batch.stdout.read(int(cab[2]))
        self._batch.stdout.read(1)
        return dado

    def fechar(self) -> None:
        if self._batch is not None:
            self._batch.stdin.close()  # type: ignore[union-attr]
            self._batch.wait()
            self._batch.stdout.close()  # type: ignore[union-attr]
            self._batch = None

    def ls(self, ref: str, *caminhos: str) -> dict[str, str]:
        """caminho -> sha do blob, no ref."""
        out = {}
        for linha in self.run("ls-tree", "-r", ref, "--", *caminhos).splitlines():
            meta, caminho = linha.split("\t", 1)
            _, tipo, sha = meta.split()
            if tipo == "blob":
                out[caminho] = sha
        return out


# --- a união dos itens ------------------------------------------------------------------------------

def _preenchido(v: Any) -> bool:
    return v not in (None, "", [], {})


@dataclass
class Uniao:
    """Itens por `dedupe_key` gravada, com o primeiro e o último instante em que cada um foi visto."""

    itens: dict[str, dict] = field(default_factory=dict)
    primeiro: dict[str, datetime] = field(default_factory=dict)
    ultimo: dict[str, datetime] = field(default_factory=dict)

    def fundir(self, rec: dict, kind_do_arquivo: str, visto: datetime) -> str | None:
        if not isinstance(rec, dict):
            return None
        rec = dict(rec)
        rec.setdefault("kind", kind_do_arquivo)
        chave = rec.get("dedupe_key") or common.dedupe_key(rec)
        rec["dedupe_key"] = chave
        atual = self.itens.get(chave)
        if atual is None:
            self.itens[chave] = rec
        else:
            for campo in CAMPOS_MAIS_RECENTE:
                if _preenchido(rec.get(campo)):
                    atual[campo] = rec[campo]
            if _preenchido(rec.get("company_slug")):
                atual["company_slug"] = rec["company_slug"]
            atual["keywords_matched"] = apg.unir(atual.get("keywords_matched") or [], rec.get("keywords_matched") or [])
            a, b = apg.instante(atual.get("collected_at")), apg.instante(rec.get("collected_at"))
            if b and (a is None or b < a):
                atual["collected_at"] = rec["collected_at"]
        self.primeiro[chave] = min(self.primeiro.get(chave, visto), visto)
        self.ultimo[chave] = max(self.ultimo.get(chave, visto), visto)
        return chave

    def so_ausente(self, rec: dict, visto: datetime) -> bool:
        """Regra do export do Supabase: chave nova entra; chave existente só ganha campo vazio. True se a chave era nova."""
        chave = rec.get("dedupe_key") or common.dedupe_key(rec)
        atual = self.itens.get(chave)
        if atual is None:
            self.fundir(rec, rec.get("kind") or "news", visto)
            return True
        for campo in (*CAMPOS_MAIS_RECENTE, "company_slug"):
            if not _preenchido(atual.get(campo)) and _preenchido(rec.get(campo)):
                atual[campo] = rec[campo]
        return False


@dataclass
class Carga:
    ref: str
    sha: str
    linhas: list[dict]
    execucoes: list[dict]
    newsletters: list[dict]
    catalogos: dict[str, list[dict]]
    relatorio: dict
    conferencia: dict[str, dict[str, list[str]]] = field(default_factory=dict)


def _commits(git: Git, ref: str) -> list[tuple[str, datetime]]:
    out = []
    for linha in git.run("log", "--reverse", "--format=%H %cI", ref).splitlines():
        sha, quando = linha.split(" ", 1)
        out.append((sha, apg.instante(quando)))
    return out


def montar(repo: Path, ref: str, supabase: Path | None = None, conferir: tuple[str, ...] = COMMITS_A_CONFERIR) -> Carga:
    git = Git(repo)
    try:
        sha_ref = git.run("rev-parse", ref).strip()
        caminhos = [p for p, _ in ARQUIVOS_DE_ITEM]
        kind_de = dict(ARQUIVOS_DE_ITEM)

        # cada versão (blob) de cada arquivo, com o primeiro e o último commit que a contêm
        versoes: dict[tuple[str, str], list[datetime]] = {}
        commits = _commits(git, ref)
        for sha, quando in commits:
            for caminho, blob in git.ls(sha, *caminhos).items():
                v = versoes.setdefault((caminho, blob), [quando, quando, sha])  # type: ignore[list-item]
                v[0], v[1] = min(v[0], quando), max(v[1], quando)
        no_ref = git.ls(sha_ref, *caminhos)

        uniao = Uniao()
        ref_por_arquivo: dict[str, set[str]] = {p: set() for p in caminhos}
        chaves_ref: set[str] = set()
        chaves_hist: set[str] = set()
        nao_parseia = []
        ordem_arquivo = {p: i for i, p in enumerate(caminhos)}
        fila = sorted(
            (k for k in versoes if no_ref.get(k[0]) != k[1]),
            key=lambda k: (versoes[k][0], ordem_arquivo[k[0]]),
        )
        fila += [(p, no_ref[p]) for p in caminhos if p in no_ref]  # o ref por último: o registro de hoje vence
        for caminho, blob in fila:
            primeiro, ultimo, sha = versoes[(caminho, blob)]
            try:
                dado = json.loads(git.blob(blob).decode("utf-8"))
                if not isinstance(dado, list):
                    raise ValueError("não é lista")
            except (ValueError, UnicodeDecodeError) as exc:
                nao_parseia.append({"arquivo": caminho, "commit": sha[:7], "erro": str(exc)[:120]})
                continue
            eh_ref = no_ref.get(caminho) == blob
            for rec in dado:
                chave = uniao.fundir(rec, kind_de[caminho], ultimo)
                if chave is None:
                    continue
                uniao.primeiro[chave] = min(uniao.primeiro[chave], primeiro)
                (chaves_ref if eh_ref else chaves_hist).add(chave)
                if eh_ref:
                    ref_por_arquivo[caminho].add(chave)

        # export do Supabase: só o que falta
        sup = {"itens": 0, "novas": 0, "newsletters": 0}
        sup_newsletters: dict[str, str] = {}
        if supabase is not None:
            itens_sup, sup_newsletters = ler_export_supabase(supabase)
            agora = datetime.now(timezone.utc)
            sup["itens"] = len(itens_sup)
            for rec in itens_sup:
                if uniao.so_ausente(rec, apg.instante(rec.get("collected_at")) or agora):
                    sup["novas"] += 1
            sup["newsletters"] = len(sup_newsletters)

        # as linhas de radar.item
        lote_recusados = []
        linhas = []
        recalculo_difere = 0
        for chave in sorted(uniao.itens):
            rec = uniao.itens[chave]
            if common.dedupe_key(rec) != chave:
                recalculo_difere += 1
            try:
                linhas.append(apg.para_linha(rec, coletores=(), visto_em=uniao.ultimo[chave],
                                             execucao=None, coletado_padrao=uniao.primeiro[chave]))
            except ValueError as exc:
                lote_recusados.append({"dedupe_key": chave[:120], "motivo": str(exc)})

        # os commits a conferir (D3). Duas medidas, porque a spec contou por arquivo: uma chave de
        # companies_activity.json que sumiu de lá mas segue em news.json perdeu a empresa, não o item.
        perdidas: dict[str, dict] = {}
        conferencia: dict[str, dict[str, list[str]]] = {}
        for c in conferir:
            por_arquivo: dict[str, set[str]] = {}
            for caminho, blob in git.ls(c, *caminhos).items():
                try:
                    por_arquivo[caminho] = {r.get("dedupe_key") or common.dedupe_key(r)
                                            for r in json.loads(git.blob(blob).decode("utf-8"))}
                except ValueError:
                    por_arquivo[caminho] = set()
            chaves_c = set().union(*por_arquivo.values()) if por_arquivo else set()
            fora_do_arquivo = set().union(*(ks - ref_por_arquivo[p] for p, ks in por_arquivo.items())) if por_arquivo else set()
            de_empresa = por_arquivo.get("pipeline/data/companies_activity.json", set()) - ref_por_arquivo["pipeline/data/companies_activity.json"]
            itens_perdidos = chaves_c - chaves_ref
            perdidas[c] = {
                "chaves_no_commit": len(chaves_c),
                "ausentes_do_mesmo_arquivo_no_ref": len(fora_do_arquivo),
                "itens_ausentes_do_ref": len(itens_perdidos),
                "so_perderam_a_empresa": len(fora_do_arquivo - itens_perdidos),
                "ausentes_na_carga": sum(1 for k in fora_do_arquivo if k not in uniao.itens),
                "de_empresa_sem_slug_na_carga": sum(1 for k in de_empresa if not uniao.itens.get(k, {}).get("company_slug")),
            }
            conferencia[c] = {"chaves": sorted(fora_do_arquivo), "de_empresa": sorted(de_empresa)}

        execucoes = _execucoes(git, sha_ref)
        newsletters = _newsletters(git, sha_ref)
        datas = {n["data"] for n in newsletters}
        newsletters += [{"data": d, "markdown": md} for d, md in sorted(sup_newsletters.items()) if d not in datas]
        catalogos = {
            tipo: apg.entradas_de_catalogo(tipo, yaml.safe_load(git.blob(git.ls(sha_ref, f"pipeline/config/{arq}")[f"pipeline/config/{arq}"])))
            for tipo, arq in apg.TIPOS_DE_CATALOGO.items()
        }
    finally:
        git.fechar()

    so_hist = chaves_hist - chaves_ref
    relatorio = {
        "ref": ref,
        "sha": sha_ref[:12],
        "commits_lidos": len(commits),
        "versoes_de_arquivo": len(versoes),
        "versoes_que_nao_parseiam": nao_parseia,
        "origens": {
            "json_do_ref": {"chaves": len(chaves_ref), "novas_na_uniao": len(chaves_ref)},
            "historico_do_git": {"chaves": len(chaves_hist | chaves_ref), "novas_na_uniao": len(so_hist)},
            "export_do_supabase": {"lido": supabase is not None, "itens": sup["itens"], "novas_na_uniao": sup["novas"],
                                   "newsletters": sup["newsletters"]},
        },
        "uniao": len(uniao.itens),
        "linhas": len(linhas),
        "recusados": lote_recusados,
        "chave_gravada_difere_do_recalculo": recalculo_difere,
        "perdidas": perdidas,
        "execucoes": len(execucoes),
        "newsletters": len(newsletters),
        "catalogos": {t: len(v) for t, v in catalogos.items()},
    }
    return Carga(ref, sha_ref, linhas, execucoes, newsletters, catalogos, relatorio, conferencia)


def _execucoes(git: Git, ref: str) -> list[dict]:
    out = []
    for caminho, blob in sorted(git.ls(ref, "pipeline/data/runs").items()):
        if not caminho.endswith("-pipeline_run.json"):
            continue
        try:
            d = json.loads(git.blob(blob).decode("utf-8"))
        except ValueError:
            continue
        ini = apg.instante(d.get("last_run_started"))
        if ini is None:
            continue
        fim = apg.instante(d.get("last_run_finished"))
        col = d.get("collectors") or {}
        out.append({
            "iniciada_em": ini.isoformat(),
            "terminada_em": fim.isoformat() if fim else None,
            # importada terminou e gravou o JSON: `ok` ou `parcial`, nunca `falhou`
            "estado": "ok" if apg.estado_da_execucao(col) == "ok" else "parcial",
            "duracao_s": d.get("duration_seconds"),
            "coletores": col,
            "totais": d.get("totals") or {},
        })
    out.sort(key=lambda e: e["iniciada_em"])  # o id segue a ordem do carimbo
    return out


def _newsletters(git: Git, ref: str) -> list[dict]:
    out = []
    for caminho, blob in sorted(git.ls(ref, "pipeline/data/newsletter").items()):
        m = NEWSLETTER_RE.match(caminho)
        if m:
            out.append({"data": m.group(1), "markdown": git.blob(blob).decode("utf-8").replace("\x00", "")})
    return out


# --- o export do Supabase -------------------------------------------------------------------------

def ler_export_supabase(pasta: Path) -> tuple[list[dict], dict[str, str]]:
    """Lê `items.json` e `newsletters.json` de `exportar_supabase.py`, conferindo o sha256 do `manifesto.json`."""
    manifesto = json.loads((pasta / "manifesto.json").read_text(encoding="utf-8"))
    dados = {}
    for tabela in ("items", "newsletters"):
        info = manifesto["tabelas"].get(tabela)
        if info is None:
            continue
        bruto = (pasta / f"{tabela}.json").read_bytes()
        if hashlib.sha256(bruto).hexdigest() != info["sha256"]:
            raise RuntimeError(f"export do Supabase: {tabela}.json não confere com o manifesto")
        dados[tabela] = json.loads(bruto)
        if len(dados[tabela]) != info["linhas"]:
            raise RuntimeError(f"export do Supabase: {tabela}.json tem {len(dados[tabela])} linhas, o manifesto diz {info['linhas']}")
    itens = [{k: v for k, v in r.items() if k not in ("id", "inserted_at", "updated_at")} for r in dados.get("items", [])]
    news = {str(r["date"])[:10]: r.get("content") or "" for r in dados.get("newsletters", [])}
    return itens, news


# --- pacote ---------------------------------------------------------------------------------------

def salvar_pacote(carga: Carga, destino: Path) -> str:
    corpo = apg._json({
        "formato": FORMATO_DO_PACOTE, "ref": carga.ref, "sha": carga.sha,
        "gerado_em": datetime.now(timezone.utc).isoformat(), "relatorio": carga.relatorio,
        "itens": carga.linhas, "execucoes": carga.execucoes, "newsletters": carga.newsletters,
        "catalogos": carga.catalogos, "conferencia": carga.conferencia,
    }).encode("utf-8")
    destino.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(destino, "wb", compresslevel=6) as fh:
        fh.write(corpo)
    return hashlib.sha256(destino.read_bytes()).hexdigest()


def ler_pacote(origem: Path) -> Carga:
    with gzip.open(origem, "rb") as fh:
        d = json.loads(fh.read().decode("utf-8"))
    if d.get("formato") != FORMATO_DO_PACOTE:
        raise RuntimeError(f"pacote de formato {d.get('formato')}, este código lê {FORMATO_DO_PACOTE}")
    return Carga(d["ref"], d["sha"], d["itens"], d["execucoes"], d["newsletters"], d["catalogos"], d["relatorio"],
                 d.get("conferencia") or {})


# --- a carga no banco -----------------------------------------------------------------------------

SQL_EXECUCAO_IMPORTADA = """
insert into radar.execucao (origem, versao, iniciada_em, terminada_em, estado, duracao_s, coletores, totais)
select 'importada', null, %(iniciada_em)s, %(terminada_em)s, %(estado)s, %(duracao_s)s, %(coletores)s::jsonb, %(totais)s::jsonb
where not exists (select 1 from radar.execucao where origem = 'importada' and iniciada_em = %(iniciada_em)s)
returning id
"""

SQL_NEWSLETTER = """
insert into radar.newsletter as n (data, markdown) values (%s, %s)
on conflict (data) do update set markdown = excluded.markdown where n.markdown is distinct from excluded.markdown
returning (n.xmax = 0) as inserido
"""


def _contagens(cur: Any) -> dict[str, int]:
    cur.execute(
        "select (select count(*) from radar.item), (select count(*) from radar.execucao where origem = 'importada'), "
        "(select count(*) from radar.newsletter), (select count(*) from radar.catalogo)"
    )
    i, e, n, c = cur.fetchone()
    return {"item": i, "execucao_importada": e, "newsletter": n, "catalogo": c}


def presentes(cur: Any, chaves: list[str]) -> int:
    total = 0
    for ini in range(0, len(chaves), 5000):
        cur.execute("select count(*) from radar.item where dedupe_key = any(%s)", (chaves[ini:ini + 5000],))
        total += cur.fetchone()[0]
    return total


def carregar(url: str, carga: Carga, dry_run: bool = False) -> dict:
    """Grava a carga numa transação, com a trava do Radar. Devolve contagens antes e depois e a conferência."""
    conn = apg.conectar(url)
    try:
        if not apg.tentar_trava(conn):
            raise RuntimeError("outra execução do Radar tem a trava: espere a coleta terminar")
        apg.conferir_contrato(conn)
        chaves = [l["dedupe_key"] for l in carga.linhas]
        with conn.cursor() as cur:
            antes = _contagens(cur)
            ja = presentes(cur, chaves)
        out: dict[str, Any] = {"antes": antes, "chaves_da_carga_ja_no_banco": ja, "chaves_da_carga": len(chaves)}
        if dry_run:
            return out
        with conn.transaction(), conn.cursor() as cur:
            cont = apg.gravar_itens(cur, carga.linhas)
            # Depois da primeira coleta da VM, nenhum snapshot é importado: a view radar.meta pega o MAIOR ID terminado,
            # e qualquer linha importada depois (a carga final do R6) ganharia id maior que a última coleta real e
            # tomaria o lugar dela na tela, mesmo sendo mais antiga. Dali em diante o histórico é o da VM.
            cur.execute("select exists (select 1 from radar.execucao where origem <> 'importada')")
            (ha_coleta_viva,) = cur.fetchone()
            exec_novas = exec_puladas = 0
            for e in carga.execucoes:
                if ha_coleta_viva:
                    exec_puladas += 1
                    continue
                cur.execute(SQL_EXECUCAO_IMPORTADA, {**e, "coletores": apg._json(e["coletores"]), "totais": apg._json(e["totais"])})
                exec_novas += len(cur.fetchall())
            news = {"novas": 0, "atualizadas": 0}
            for n in carga.newsletters:
                cur.execute(SQL_NEWSLETTER, (n["data"], n["markdown"]))
                for (ins,) in cur.fetchall():
                    news["novas" if ins else "atualizadas"] += 1
            cats = apg.gravar_catalogos(cur, carga.catalogos)
        with conn.cursor() as cur:
            depois = _contagens(cur)
            conferidas = presentes(cur, chaves)
            cur.execute("select count(*) from radar.item where kind = 'news' and company_slug is null and dedupe_key = any(%s)",
                        ([l["dedupe_key"] for l in carga.linhas if l["company_slug"]],))
            empresa_sem_slug = cur.fetchone()[0]
            recuperadas = {}
            for c, conf in carga.conferencia.items():
                cur.execute("select count(*) from radar.item where dedupe_key = any(%s) and company_slug is null",
                            (conf["de_empresa"],))
                sem_slug = cur.fetchone()[0]
                recuperadas[c] = {"chaves": len(conf["chaves"]), "no_banco": presentes(cur, conf["chaves"]),
                                  "de_empresa": len(conf["de_empresa"]), "de_empresa_sem_slug": sem_slug}
        out.update({
            "itens": {"novos": cont.total()[0], "atualizados": cont.total()[1], "por_tipo": cont.novos},
            "execucoes_novas": exec_novas, "execucoes_puladas_por_haver_coleta_da_vm": exec_puladas,
            "newsletters": news, "catalogos": cats,
            "depois": depois, "chaves_da_carga_no_banco": conferidas, "empresa_sem_slug": empresa_sem_slug,
            "recuperadas": recuperadas,
        })
        return out
    finally:
        try:
            apg.liberar_trava(conn)
        except Exception:  # noqa: BLE001
            pass
        conn.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Carga inicial do Radar no esquema radar do System")
    ap.add_argument("--repo", type=Path, default=common.REPO_ROOT, help="Checkout com o histórico do git")
    ap.add_argument("--ref", default="origin/main", help="O commit da virada (padrão origin/main)")
    ap.add_argument("--supabase", type=Path, default=None, help="Pasta do export (exportar_supabase.py), se houver")
    ap.add_argument("--pacote", type=Path, default=None, help="Carrega deste pacote em vez de ler o git")
    ap.add_argument("--salvar-pacote", type=Path, default=None, help="Grava o pacote e sai (não toca banco)")
    ap.add_argument("--dry-run", action="store_true", help="Só conta; com DATABASE_URL_RADAR, conta também o que já está no banco")
    args = ap.parse_args(argv)

    carga = ler_pacote(args.pacote) if args.pacote else montar(args.repo, args.ref, args.supabase)
    apg.evento("radar.carga.montada", **carga.relatorio)
    if args.salvar_pacote:
        sha = salvar_pacote(carga, args.salvar_pacote)
        apg.evento("radar.carga.pacote", arquivo=args.salvar_pacote.name, sha256=sha, bytes=args.salvar_pacote.stat().st_size)
        return 0
    url = (os.environ.get("DATABASE_URL_RADAR") or "").strip()
    if not url:
        if args.dry_run:
            return 0
        apg.evento("radar.carga.falhou", motivo="DATABASE_URL_RADAR ausente no ambiente")
        return 1
    try:
        res = carregar(url, carga, dry_run=args.dry_run)
    except Exception as exc:  # noqa: BLE001
        apg.evento("radar.carga.falhou", erro=apg.sem_segredo(f"{type(exc).__name__}: {exc}", url))
        return 1
    ok = args.dry_run or (
        res["chaves_da_carga_no_banco"] == len(carga.linhas)
        and res["empresa_sem_slug"] == 0
        and all(r["no_banco"] == r["chaves"] and r["de_empresa_sem_slug"] == 0 for r in res["recuperadas"].values())
    )
    apg.evento("radar.carga.dry_run" if args.dry_run else ("radar.carga.fim" if ok else "radar.carga.divergente"), **res)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
