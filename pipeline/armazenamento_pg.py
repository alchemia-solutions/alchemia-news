"""O escritor do Radar no Postgres do System (spec docs/specs/2026-10-02-radar-na-vm-postgres.md).

Substitui, no modo `--destino postgres` do `run_all`, o ciclo `load_json` -> `merge_items` -> `save_json`.
O esquema `radar` é do System (migração Drizzle dele); este módulo só escreve, com o papel `alchemia_radar`,
e nunca roda DDL. Por isso confere o contrato de colunas antes de gravar: uma migração do System que mude
`radar.*` vira falha alta e nomeada aqui, e não um defeito silencioso na tela.

Uma execução (`executar`):
  1. `pg_try_advisory_lock(TRAVA_RADAR)`; sem a trava, evento `radar.execucao.ocupado` e saída 0;
  2. confere as colunas de `radar.*` (`conferir_contrato`); divergência é saída 1 com a diferença;
  3. marca como `falhou` toda execução `rodando` que sobrou de um processo morto (com a trava na mão,
     nenhuma outra está viva) e abre a linha da execução com `estado = 'rodando'`;
  4. roda os coletores (inalterados);
  5. numa transação: upsert dos itens (só preenche campo vazio), dos catálogos e o fechamento da execução;
  6. libera a trava.

Nunca há leitura-modificação-escrita do acervo inteiro: a classe de defeito de 2026-09-07 (JSON corrompido
lido como vazio e gravado por cima) não tem como acontecer aqui. Pela mesma razão, um catálogo YAML vazio
é recusado em vez de apagar o catálogo do banco.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))

from collectors import common  # noqa: E402

try:
    import psycopg  # type: ignore
except ImportError:  # pragma: no cover - só o modo postgres precisa; o Actions roda sem
    psycopg = None  # type: ignore[assignment]

# "RADAR" em ASCII: a mesma constante em toda execução e no migrador, para os dois nunca se sobreporem.
TRAVA_RADAR = int.from_bytes(b"RADAR", "big")

# O limite que o `check` da coluna impõe (spec, "Chave natural, não uuid"): acima dele a B-tree recusaria.
MAX_BYTES_CHAVE = 2000
LOTE = 500

TIPOS_DE_CATALOGO = {
    "companies": "companies.yaml",
    "resources": "resources.yaml",
    "funding_channels": "funding_channels.yaml",
    "corporate_programs": "corporate_programs.yaml",
}

# O contrato com a migração do System: coluna -> udt_name do information_schema. Igualdade estrita nos dois
# sentidos: coluna a mais também reprova, porque mudar `radar.*` exige combinar com este nó.
CONTRATO: dict[str, dict[str, str]] = {
    "execucao": {
        "id": "int8", "origem": "text", "versao": "text", "iniciada_em": "timestamptz",
        "terminada_em": "timestamptz", "estado": "text", "duracao_s": "numeric",
        "coletores": "jsonb", "totais": "jsonb",
    },
    "item": {
        "dedupe_key": "text", "kind": "text", "title": "text", "url": "text", "source": "text",
        "source_type": "text", "published_date": "date", "collected_at": "timestamptz",
        "authors": "_text", "summary": "text", "doi": "text", "company_slug": "text",
        "keywords_matched": "_text", "coletores": "_text", "extra": "jsonb",
        "primeira_execucao": "int8", "vista_em": "timestamptz", "atualizado_em": "timestamptz",
    },
    "catalogo": {
        "tipo": "text", "slug": "text", "posicao": "int4", "dados": "jsonb", "atualizado_em": "timestamptz",
    },
    "newsletter": {"data": "date", "markdown": "text"},
}

# Os coletores de artigo, pela chave do `run_all`; os demais produzem notícia.
COLETORES_DE_ARTIGO = ("pubmed", "biorxiv", "arxiv", "chemrxiv", "scielo")


class ContratoDivergente(RuntimeError):
    """As colunas de `radar.*` no banco não são as que este código grava."""


class CatalogoInvalido(ValueError):
    """Um YAML de catálogo veio vazio, sem `slug` ou com `slug` repetido: não se grava nem se apaga nada."""


# --- log ------------------------------------------------------------------------------------------

def evento(nome: str, **campos: Any) -> None:
    """Uma linha JSON por evento no stdout (spec, "Logs"). Nunca recebe a URL do banco."""
    linha = {"evento": nome, "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), **campos}
    print(json.dumps(linha, ensure_ascii=False, default=str), flush=True)


def sem_segredo(texto: str, url: str | None) -> str:
    """Tira da mensagem a URL do banco e a senha dela, se o driver as tiver repetido."""
    texto = common.sanitize_local_path(texto or "")
    if url:
        texto = texto.replace(url, "<DATABASE_URL_RADAR>")
        m = re.match(r"^[a-z]+://[^:/@]+:([^@]+)@", url)
        if m and m.group(1):
            texto = texto.replace(m.group(1), "<senha>")
    return re.sub(r"(postgres(?:ql)?://[^:/@\s]+:)[^@\s]+@", r"\1<senha>@", texto)


# --- normalização de um item para a linha de `radar.item` -------------------------------------------

_DATA_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def _sem_nul(valor: Any) -> Any:
    """O Postgres recusa U+0000 em `text` e em `jsonb`; feed de terceiro às vezes o entrega."""
    if isinstance(valor, str):
        return valor.replace("\x00", "")
    if isinstance(valor, list):
        return [_sem_nul(v) for v in valor]
    if isinstance(valor, dict):
        return {_sem_nul(k): _sem_nul(v) for k, v in valor.items()}
    return valor


def data_publicada(valor: Any) -> str | None:
    """`AAAA-MM-DD` válida, ou None. A data 1970-01-01 que alguns feeds mandam vira None (spec, `published_date`)."""
    if not isinstance(valor, str):
        return None
    m = _DATA_RE.match(valor.strip())
    if not m:
        return None
    try:
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None
    return None if d.year == 1970 else d.isoformat()


def instante(valor: Any) -> datetime | None:
    """ISO-8601 com fuso; sem fuso, presume UTC (é como o pipeline sempre gravou)."""
    if isinstance(valor, datetime):
        dt = valor
    elif isinstance(valor, str) and valor.strip():
        try:
            dt = datetime.fromisoformat(valor.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _texto(valor: Any) -> str:
    return valor if isinstance(valor, str) else ("" if valor is None else str(valor))


def unir(*listas: Iterable[Any]) -> list[str]:
    """União que preserva a ordem de chegada, só com texto não vazio."""
    vistos: dict[str, None] = {}
    for lista in listas:
        for v in lista or []:
            if isinstance(v, str) and v.strip():
                vistos.setdefault(v, None)
    return list(vistos)


def para_linha(item: dict, *, coletores: Iterable[str] = (), visto_em: datetime,
               execucao: int | None = None, coletado_padrao: datetime | None = None) -> dict:
    """O item do coletor (formato `common.Item.to_dict`) na forma da linha de `radar.item`.

    Levanta ValueError com o motivo quando o item não cabe na tabela (chave grande demais, `kind` fora do
    contrato, sem data de coleta): quem chama conta e relata, nunca descarta calado.
    """
    item = _sem_nul(item)
    chave = item.get("dedupe_key") or common.dedupe_key(item)
    if len(chave.encode("utf-8")) > MAX_BYTES_CHAVE:
        raise ValueError(f"dedupe_key com {len(chave.encode('utf-8'))} bytes (máximo {MAX_BYTES_CHAVE})")
    kind = item.get("kind")
    if kind not in ("article", "news"):
        raise ValueError(f"kind fora do contrato: {kind!r}")
    coletado = instante(item.get("collected_at")) or coletado_padrao
    if coletado is None:
        raise ValueError("sem collected_at")
    autores = item.get("authors")
    extra = item.get("extra")
    return {
        "dedupe_key": chave,
        "kind": kind,
        "title": _texto(item.get("title")),
        "url": _texto(item.get("url")),
        "source": _texto(item.get("source")),
        "source_type": _texto(item.get("source_type")),
        "published_date": data_publicada(item.get("published_date")),
        "collected_at": coletado.isoformat(),
        "authors": [_texto(a) for a in autores] if isinstance(autores, list) else [],
        "summary": _texto(item.get("summary")),
        "doi": _texto(item.get("doi")).strip() or None,
        "company_slug": _texto(item.get("company_slug")).strip() or None,
        "keywords_matched": unir(item.get("keywords_matched") or []),
        "coletores": unir(coletores),
        "extra": extra if isinstance(extra, dict) else {},
        "primeira_execucao": execucao,
        "vista_em": visto_em.isoformat(),
    }


def fundir_linhas(primeira: dict, outra: dict) -> dict:
    """Duas linhas com a mesma chave no MESMO lote (um item que dois coletores acharam): a regra do upsert, em Python.

    Fica o primeiro registro, como o `merge_items` de hoje; campo vazio é preenchido pelo segundo; `company_slug`
    não nulo entra (era o defeito dos 113 itens divergentes); termos e coletores se unem. O Postgres não aceita a
    mesma chave duas vezes num só `insert ... on conflict`, então o lote chega já fundido.
    """
    r = dict(primeira)
    for campo in ("summary", "authors", "published_date", "doi", "company_slug"):
        if not r.get(campo) and outra.get(campo):
            r[campo] = outra[campo]
    r["keywords_matched"] = unir(r["keywords_matched"], outra["keywords_matched"])
    r["coletores"] = unir(r["coletores"], outra["coletores"])
    r["collected_at"] = min(r["collected_at"], outra["collected_at"], key=lambda s: instante(s))
    r["vista_em"] = max(r["vista_em"], outra["vista_em"], key=lambda s: instante(s))
    return r


@dataclass
class Lote:
    """Linhas prontas para o upsert, uma por chave, e o que ficou de fora com o motivo."""

    linhas: dict[str, dict] = field(default_factory=dict)
    recusados: list[dict] = field(default_factory=list)

    def acrescentar(self, item: dict, **kw: Any) -> None:
        try:
            linha = para_linha(item, **kw)
        except ValueError as exc:
            self.recusados.append({"motivo": str(exc), "url": _texto(item.get("url"))[:200]})
            return
        anterior = self.linhas.get(linha["dedupe_key"])
        self.linhas[linha["dedupe_key"]] = fundir_linhas(anterior, linha) if anterior else linha


# --- SQL ------------------------------------------------------------------------------------------

_COLUNAS_ITEM = (
    "dedupe_key", "kind", "title", "url", "source", "source_type", "published_date", "collected_at",
    "authors", "summary", "doi", "company_slug", "keywords_matched", "coletores", "extra",
    "primeira_execucao", "vista_em",
)
_TIPOS_ITEM = (
    "dedupe_key text, kind text, title text, url text, source text, source_type text, published_date date, "
    "collected_at timestamptz, authors text[], summary text, doi text, company_slug text, "
    "keywords_matched text[], coletores text[], extra jsonb, primeira_execucao bigint, vista_em timestamptz"
)

# Só preenche campo vazio, como o `merge_items`; `collected_at` fica o mais antigo; termos e coletores se unem
# preservando a ordem. O `where` repete as mesmas condições: linha sem mudança real não é atualizada nem
# devolvida, e por isso `atualizados` conta mudança de verdade (a idempotência do critério 3 se mede por ele).
# `vista_em` anda num `update` à parte, para não contar como atualização.
SQL_UPSERT_ITEM = f"""
insert into radar.item as i ({", ".join(_COLUNAS_ITEM)})
select {", ".join(_COLUNAS_ITEM)} from jsonb_to_recordset(%(linhas)s::jsonb) as v({_TIPOS_ITEM})
on conflict (dedupe_key) do update set
  summary          = case when i.summary = '' then excluded.summary else i.summary end,
  authors          = case when cardinality(i.authors) = 0 then excluded.authors else i.authors end,
  published_date   = coalesce(i.published_date, excluded.published_date),
  doi              = coalesce(i.doi, excluded.doi),
  company_slug     = coalesce(i.company_slug, excluded.company_slug),
  collected_at     = least(i.collected_at, excluded.collected_at),
  keywords_matched = i.keywords_matched
                     || array(select k from unnest(excluded.keywords_matched) as k where not (k = any(i.keywords_matched))),
  coletores        = i.coletores
                     || array(select c from unnest(excluded.coletores) as c where not (c = any(i.coletores))),
  atualizado_em    = now()
where (i.summary = '' and excluded.summary <> '')
   or (cardinality(i.authors) = 0 and cardinality(excluded.authors) > 0)
   or (i.published_date is null and excluded.published_date is not null)
   or (i.doi is null and excluded.doi is not null)
   or (i.company_slug is null and excluded.company_slug is not null)
   or excluded.collected_at < i.collected_at
   or not (excluded.keywords_matched <@ i.keywords_matched)
   or not (excluded.coletores <@ i.coletores)
returning i.kind, (i.xmax = 0) as inserido, (i.company_slug is not null) as de_empresa
"""

SQL_VISTA_EM = """
update radar.item as i set vista_em = v.vista_em
from jsonb_to_recordset(%(linhas)s::jsonb) as v(dedupe_key text, vista_em timestamptz)
where i.dedupe_key = v.dedupe_key and i.vista_em < v.vista_em
"""

SQL_UPSERT_CATALOGO = """
insert into radar.catalogo as c (tipo, slug, posicao, dados)
select %(tipo)s, v.slug, v.posicao, v.dados from jsonb_to_recordset(%(linhas)s::jsonb) as v(slug text, posicao int, dados jsonb)
on conflict (tipo, slug) do update set posicao = excluded.posicao, dados = excluded.dados, atualizado_em = now()
where (c.posicao, c.dados) is distinct from (excluded.posicao, excluded.dados)
returning (c.xmax = 0) as inserido
"""


def _json(valor: Any) -> str:
    """JSON para o parâmetro `jsonb`. O PyYAML lê `2026-08-19` sem aspas como `date`: vira texto ISO, como no System."""
    def padrao(o: Any) -> Any:
        if isinstance(o, (date, datetime)):
            return o.isoformat()
        raise TypeError(f"tipo sem conversão para JSON: {type(o).__name__}")
    return json.dumps(valor, ensure_ascii=False, default=padrao)


@dataclass
class Contagem:
    novos: dict[str, int] = field(default_factory=lambda: {"article": 0, "news": 0, "companies": 0})
    atualizados: dict[str, int] = field(default_factory=lambda: {"article": 0, "news": 0, "companies": 0})

    def total(self) -> tuple[int, int]:
        return self.novos["article"] + self.novos["news"], self.atualizados["article"] + self.atualizados["news"]


def gravar_itens(cur: Any, linhas: Iterable[dict]) -> Contagem:
    """Upsert em lotes de `LOTE`, dentro da transação de quem chama. `companies` conta o subconjunto com empresa."""
    todas = list(linhas)
    cont = Contagem()
    for ini in range(0, len(todas), LOTE):
        bloco = todas[ini:ini + LOTE]
        cur.execute(SQL_UPSERT_ITEM, {"linhas": _json(bloco)})
        for kind, inserido, de_empresa in cur.fetchall():
            alvo = cont.novos if inserido else cont.atualizados
            alvo[kind] += 1
            if de_empresa:
                alvo["companies"] += 1
        cur.execute(SQL_VISTA_EM, {"linhas": _json([{"dedupe_key": l["dedupe_key"], "vista_em": l["vista_em"]} for l in bloco])})
    return cont


def entradas_de_catalogo(tipo: str, dado_yaml: Any) -> list[dict]:
    """A lista do YAML (`<tipo>: [...]`) na ordem do arquivo. Vazia, sem `slug` ou com `slug` repetido: recusa."""
    lista = dado_yaml.get(tipo) if isinstance(dado_yaml, dict) else None
    if not isinstance(lista, list) or not lista:
        raise CatalogoInvalido(f"{TIPOS_DE_CATALOGO[tipo]}: sem a lista '{tipo}' ou vazia")
    vistos: set[str] = set()
    out = []
    for pos, entrada in enumerate(lista):
        slug = entrada.get("slug") if isinstance(entrada, dict) else None
        if not isinstance(slug, str) or not slug.strip():
            raise CatalogoInvalido(f"{TIPOS_DE_CATALOGO[tipo]}: entrada {pos} sem slug")
        if slug in vistos:
            raise CatalogoInvalido(f"{TIPOS_DE_CATALOGO[tipo]}: slug repetido {slug!r}")
        vistos.add(slug)
        out.append({"slug": slug, "posicao": pos, "dados": entrada})
    return out


def ler_catalogos() -> dict[str, list[dict]]:
    """Os quatro YAML de `pipeline/config/`, validados. Levanta CatalogoInvalido antes de qualquer escrita."""
    return {tipo: entradas_de_catalogo(tipo, common.load_yaml(arq)) for tipo, arq in TIPOS_DE_CATALOGO.items()}


def gravar_catalogos(cur: Any, catalogos: dict[str, list[dict]]) -> dict[str, dict[str, int]]:
    """Upsert de cada catálogo e remoção, na mesma transação, do `slug` que saiu do YAML."""
    out: dict[str, dict[str, int]] = {}
    for tipo, entradas in catalogos.items():
        if not entradas:
            raise CatalogoInvalido(f"{tipo}: catálogo vazio, nada é apagado")
        cur.execute(SQL_UPSERT_CATALOGO, {"tipo": tipo, "linhas": _json(entradas)})
        res = cur.fetchall()
        novos = sum(1 for (ins,) in res if ins)
        cur.execute(
            "delete from radar.catalogo where tipo = %s and not (slug = any(%s)) returning slug",
            (tipo, [e["slug"] for e in entradas]),
        )
        out[tipo] = {"novos": novos, "atualizados": len(res) - novos, "removidos": len(cur.fetchall())}
    return out


def totais_do_banco(cur: Any) -> dict[str, int]:
    cur.execute(
        "select count(*) filter (where kind = 'article'), count(*) filter (where kind = 'news'), "
        "count(*) filter (where kind = 'news' and company_slug is not null) from radar.item"
    )
    a, n, c = cur.fetchone()
    return {"articles": a, "news": n, "companies_activity": c}


# --- conexão, trava e contrato --------------------------------------------------------------------

def conectar(url: str):
    if psycopg is None:
        raise RuntimeError("psycopg não está instalado: pip install -r pipeline/requirements-pg.txt")
    return psycopg.connect(url, autocommit=True, connect_timeout=15, application_name="alchemia-radar")


def tentar_trava(conn: Any) -> bool:
    return bool(conn.execute("select pg_try_advisory_lock(%s)", (TRAVA_RADAR,)).fetchone()[0])


def liberar_trava(conn: Any) -> None:
    conn.execute("select pg_advisory_unlock(%s)", (TRAVA_RADAR,))


def conferir_contrato(conn: Any) -> None:
    """Compara as colunas de `radar.*` visíveis ao papel com `CONTRATO`. Levanta ContratoDivergente com a diferença."""
    rows = conn.execute(
        "select table_name, column_name, udt_name from information_schema.columns "
        "where table_schema = 'radar' and table_name = any(%s)",
        (list(CONTRATO),),
    ).fetchall()
    no_banco: dict[str, dict[str, str]] = {}
    for tabela, coluna, tipo in rows:
        no_banco.setdefault(tabela, {})[coluna] = tipo
    dif = []
    for tabela, esperado in CONTRATO.items():
        real = no_banco.get(tabela, {})
        if not real:
            dif.append(f"radar.{tabela}: ausente ou sem privilégio para este papel")
            continue
        faltam = sorted(set(esperado) - set(real))
        sobram = sorted(set(real) - set(esperado))
        tipos = sorted(c for c in set(esperado) & set(real) if esperado[c] != real[c])
        if faltam:
            dif.append(f"radar.{tabela}: faltam {faltam}")
        if sobram:
            dif.append(f"radar.{tabela}: colunas não combinadas {sobram}")
        for c in tipos:
            dif.append(f"radar.{tabela}.{c}: tipo {real[c]}, esperado {esperado[c]}")
    if dif:
        raise ContratoDivergente("; ".join(dif))


def fechar_orfas(conn: Any) -> int:
    """Com a trava na mão, nenhuma execução está viva: `rodando` é resto de processo morto."""
    cur = conn.execute(
        "update radar.execucao set estado = 'falhou' where estado = 'rodando' and origem <> 'importada' returning id"
    )
    ids = [r[0] for r in cur.fetchall()]
    if ids:
        evento("radar.execucao.orfa", ids=ids)
    return len(ids)


def abrir_execucao(conn: Any, origem: str, versao: str | None, iniciada: datetime) -> int:
    return conn.execute(
        "insert into radar.execucao (origem, versao, iniciada_em, estado) values (%s, %s, %s, 'rodando') returning id",
        (origem, versao, iniciada),
    ).fetchone()[0]


# --- a execução inteira ---------------------------------------------------------------------------

@dataclass
class Colheita:
    """O que os coletores devolveram: o relatório por coletor (formato de meta.json) e os itens de cada um."""

    coletores: dict[str, dict]
    itens: list[tuple[str, list[dict]]]


def estado_da_execucao(coletores: dict[str, dict]) -> str:
    """`ok` sem erro; `parcial` com erro em parte dos coletores; `falhou` se todo coletor que rodou falhou."""
    rodaram = [c for c in coletores.values() if not c.get("skipped")]
    com_erro = [c for c in rodaram if c.get("error")]
    if not com_erro:
        return "ok"
    return "falhou" if len(com_erro) == len(rodaram) else "parcial"


def executar(url: str, coletar: Callable[[], Colheita], *, origem: str, versao: str | None,
             catalogos: Callable[[], dict[str, list[dict]]] = ler_catalogos) -> int:
    """Uma coleta gravando no banco. Devolve o código de saída do processo (0 ok/parcial/ocupado, 1 falha)."""
    try:
        conn = conectar(url)
    except Exception as exc:  # noqa: BLE001 - banco fora do ar: log e saída 1, nada escrito em disco
        evento("radar.execucao.falhou", motivo="sem conexão com o banco", erro=sem_segredo(str(exc), url))
        return 1
    exec_id: int | None = None
    try:
        if not tentar_trava(conn):
            evento("radar.execucao.ocupado", motivo="outra execução tem a trava consultiva")
            return 0
        conferir_contrato(conn)
        cats = catalogos()
        fechar_orfas(conn)
        iniciada = datetime.now(timezone.utc)
        exec_id = abrir_execucao(conn, origem, versao, iniciada)
        evento("radar.execucao.inicio", id=exec_id, origem=origem, versao=versao)

        colheita = coletar()
        visto = datetime.now(timezone.utc)
        lote = Lote()
        for coletor, itens in colheita.itens:
            for it in itens:
                lote.acrescentar(it, coletores=[coletor], visto_em=visto, execucao=exec_id)
        for r in lote.recusados:
            evento("radar.item.recusado", **r)

        estado = estado_da_execucao(colheita.coletores)
        with conn.transaction():
            with conn.cursor() as cur:
                cont = gravar_itens(cur, lote.linhas.values())
                res_cat = gravar_catalogos(cur, cats)
                tot = totais_do_banco(cur)
                terminada = datetime.now(timezone.utc)
                totais = {
                    **tot,
                    "new_articles_this_run": cont.novos["article"],
                    "new_news_this_run": cont.novos["news"],
                    "new_companies_activity_this_run": cont.novos["companies"],
                }
                cur.execute(
                    "update radar.execucao set estado = %s, terminada_em = %s, duracao_s = %s, coletores = %s::jsonb, "
                    "totais = %s::jsonb where id = %s",
                    (
                        estado,
                        None if estado == "falhou" else terminada,
                        round((terminada - iniciada).total_seconds(), 1),
                        _json(colheita.coletores),
                        _json(totais),
                        exec_id,
                    ),
                )
        for cid, c in colheita.coletores.items():
            evento("radar.coletor", id=cid, count=c.get("count"), segundos=c.get("seconds"),
                   erro=bool(c.get("error")), pulado=bool(c.get("skipped")))
        evento(
            "radar.execucao.fim" if estado == "ok" else f"radar.execucao.{estado}",
            id=exec_id, estado=estado, totais=totais, atualizados=cont.atualizados,
            recusados=len(lote.recusados), catalogos=res_cat,
        )
        return 0 if estado != "falhou" else 1
    except ContratoDivergente as exc:
        evento("radar.execucao.falhou", motivo="contrato do esquema radar divergiu", diferenca=str(exc))
        return 1
    except CatalogoInvalido as exc:
        evento("radar.execucao.falhou", motivo="catálogo inválido", erro=str(exc))
        _marcar_falha(conn, exec_id)
        return 1
    except Exception as exc:  # noqa: BLE001 - qualquer outra falha fecha a execução como `falhou`, com saída 1
        evento("radar.execucao.falhou", id=exec_id, erro=sem_segredo(f"{type(exc).__name__}: {exc}", url))
        _marcar_falha(conn, exec_id)
        return 1
    finally:
        try:
            liberar_trava(conn)
        except Exception:  # noqa: BLE001 - conexão já perdida: o Postgres solta a trava ao fechar a sessão
            pass
        conn.close()


def _marcar_falha(conn: Any, exec_id: int | None) -> None:
    if exec_id is None:
        return
    try:
        conn.execute("update radar.execucao set estado = 'falhou' where id = %s and estado = 'rodando'", (exec_id,))
    except Exception:  # noqa: BLE001 - se nem isso grava, a próxima execução a fecha como órfã
        pass
