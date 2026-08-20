"""Utilidades compartilhadas do pipeline Alchemia News.

Sem dependência de banco de dados: armazenamento é arquivo JSON versionável (mesmo princípio já
usado em outros setores da Alchemia -- "dado grande fora do controle de versão, referenciado por
manifest"). Todo coletor deste pipeline importa este módulo em vez de duplicar lógica de
normalização/dedupe/escrita.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, quote_plus, urlencode, urlsplit, urlunsplit

try:
    import yaml  # type: ignore
except ImportError as exc:  # pragma: no cover - dependência declarada em requirements.txt
    raise SystemExit(
        "PyYAML não está instalado no venv ativo. Rode "
        "'pipeline/.venv/Scripts/python -m pip install -r pipeline/requirements.txt' "
        "(ver README.md deste setor)."
    ) from exc

PIPELINE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = PIPELINE_DIR.parent
CONFIG_DIR = PIPELINE_DIR / "config"
DATA_DIR = PIPELINE_DIR / "data"
STATE_DIR = DATA_DIR / "state"
RUNS_DIR = DATA_DIR / "runs"
LOGS_DIR = PIPELINE_DIR / "logs"

USER_AGENT = "AlchemiaNewsBot/1.0 (+https://alchemia.solutions; contato: company@alchemia.solutions)"

for _d in (DATA_DIR, STATE_DIR, RUNS_DIR, LOGS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] {msg}"
    print(line, flush=True)


def sanitize_local_path(text: str) -> str:
    """Troca o caminho absoluto local (inclui o usuário do SO) por um marcador portável.

    Achado real em 2026-08-20: `traceback.format_exc()` sempre inclui o caminho absoluto de
    onde o processo roda -- e esse texto acaba gravado em `meta.json`/`pipeline/data/runs/*.json`,
    que são versionados de propósito (auditoria). Como o repositório é público desde hoje, isso
    vazava o usuário do Windows do fundador em texto puro. Sanitiza sem perder o resto do
    traceback (linha, função, mensagem), que continua útil para investigar `error` não-nulo.
    """
    if not text:
        return text
    return text.replace(str(REPO_ROOT), "<alchemia-news>")


def load_yaml(name: str) -> Any:
    path = CONFIG_DIR / name
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_keywords() -> dict:
    return load_yaml("keywords.yaml")


def load_sources() -> dict:
    return load_yaml("sources.yaml")


def load_companies() -> list[dict]:
    return load_yaml("companies.yaml")["companies"]


def load_resources() -> list[dict]:
    return load_yaml("resources.yaml")["resources"]


def http_get(url: str, timeout: int = 20, headers: dict | None = None, retries: int = 3) -> bytes:
    """GET simples com User-Agent identificável, retry exponencial e sem dependências externas.

    Usado por coletores que não precisam de nada além de um corpo de resposta bruto (XML/JSON).
    """
    req_headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        req_headers.update(headers)
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=req_headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:  # noqa: PERF203
            last_exc = exc
            if attempt < retries:
                time.sleep(1.5 * attempt)
            continue
    raise RuntimeError(f"GET falhou após {retries} tentativas: {url} ({last_exc})")


def http_get_json(url: str, timeout: int = 20, headers: dict | None = None) -> Any:
    raw = http_get(url, timeout=timeout, headers=headers)
    return json.loads(raw.decode("utf-8", errors="replace"))


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(text: str | None) -> str:
    """Remove tags E decodifica entidades HTML.

    A decodificação foi adicionada em 2026-08-18: sem ela, o resumo de todo item do Google News
    aparecia no dashboard com `&nbsp;&nbsp;` literal antes do nome da fonte (visível na home, não
    um detalhe interno). Só remover tags não basta — o feed entrega entidades, não caracteres.

    `unescape` roda ANTES do `_TAG_RE`, senão um `&lt;script&gt;` viraria uma tag de verdade
    depois de decodificado e passaria intacto pelo filtro. Depois disso o colapso de espaço em
    branco também absorve os NBSP recém-decodificados.
    """
    if not text:
        return ""
    no_tags = _TAG_RE.sub(" ", html.unescape(text))
    # \xa0 (NBSP) não é \s em modo unicode do `re` até Python 3.x tratá-lo como espaço — trocamos
    # explicitamente para o colapso de espaço abaixo funcionar.
    return _WS_RE.sub(" ", no_tags.replace("\xa0", " ")).strip()


# Parâmetros de rastreamento que nunca fazem parte da identidade de uma matéria: `fbclid`/`gclid`
# vêm de compartilhamento em rede social/anúncio, `mc_*` de newsletter. O `oc=5` do Google News
# NÃO entra aqui de propósito — ele é constante em todo link daquela fonte, então não distingue
# nada, e removê-lo só quebraria a URL sem ganho de deduplicação.
_TRACKING_PARAMS = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid", "igshid", "ref_src", "spm")


def normalize_url(url: str) -> str:
    """Normaliza uma URL para fins de deduplicação (remove tracking params comuns).

    Reescrito em 2026-08-18. A implementação anterior fatiava a string à mão e tinha um bug real,
    confirmado por teste antes da correção: quando havia **qualquer parâmetro antes** do `utm_`
    (`?id=7&utm_source=rss`), ela remontava a URL como `?id=7?utm_source=rss` — dois `?`, e o
    `utm_source` **sobrevivia**. Consequência concreta: a mesma matéria chegando por dois caminhos
    com `utm_source` diferente produzia duas `dedupe_key` distintas e entrava **duas vezes** na
    base. Só o caso `?utm_...` no início da query funcionava.

    Agora a query é decomposta de verdade (`urllib.parse`), os parâmetros de rastreamento saem, e
    os demais são reordenados — assim `?a=1&b=2` e `?b=2&a=1` também deduplicam, o que a versão
    antiga não fazia.
    """
    if not url:
        return ""
    try:
        partes = urlsplit(url.strip())
    except ValueError:
        return url.strip().rstrip("/")

    mantidos = [
        (k, v)
        for k, v in parse_qsl(partes.query, keep_blank_values=True)
        if not any(k.lower().startswith(t) for t in _TRACKING_PARAMS)
    ]
    query = urlencode(sorted(mantidos))
    # Fragmento (#âncora) nunca identifica uma matéria diferente — sempre descartado.
    limpa = urlunsplit((partes.scheme, partes.netloc, partes.path, query, ""))
    return limpa.rstrip("/")


def dedupe_key(item: dict) -> str:
    """Chave de deduplicação: DOI normalizado se existir, senão URL normalizada, senão hash de título+fonte."""
    doi = (item.get("doi") or "").strip().lower()
    if doi:
        return f"doi:{doi}"
    url = normalize_url(item.get("url") or "")
    if url:
        return f"url:{url.lower()}"
    basis = f"{item.get('source','')}|{item.get('title','')}".lower()
    return "hash:" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]


def _fold(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def match_keywords(text: str, topics: Iterable[str]) -> list[str]:
    """Retorna a lista de tópicos do nicho encontrados em `text` (case/acento-insensível)."""
    folded = _fold(text)
    hits = []
    for topic in topics:
        if _fold(topic) in folded:
            hits.append(topic)
    return hits


def parse_date_safe(value: str | None) -> str | None:
    """Tenta normalizar uma data para ISO-8601 (YYYY-MM-DD). Retorna None se não conseguir."""
    if not value:
        return None
    value = value.strip()
    fmts = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%d %b %Y",
        "%Y/%m/%d",
        "%Y%m%d",
        # Fierce Biotech: "Aug 18, 2026 8:14am" (adicionado 2026-08-18, medido no feed real).
        "%b %d, %Y %I:%M%p",
        "%b %d, %Y",
        "%d %B %Y",
    ]
    for fmt in fmts:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    # RFC-822 sem timezone padrão (comum em RSS) -- tenta cortar até os primeiros 25 chars úteis
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", value)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None


def within_window(iso_date: str | None, days: int) -> bool:
    if not iso_date:
        return True  # sem data conhecida -> não descarta por janela, deixa outro filtro decidir
    try:
        dt = datetime.strptime(iso_date, "%Y-%m-%d")
    except ValueError:
        return True
    cutoff = datetime.now() - timedelta(days=days)
    return dt >= cutoff


@dataclass
class Item:
    """Item normalizado, comum a artigo/preprint e notícia."""

    kind: str  # "article" | "news"
    title: str
    url: str
    source: str  # nome legível da fonte (ex.: "PubMed", "bioRxiv", "Instituto Butantan")
    source_type: str  # "journal" | "preprint" | "news" | "company_blog" | "press"
    published_date: str | None = None
    collected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    authors: list[str] = field(default_factory=list)
    summary: str = ""
    doi: str | None = None
    company_slug: str | None = None
    keywords_matched: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["dedupe_key"] = dedupe_key(d)
        return d


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=False)
    tmp.replace(path)


def merge_items(existing: list[dict], new_items: list[dict]) -> tuple[list[dict], int, int]:
    """Funde itens novos a uma lista existente por dedupe_key. Retorna (lista_final, n_novos, n_atualizados)."""
    by_key = {it.get("dedupe_key") or dedupe_key(it): it for it in existing}
    n_new = 0
    n_updated = 0
    for raw in new_items:
        key = raw.get("dedupe_key") or dedupe_key(raw)
        raw["dedupe_key"] = key
        if key in by_key:
            # Mantém o registro existente, mas preenche campos vazios com o dado novo (ex.: summary).
            prev = by_key[key]
            changed = False
            for field_name in ("summary", "authors", "published_date", "doi"):
                if not prev.get(field_name) and raw.get(field_name):
                    prev[field_name] = raw[field_name]
                    changed = True
            if changed:
                n_updated += 1
        else:
            by_key[key] = raw
            n_new += 1
    merged = list(by_key.values())
    merged.sort(key=lambda x: x.get("published_date") or "", reverse=True)
    return merged, n_new, n_updated


def crossref_works_by_prefix(
    base_url: str,
    doi_prefix: str,
    rows: int,
    query: str | None = None,
    days_back: int | None = None,
) -> list[dict]:
    """Busca obras no Crossref por prefixo de DOI (editora), opcionalmente com query e janela de
    data de criação. Usado como proxy para ChemRxiv (10.26434) e SciELO Brasil (10.1590), que
    bloqueiam acesso direto (403) mas têm seus DOIs indexados normalmente no Crossref.
    """
    parts = [f"filter=prefix:{doi_prefix}"]
    if days_back:
        since = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        parts[0] += f",from-created-date:{since}"
    query_part = f"&query={quote_plus(query)}" if query else ""
    url = (
        f"{base_url}?{parts[0]}{query_part}&rows={rows}&sort=created&order=desc"
        f"&select=DOI,title,created,author,abstract,container-title,URL"
    )
    data = http_get_json(url)
    return data.get("message", {}).get("items", [])


def crossref_item_to_dict(entry: dict, source: str, source_type: str, topics: list[str]) -> dict | None:
    titles = entry.get("title") or []
    title = titles[0] if titles else ""
    if not title:
        return None
    doi = entry.get("DOI")
    url = entry.get("URL") or (f"https://doi.org/{doi}" if doi else "")
    if not url:
        return None
    created = entry.get("created", {}).get("date-time", "")
    published = parse_date_safe(created)
    authors = []
    for a in entry.get("author", []) or []:
        given = a.get("given", "")
        family = a.get("family", "")
        name = f"{given} {family}".strip()
        if name:
            authors.append(name)
    abstract = strip_html(entry.get("abstract", ""))
    container = entry.get("container-title") or []
    journal = container[0] if container else ""
    hits = match_keywords(f"{title} {abstract}", topics)
    return Item(
        kind="article",
        title=strip_html(title),
        url=url,
        source=source,
        source_type=source_type,
        published_date=published,
        authors=authors,
        summary=abstract[:1200],
        doi=doi,
        keywords_matched=hits,
        extra={"journal": journal} if journal else {},
    ).to_dict()


def write_run_snapshot(name: str, payload: dict) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    save_json(RUNS_DIR / f"{ts}-{name}.json", payload)
