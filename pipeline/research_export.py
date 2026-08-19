#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Exporta o dia do Alchemia News para `alchemia-science` — radar em markdown + PDFs open access.

Criado em 2026-08-18 a pedido do fundador: "integrando os artigos com alchemia-science e
alchemia-library quando possível resgatar o pdf completo, se não, somente como markdown que deve
ser colocado em research com a data do dia e com todos os artigos e tudo que foi atualizado no
alchemia-news".

Duas saídas, uma execução:

1. **`alchemia-science/research/AAAA-MM-DD-alchemia-news-radar.md`** — o radar do dia. Contém
   TUDO que entrou no `alchemia-news` naquela data: artigos/preprints, notícias, atividade de
   empresas, mais os números reais da coleta e a saúde dos 8 coletores. É o registro de pesquisa
   que sobrevive independente do dashboard e do Discord.

2. **`alchemia-science/alchemia-library/*.pdf`** — o texto completo, quando (e só quando) ele é
   comprovadamente open access. Cada PDF baixado entra no `manifest.csv` e no
   `alchemia-library.json` (CSL-JSON) com metadado real, do mesmo jeito que a biblioteca já era
   mantida à mão — e passa a ser auditável por `scripts/check_sync.py`.

## Regra de licenciamento (a parte que não é negociável)

Só baixa PDF cuja abertura foi **confirmada por uma fonte real nesta execução** — nunca por
palpite, nunca por "provavelmente é aberto". As quatro rotas, nesta ordem:

| Rota | Confirmação de abertura | Verificada ao vivo em |
|---|---|---|
| arXiv (`extra.arxiv_id`) | o próprio arXiv é repositório aberto | 2026-08-18 |
| bioRxiv / medRxiv (`source`) | preprint server aberto, PDF público em `/content/<doi>v1.full.pdf` | 2026-08-18 |
| Unpaywall (`is_oa == true`) | campo `is_oa` + `best_oa_location.license` da própria API | 2026-08-18 |
| Europe PMC (`isOpenAccess == "Y"`) | flag da própria API + `pmcid` | 2026-08-18 |

Artigo sem rota aberta **não é baixado** — entra no radar só como markdown, com o motivo
registrado. Isso é deliberado: baixar paywall seria a classe de decisão que a "Cultura
não-negociável" da empresa manda escalar ao fundador, não automatizar 3x/dia.

A licença encontrada é gravada no `manifest.csv` de cada PDF, para nunca se perder a proveniência.

## Limites operacionais (memória da crise de disco de 2026-08-09)

- teto de PDFs por execução (`--max-pdf`, default 6) — o que passar do teto é **reportado** no
  radar, nunca truncado em silêncio;
- teto de tamanho por arquivo (`--max-mb`, default 60);
- teto de volume total por execução (`--max-total-mb`, default 150) — um único preprint de
  RFdiffusion tem 40 MB; sem esse teto, 3 execuções/dia podem virar centenas de MB/dia;
- **piso de espaço livre em disco** (`--min-free-gb`, default 20): abaixo disso a colheita é
  pulada por inteiro e o radar registra o porquê. O `C:` desta máquina já chegou a 10 MB livres.

## Uso

    python -m pipeline.research_export                    # o dia de hoje, com colheita de PDF
    python -m pipeline.research_export --date 2026-08-17  # refaz um dia anterior
    python -m pipeline.research_export --no-pdf           # só o markdown
    python -m pipeline.research_export --dry-run          # não escreve nada, só relata

Idempotente: reexecutar o mesmo dia regenera o markdown e **não** rebaixa PDF já registrado
(dedupe por DOI e por SHA-256 do conteúdo).

Ver `alchemia-ai/alchemia-news/docs/specs/2026-08-18-research-library-integration.md`.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import time
import unicodedata
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent
NEWS_ROOT = PIPELINE_DIR.parent
COMPANY_ROOT = NEWS_ROOT.parent.parent  # alchemia-news -> alchemia-ai -> Alchemia LTDA
SCIENCE_ROOT = COMPANY_ROOT / "alchemia-science"
RESEARCH_DIR = SCIENCE_ROOT / "research"
LIBRARY_DIR = SCIENCE_ROOT / "alchemia-library"
MANIFEST = LIBRARY_DIR / "manifest.csv"
CSL_JSON = LIBRARY_DIR / "alchemia-library.json"
DATA_DIR = PIPELINE_DIR / "data"
# Onde o Axel deposita, verbatim, a mensagem que publicou no Discord. Existe para o radar do dia
# poder incluir "o que foi anunciado" sem que isso se perca quando o markdown é regenerado — o
# radar é derivado, então nada pode ser escrito direto nele por outro processo.
DISCORD_DIR = DATA_DIR / "discord"

USER_AGENT = (
    "AlchemiaNewsBot/1.0 (+https://alchemia.solutions; contato: company@alchemia.solutions)"
)
UNPAYWALL_EMAIL = "company@alchemia.solutions"

SECOES = (
    ("articles.json", "Artigos e preprints", "article"),
    ("news.json", "Notícias", "news"),
    ("companies_activity.json", "Atividade de empresas", "company"),
)


# --------------------------------------------------------------------------------------------
# utilitários
# --------------------------------------------------------------------------------------------
def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def http_get(url: str, timeout: int = 30, accept: str = "*/*", retries: int = 3) -> tuple[int, str, bytes]:
    """GET com retry exponencial — mesma política do `collectors/common.py` deste pipeline.

    O retry não é cosmético: na primeira execução desta integração (2026-08-18) o PDF do bioRxiv
    falhou com HTTPError e voltou 200 na tentativa seguinte, sem nada ter mudado. Sem retry, um
    soluço de rede vira "artigo sem texto completo" no registro de pesquisa — um dado errado, não
    só um download perdido. 404/403 não são retentados: são resposta definitiva, não soluço.
    """
    ultimo: Exception | None = None
    for tentativa in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, (resp.headers.get("Content-Type") or ""), resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 404, 410):
                raise
            ultimo = exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            ultimo = exc
        if tentativa < retries:
            time.sleep(1.5 * tentativa)
    raise ultimo if ultimo else RuntimeError(f"GET falhou: {url}")


def http_get_json(url: str, timeout: int = 30):
    _, _, body = http_get(url, timeout=timeout, accept="application/json")
    return json.loads(body.decode("utf-8", errors="replace"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dia_do_item(item: dict) -> str | None:
    """Dia a que o item pertence.

    Mesma semântica do `--today-only` do Axel (`alchemia_news_axel_feed.py`), de propósito: usa
    `published_date` quando a fonte traz e cai para `collected_at` quando não. 41% dos artigos
    (PubMed sobretudo) chegam sem `published_date`; um filtro estrito os deixaria de fora do
    registro de pesquisa exatamente como deixaria de fora do anúncio. Por isso o radar diz
    "entrou no radar em", não "publicado em".
    """
    for campo in ("published_date", "collected_at"):
        v = item.get(campo)
        if v:
            return str(v)[:10]
    return None


def slugify(texto: str, limite: int = 60) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", texto or "").strip("-.")
    return (s[:limite] or "sem-nome").lower()


def md_escape(texto: str) -> str:
    """Neutraliza markdown vindo de título de terceiro — é dado, nunca formatação nossa."""
    return re.sub(r"([\\`*_\[\]{}<>|])", r"\\\1", (texto or "").replace("\n", " ")).strip()


# --------------------------------------------------------------------------------------------
# resolução de open access
# --------------------------------------------------------------------------------------------
class RotaOA:
    """Resultado da tentativa de achar um PDF aberto. `url` None = não há rota aberta."""

    def __init__(self, url: str | None, rota: str, licenca: str | None, motivo: str = ""):
        self.url = url
        self.rota = rota
        self.licenca = licenca
        self.motivo = motivo


def _unpaywall(doi: str) -> RotaOA:
    url = f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi)}?email={UNPAYWALL_EMAIL}"
    try:
        d = http_get_json(url, timeout=25)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return RotaOA(None, "unpaywall", None, "DOI não indexado no Unpaywall")
        return RotaOA(None, "unpaywall", None, f"Unpaywall HTTP {exc.code}")
    except Exception as exc:  # noqa: BLE001
        return RotaOA(None, "unpaywall", None, f"Unpaywall indisponível ({type(exc).__name__})")

    if not d.get("is_oa"):
        return RotaOA(None, "unpaywall", None, "Unpaywall: is_oa=false (sem versão aberta)")
    loc = d.get("best_oa_location") or {}
    lic = loc.get("license")
    pdf = loc.get("url_for_pdf")
    if not pdf:
        cand = loc.get("url") or ""
        if cand.lower().endswith(".pdf"):
            pdf = cand
    if not pdf:
        return RotaOA(None, "unpaywall", lic, "Unpaywall: é OA mas não expõe URL direta de PDF")
    return RotaOA(pdf, "unpaywall", lic)


def _europepmc(doi: str) -> RotaOA:
    q = urllib.parse.quote(f'DOI:"{doi}"')
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={q}&format=json&resultType=core"
    try:
        d = http_get_json(url, timeout=25)
        rs = (d.get("resultList") or {}).get("result") or []
    except Exception as exc:  # noqa: BLE001
        return RotaOA(None, "europepmc", None, f"Europe PMC indisponível ({type(exc).__name__})")
    if not rs:
        return RotaOA(None, "europepmc", None, "não encontrado no Europe PMC")
    r = rs[0]
    if r.get("isOpenAccess") != "Y":
        return RotaOA(None, "europepmc", None, "Europe PMC: isOpenAccess=N")
    pmcid = r.get("pmcid")
    if not pmcid:
        return RotaOA(None, "europepmc", r.get("license"), "Europe PMC: OA sem PMCID")
    return RotaOA(
        f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextPDF",
        "europepmc",
        r.get("license"),
    )


def resolver_oa(item: dict) -> RotaOA:
    """Acha uma rota aberta para o texto completo, ou explica por que não há."""
    source = (item.get("source") or "").lower()
    doi = (item.get("doi") or "").strip()
    arxiv_id = ((item.get("extra") or {}).get("arxiv_id") or "").strip()

    # 1) arXiv — repositório aberto por construção.
    if arxiv_id:
        return RotaOA(f"https://arxiv.org/pdf/{arxiv_id}", "arxiv", "arXiv (licença por preprint)")

    # 2) bioRxiv / medRxiv — PDF público no próprio servidor de preprint.
    #
    # A versão importa: `v1` cobre a maioria, mas preprint revisado pode não ter mais v1 servido,
    # e aí `/content/<doi>v1.full.pdf` responde 404 (aconteceu de verdade com 2 de 6 preprints no
    # backfill de 2026-08-17). Antes de desistir, perguntamos a versão real à própria API de
    # detalhes do bioRxiv — que é a mesma que o `biorxiv_collector` já usa neste pipeline.
    if doi and ("biorxiv" in source or "medrxiv" in source):
        host = "medrxiv" if "medrxiv" in source else "biorxiv"
        versao = "1"
        try:
            det = http_get_json(f"https://api.{host}.org/details/{host}/{doi}", timeout=20)
            col = det.get("collection") or []
            if col and col[-1].get("version"):
                versao = str(col[-1]["version"])
        except Exception:  # noqa: BLE001
            pass  # sem a API, v1 continua sendo o palpite certo na grande maioria
        return RotaOA(
            f"https://www.{host}.org/content/{doi}v{versao}.full.pdf",
            host,
            f"{host} (licença por preprint)",
        )

    if not doi:
        return RotaOA(None, "-", None, "item sem DOI e sem ID de arXiv")

    # 2b) ChemRxiv — aberto para ler no site, mas fechado para máquina. Tanto o acesso direto
    # quanto a public-api respondem **403** (reverificado em 2026-08-18; é a mesma barreira que
    # levou este setor a coletar ChemRxiv por proxy via Crossref, e o Crossref indexa o metadado
    # mas não o PDF). O Unpaywall também não indexa o prefixo 10.26434. Reportar o motivo real
    # em vez de deixar cair no texto genérico do Unpaywall.
    if doi.startswith("10.26434") or "chemrxiv" in source:
        return RotaOA(None, "-", None,
                      "ChemRxiv responde 403 a acesso automatizado (site e public-api) e não é "
                      "indexado pelo Unpaywall — texto completo só manualmente pelo navegador")

    # 3) Unpaywall — a rota mais ampla; is_oa é a confirmação.
    r = _unpaywall(doi)
    if r.url:
        return r

    # 4) Europe PMC — pega OA que o Unpaywall não indexa (comum em PubMed recente).
    r2 = _europepmc(doi)
    if r2.url:
        return r2

    return RotaOA(None, "-", r.licenca, f"{r.motivo}; {r2.motivo}")


# --------------------------------------------------------------------------------------------
# metadado bibliográfico
# --------------------------------------------------------------------------------------------
def crossref(doi: str) -> dict | None:
    try:
        return http_get_json(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}", timeout=25)["message"]
    except Exception:  # noqa: BLE001
        return None


def _autores_csl(item: dict, cr: dict | None) -> tuple[list[dict], bool]:
    """Autores em CSL-JSON. Retorna (lista, heuristico) — `heuristico=True` quando a divisão
    given/family veio de partir uma string, não de um campo estruturado da fonte."""
    if cr and cr.get("author"):
        return ([{"given": a.get("given", ""), "family": a.get("family", "")}
                 for a in cr["author"]], False)
    out = []
    for nome in item.get("authors") or []:
        nome = str(nome).strip()
        if not nome:
            continue
        if "," in nome:  # "Lin, J." (bioRxiv)
            fam, _, giv = nome.partition(",")
            out.append({"given": giv.strip(), "family": fam.strip()})
        else:  # "Le Song" (arXiv)
            partes = nome.split()
            out.append({"given": " ".join(partes[:-1]), "family": partes[-1]} if len(partes) > 1
                       else {"given": "", "family": nome})
    return out, bool(out)


def montar_csl(item: dict, cr: dict | None, cid: str, nome_pdf: str, obs: str) -> dict:
    autores, heuristico = _autores_csl(item, cr)
    titulo = (cr.get("title") or [""])[0] if cr else ""
    titulo = titulo or item.get("title") or ""
    revista = ""
    if cr:
        revista = (cr.get("container-title") or [""])[0]
    revista = revista or (item.get("extra") or {}).get("journal") or item.get("source") or ""
    ano = None
    if cr and cr.get("issued", {}).get("date-parts"):
        ano = cr["issued"]["date-parts"][0][0]
    if not ano:
        pd = item.get("published_date") or ""
        ano = int(pd[:4]) if pd[:4].isdigit() else date.today().year

    nota = f"alchemia-science/alchemia-library/{nome_pdf}; {obs}"
    if heuristico:
        nota += (" Divisao given/family dos autores derivada da string da fonte (o item nao tem "
                 "campo estruturado e o DOI nao esta no Crossref) - conferir antes de citar.")

    csl = {
        "id": cid,
        "type": "article-journal" if (item.get("source_type") == "journal") else "article",
        "title": titulo,
        "author": autores,
        "issued": {"date-parts": [[ano]]},
        "container-title": revista,
        "note": nota,
    }
    if item.get("doi"):
        csl["DOI"] = item["doi"]
    elif item.get("url"):
        csl["URL"] = item["url"]
    if cr:
        if cr.get("volume"):
            csl["volume"] = str(cr["volume"])
        if cr.get("article-number"):
            csl["page"] = str(cr["article-number"])
        elif cr.get("page"):
            csl["page"] = str(cr["page"])
    return csl


def gerar_id_csl(item: dict, cr: dict | None, usados: set[str]) -> str:
    autores, _ = _autores_csl(item, cr)
    sobrenome = slugify(autores[0]["family"], 20).replace("-", "") if autores else "anon"
    pd = item.get("published_date") or ""
    ano = pd[:4] if pd[:4].isdigit() else str(date.today().year)
    palavras = [w for w in re.findall(r"[A-Za-z]{4,}", item.get("title") or "")][:2]
    cauda = "".join(w.lower() for w in palavras) or "artigo"
    base = f"{sobrenome or 'anon'}{ano}{cauda}"[:48]
    cid, n = base, 2
    while cid in usados:
        cid, n = f"{base}{n}", n + 1
    return cid


def nome_arquivo_pdf(item: dict, existentes: set[str]) -> str:
    arxiv_id = ((item.get("extra") or {}).get("arxiv_id") or "").strip()
    doi = (item.get("doi") or "").strip()
    if arxiv_id:
        base = f"arxiv-{slugify(arxiv_id, 30)}"
    elif doi:
        base = slugify(doi.split("/", 1)[-1], 50)
    else:
        base = slugify(item.get("title") or "artigo", 50)
    nome, n = f"{base}.pdf", 2
    while nome in existentes:
        nome, n = f"{base}-{n}.pdf", n + 1
    return nome


# --------------------------------------------------------------------------------------------
# biblioteca
# --------------------------------------------------------------------------------------------
def ler_biblioteca() -> tuple[list[dict], list[dict], list[str]]:
    """Retorna (itens CSL-JSON, linhas do manifest como dicts, cabecalho do manifest)."""
    csl = load_json(CSL_JSON, [])
    linhas: list[dict] = []
    campos = ["arquivo_pdf", "sha256", "tamanho_bytes", "doi", "csl_json_id", "observacao"]
    if MANIFEST.exists():
        with MANIFEST.open("r", encoding="utf-8", newline="") as fh:
            leitor = csv.DictReader(fh)
            campos = leitor.fieldnames or campos
            linhas = list(leitor)
    return (csl if isinstance(csl, list) else []), linhas, campos


def gravar_biblioteca(csl: list[dict], linhas: list[dict], campos: list[str]) -> None:
    CSL_JSON.write_text(json.dumps(csl, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with MANIFEST.open("w", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=campos, lineterminator="\n")
        escritor.writeheader()
        for row in linhas:
            escritor.writerow({c: (row.get(c) or "") for c in campos})


# --- exclusão mútua da colheita ---------------------------------------------------------------
# Por que existe (achado real de 2026-08-18, primeira execução agendada do Baker): a colheita faz
# read-modify-write de `manifest.csv` e `alchemia-library.json`. Duas execuções sobrepostas — o
# cenário normal, não exótico: Task Scheduler às 12:40 fazendo backfill lento + Baker às 12:50 —
# leriam a mesma versão do manifest e a segunda a reescreveria **sem** as entradas da primeira,
# deixando o PDF órfão em disco para sempre.
#
# O lock cobre a colheita inteira. Quem não consegue pegá-lo **não falha e não espera**: pula só a
# colheita, registra o motivo no radar, e o markdown do dia sai normalmente. Os PDFs não colhidos
# reaparecem na execução seguinte — a mesma disciplina do teto de `--max-pdf`.
LOCK = LIBRARY_DIR / ".harvest.lock"
LOCK_STALE_SEGUNDOS = 45 * 60  # colheita real leva < 5 min; 45 min só cobre processo morto


class ColheitaOcupada(Exception):
    pass


def _lock_vivo() -> bool:
    try:
        idade = time.time() - LOCK.stat().st_mtime
    except OSError:
        return False
    if idade > LOCK_STALE_SEGUNDOS:
        # Lock velho = processo morreu sem liberar. Assume-se abandonado, senão uma queda única
        # bloquearia a colheita para sempre.
        try:
            LOCK.unlink()
        except OSError:
            pass
        return False
    return True


class trava_colheita:
    """Lock de arquivo por criação exclusiva (`O_EXCL`) — atômico no Windows e no POSIX."""

    def __enter__(self):
        if _lock_vivo():
            raise ColheitaOcupada(LOCK.read_text(encoding="utf-8", errors="replace").strip())
        try:
            with open(LOCK, "x", encoding="utf-8") as fh:
                fh.write(f"pid={os.getpid()} iniciado={datetime.now(timezone.utc).isoformat()}\n")
        except FileExistsError as exc:  # corrida entre o teste acima e a criação
            raise ColheitaOcupada("outro processo pegou o lock no mesmo instante") from exc
        return self

    def __exit__(self, *_exc):
        try:
            LOCK.unlink()
        except OSError:
            pass
        return False


# --------------------------------------------------------------------------------------------
# colheita
# --------------------------------------------------------------------------------------------
def colher_pdfs(artigos: list[dict], args, relato: list[str]) -> tuple[dict[str, dict], list[str]]:
    """Baixa e registra o que for comprovadamente aberto. Retorna (por_chave_do_item, avisos)."""
    resultado: dict[str, dict] = {}
    avisos: list[str] = []

    if args.no_pdf or args.max_pdf <= 0:
        avisos.append("Colheita de PDF desligada nesta execução (`--no-pdf`/`--max-pdf 0`).")
        return resultado, avisos

    livre_gb = shutil.disk_usage(str(LIBRARY_DIR)).free / (1024 ** 3)
    if livre_gb < args.min_free_gb:
        avisos.append(
            f"⚠️ Colheita de PDF **pulada por inteiro**: só {livre_gb:.1f} GB livres em disco "
            f"(piso configurado: {args.min_free_gb} GB). Os artigos abaixo seguem registrados "
            f"como markdown; nenhum texto completo foi perdido, só adiado."
        )
        return resultado, avisos

    try:
        trava = trava_colheita().__enter__()
    except ColheitaOcupada as exc:
        avisos.append(
            f"⏭️ Colheita de PDF **pulada**: outra execução do `research_export` está colhendo "
            f"agora ({exc}). O radar deste dia foi gerado normalmente; os PDFs pendentes entram na "
            f"próxima execução. Isso é exclusão mútua deliberada — duas colheitas simultâneas "
            f"sobrescreveriam o manifest uma da outra."
        )
        return resultado, avisos

    try:
        return _colher_com_lock(artigos, args, relato, resultado, avisos)
    finally:
        trava.__exit__(None, None, None)


def _colher_com_lock(artigos, args, relato, resultado, avisos):
    """Corpo da colheita, já sob o lock exclusivo — ver `trava_colheita`."""
    csl, linhas, campos = ler_biblioteca()
    ids_usados = {str(i.get("id", "")) for i in csl}
    nomes_usados = {str(r.get("arquivo_pdf", "")) for r in linhas}
    dois_registrados = {(r.get("doi") or "").strip().lower() for r in linhas if r.get("doi")}
    hashes_registrados = {(r.get("sha256") or "").strip().lower() for r in linhas if r.get("sha256")}

    baixados = 0
    bytes_baixados = 0
    teto_bytes = args.max_total_mb * (1024 ** 2)
    fila = list(artigos)
    for item in fila:
        chave = item.get("dedupe_key") or item.get("url") or item.get("title") or ""
        doi = (item.get("doi") or "").strip().lower()

        if doi and doi in dois_registrados:
            resultado[chave] = {"estado": "ja_na_biblioteca", "motivo": "DOI já registrado na alchemia-library"}
            continue

        if baixados >= args.max_pdf:
            resultado[chave] = {"estado": "adiado", "motivo": f"teto de {args.max_pdf} PDFs/execução atingido"}
            continue

        if bytes_baixados >= teto_bytes:
            resultado[chave] = {
                "estado": "adiado",
                "motivo": f"teto de volume de {args.max_total_mb:.0f} MB/execução atingido",
            }
            continue

        rota = resolver_oa(item)
        if not rota.url:
            resultado[chave] = {"estado": "sem_oa", "motivo": rota.motivo or "sem rota aberta"}
            continue

        try:
            status, ctype, corpo = http_get(rota.url, timeout=90, accept="application/pdf,*/*")
        except Exception as exc:  # noqa: BLE001
            resultado[chave] = {"estado": "falhou", "motivo": f"download falhou via {rota.rota} ({type(exc).__name__})"}
            continue

        if status != 200 or not corpo.startswith(b"%PDF"):
            resultado[chave] = {
                "estado": "falhou",
                "motivo": f"resposta de {rota.rota} não é um PDF (HTTP {status}, {ctype or 'sem content-type'})",
            }
            continue

        mb = len(corpo) / (1024 ** 2)
        if mb > args.max_mb:
            resultado[chave] = {"estado": "grande_demais", "motivo": f"{mb:.1f} MB acima do teto de {args.max_mb} MB"}
            continue

        h = sha256_bytes(corpo)
        if h in hashes_registrados:
            resultado[chave] = {"estado": "ja_na_biblioteca", "motivo": "conteúdo idêntico (SHA-256) já na biblioteca"}
            continue

        cr = crossref(item["doi"]) if item.get("doi") else None
        nome = nome_arquivo_pdf(item, nomes_usados)
        cid = gerar_id_csl(item, cr, ids_usados)
        obs = (
            f"Colhido automaticamente em {date.today().isoformat()} pelo research_export do "
            f"alchemia-news; rota open access: {rota.rota}; licenca: {rota.licenca or 'nao declarada pela fonte'}; "
            f"origem: {item.get('source', '?')}."
        )

        if args.dry_run:
            resultado[chave] = {"estado": "baixaria", "motivo": f"via {rota.rota} ({mb:.1f} MB) — dry-run, nada gravado"}
            baixados += 1
            continue

        (LIBRARY_DIR / nome).write_bytes(corpo)
        nomes_usados.add(nome)
        ids_usados.add(cid)
        hashes_registrados.add(h)
        if doi:
            dois_registrados.add(doi)

        csl.append(montar_csl(item, cr, cid, nome, obs))
        linhas.append({
            "arquivo_pdf": nome,
            "sha256": h,
            "tamanho_bytes": str(len(corpo)),
            "doi": item.get("doi") or "",
            "csl_json_id": cid,
            "observacao": obs,
        })
        # Commit IMEDIATO, não em lote no fim do laço. Antes (2026-08-18, primeira versão), o
        # manifest só era escrito depois de todos os downloads — uma janela de minutos em que o
        # PDF já estava em disco e o metadado não. Um `check_sync` rodando nessa janela acusava
        # divergência de uma biblioteca perfeitamente saudável (aconteceu de verdade: PDF às
        # 11:07:39, manifest às 11:08:11), e um processo morto no meio deixaria órfão permanente.
        # Agora a janela é de milissegundos, e uma queda perde no máximo o item em voo.
        gravar_biblioteca(csl, linhas, campos)
        resultado[chave] = {
            "estado": "baixado",
            "arquivo": nome,
            "csl_json_id": cid,
            "rota": rota.rota,
            "licenca": rota.licenca,
            "motivo": f"{mb:.1f} MB via {rota.rota}",
        }
        baixados += 1
        bytes_baixados += len(corpo)
        relato.append(f"  + {nome} ({mb:.1f} MB, {rota.rota}, {rota.licenca or 'licenca nao declarada'})")

    # Nada a gravar aqui: cada download já fez seu próprio `gravar_biblioteca` acima. A escrita em
    # lote que existia neste ponto foi removida em 2026-08-18 — era ela que criava a janela de
    # inconsistência entre o PDF em disco e o manifest.

    adiados = sum(1 for v in resultado.values() if v["estado"] == "adiado")
    if adiados:
        avisos.append(
            f"{adiados} artigo(s) com rota aberta ficaram para a próxima execução (teto de "
            f"`--max-pdf {args.max_pdf}`). Nada foi descartado — eles reaparecem enquanto não "
            f"estiverem na biblioteca."
        )
    return resultado, avisos


# --------------------------------------------------------------------------------------------
# markdown
# --------------------------------------------------------------------------------------------
def bloco_artigo(item: dict, pdf: dict | None) -> list[str]:
    ls = [f"#### {md_escape(item.get('title') or 'sem título')}"]
    meta = [f"**Fonte:** {md_escape(item.get('source') or '?')}"]
    if item.get("published_date"):
        meta.append(f"**Publicado:** {item['published_date']}")
    if (item.get("extra") or {}).get("journal"):
        meta.append(f"**Periódico:** {md_escape(item['extra']['journal'])}")
    ls.append(" · ".join(meta))

    autores = item.get("authors") or []
    if autores:
        txt = ", ".join(md_escape(str(a)) for a in autores[:8])
        if len(autores) > 8:
            txt += f" … (+{len(autores) - 8})"
        ls.append(f"**Autores:** {txt}")

    if item.get("doi"):
        ls.append(f"**DOI:** [{item['doi']}](https://doi.org/{item['doi']})")
    if item.get("url"):
        ls.append(f"**Link:** <{item['url']}>")

    kw = item.get("keywords_matched") or []
    ls.append(f"**Termos que trouxeram o item:** {', '.join(md_escape(k) for k in kw) if kw else '_(query da própria fonte já é do nicho)_'}")

    if pdf and pdf.get("estado") == "baixado":
        ls.append(f"**Texto completo:** ✅ `alchemia-library/{pdf['arquivo']}` "
                  f"(CSL `{pdf['csl_json_id']}`, via {pdf['rota']}, licença {pdf.get('licenca') or 'não declarada'})")
    elif pdf and pdf.get("estado") == "ja_na_biblioteca":
        ls.append(f"**Texto completo:** ↩️ já estava na `alchemia-library` — {pdf['motivo']}")
    elif pdf and pdf.get("estado") in ("adiado", "grande_demais", "falhou"):
        ls.append(f"**Texto completo:** ⏳ não baixado — {pdf['motivo']}")
    elif pdf and pdf.get("estado") == "baixaria":
        ls.append(f"**Texto completo:** (dry-run) {pdf['motivo']}")
    else:
        motivo = pdf["motivo"] if pdf else "colheita desligada"
        ls.append(f"**Texto completo:** ❌ só markdown — {motivo}")

    resumo = (item.get("summary") or "").strip()
    if resumo:
        if len(resumo) > 1200:
            resumo = resumo[:1197] + "…"
        ls.append("")
        ls.append("> " + md_escape(resumo).replace("\n", " "))
    ls.append("")
    return ls


def bloco_noticia(item: dict) -> str:
    titulo = md_escape(item.get("title") or "sem título")
    fonte = md_escape(item.get("source") or "?")
    url = item.get("url") or ""
    kw = item.get("keywords_matched") or []
    cauda = f" _(termo: {', '.join(md_escape(k) for k in kw[:3])})_" if kw else ""
    return f"- **{titulo}** — {fonte}{cauda}  \n  <{url}>"


def montar_markdown(dia: str, buckets: dict, meta: dict, pdfs: dict, avisos: list[str]) -> str:
    artigos = buckets["article"]
    noticias = buckets["news"]
    empresas = buckets["company"]
    newsletters = buckets["newsletter"]

    baixados = [v for v in pdfs.values() if v.get("estado") == "baixado"]
    ja_tinha = [v for v in pdfs.values() if v.get("estado") == "ja_na_biblioteca"]
    so_md = [v for v in pdfs.values() if v.get("estado") == "sem_oa"]

    L: list[str] = []
    L.append("---")
    L.append(f"data: {dia}")
    L.append("tags: [setor/science, tipo/radar, fonte/alchemia-news]")
    L.append("origem: alchemia-ai/alchemia-news (pipeline determinístico, sem LLM)")
    L.append(f"gerado_em: {datetime.now(timezone.utc).isoformat()}")
    L.append("---")
    L.append("")
    L.append(f"# Radar Alchemia News — {dia}")
    L.append("")
    L.append(
        "Registro de pesquisa do dia, gerado por `pipeline/research_export.py` a partir do que o "
        "pipeline determinístico do `alchemia-news` coletou. **Nenhum LLM participa da seleção** — "
        "relevância é palavra-chave + fonte, e todo item carrega o termo que o trouxe. Nada aqui "
        "foi resumido, reescrito ou classificado por um modelo: título, autores e resumo são os "
        "da própria fonte."
    )
    L.append("")
    L.append(
        "> **Como ler a data.** Um item entra no dia em que foi *publicado* quando a fonte informa "
        "a data, e no dia em que foi *detectado* quando não informa (41% dos artigos, PubMed "
        "sobretudo). Por isso o título diz *radar*, não *publicados em*."
    )
    L.append("")

    # -- resumo ------------------------------------------------------------------------------
    L.append("## Resumo do dia")
    L.append("")
    L.append("| | |")
    L.append("|---|---|")
    L.append(f"| Artigos e preprints no radar | **{len(artigos)}** |")
    L.append(f"| Newsletters do nicho | **{len(newsletters)}** |")
    L.append(f"| Notícias | **{len(noticias)}** |")
    L.append(f"| Atividade de empresas | **{len(empresas)}** |")
    L.append(f"| Texto completo colhido para a `alchemia-library` | **{len(baixados)}** |")
    L.append(f"| Já estavam na biblioteca | {len(ja_tinha)} |")
    L.append(f"| Sem rota open access (só markdown) | {len(so_md)} |")
    L.append("")

    if avisos:
        for a in avisos:
            L.append(f"> {a}")
            L.append("")

    # -- saúde da coleta ---------------------------------------------------------------------
    cols = (meta or {}).get("collectors") or {}
    if cols:
        L.append("## Saúde da coleta (última execução do pipeline)")
        L.append("")
        L.append(f"Início `{meta.get('last_run_started','?')}` · duração **{meta.get('duration_seconds','?')} s**")
        L.append("")
        L.append("| Coletor | Itens | Tempo | Erro |")
        L.append("|---|---:|---:|---|")
        for nome, c in cols.items():
            if not isinstance(c, dict):
                continue
            if c.get("skipped"):
                L.append(f"| `{nome}` | — | — | pulado |")
                continue
            erro = "✅" if not c.get("error") else "🔴 sim"
            L.append(f"| `{nome}` | {c.get('count','?')} | {c.get('seconds','?')} s | {erro} |")
        tot = (meta or {}).get("totals") or {}
        if tot:
            L.append("")
            L.append(
                f"Base acumulada: {tot.get('articles','?')} artigos · {tot.get('news','?')} notícias · "
                f"{tot.get('companies_activity','?')} menções de empresas."
            )
        L.append("")

    # -- biblioteca --------------------------------------------------------------------------
    L.append("## Biblioteca — o que entrou hoje")
    L.append("")
    if baixados:
        L.append("| Arquivo | ID CSL-JSON | Rota | Licença |")
        L.append("|---|---|---|---|")
        for v in baixados:
            L.append(f"| `{v['arquivo']}` | `{v['csl_json_id']}` | {v['rota']} | {v.get('licenca') or 'não declarada'} |")
        L.append("")
        L.append(
            "Todos registrados em `alchemia-library/manifest.csv` e `alchemia-library.json` "
            "(CSL-JSON, importável no Zotero). Auditável com "
            "`bash alchemia-science/alchemia-library/scripts/check_sync.sh`."
        )
    else:
        L.append("_Nenhum texto completo novo entrou na biblioteca nesta execução._")
    L.append("")

    # -- artigos -----------------------------------------------------------------------------
    L.append(f"## Artigos e preprints ({len(artigos)})")
    L.append("")
    if artigos:
        por_fonte: dict[str, list[dict]] = {}
        for it in artigos:
            por_fonte.setdefault(it.get("source") or "?", []).append(it)
        for fonte in sorted(por_fonte, key=lambda f: -len(por_fonte[f])):
            L.append(f"### {md_escape(fonte)} ({len(por_fonte[fonte])})")
            L.append("")
            for it in por_fonte[fonte]:
                chave = it.get("dedupe_key") or it.get("url") or it.get("title") or ""
                L.extend(bloco_artigo(it, pdfs.get(chave)))
    else:
        L.append("_Nenhum artigo novo no radar deste dia._")
        L.append("")

    # -- newsletters -------------------------------------------------------------------------
    # Antes de "Notícias" de propósito: é a seção de maior sinal do dia.
    L.append(f"## Newsletters do nicho ({len(newsletters)})")
    L.append("")
    if newsletters:
        por_veiculo: dict[str, list[dict]] = {}
        for it in newsletters:
            por_veiculo.setdefault(it.get("source") or "?", []).append(it)
        for veiculo in sorted(por_veiculo, key=lambda v: -len(por_veiculo[v])):
            L.append(f"### {md_escape(veiculo)} ({len(por_veiculo[veiculo])})")
            L.append("")
            L.extend(bloco_noticia(it) for it in por_veiculo[veiculo])
            L.append("")
    else:
        L.append("_Nenhuma._")
        L.append("")

    # -- notícias ----------------------------------------------------------------------------
    L.append(f"## Notícias ({len(noticias)})")
    L.append("")
    L.extend(bloco_noticia(it) for it in noticias) if noticias else L.append("_Nenhuma._")
    L.append("")

    # -- empresas ----------------------------------------------------------------------------
    L.append(f"## Atividade de empresas ({len(empresas)})")
    L.append("")
    if empresas:
        por_emp: dict[str, list[dict]] = {}
        for it in empresas:
            por_emp.setdefault(it.get("company_slug") or it.get("source") or "?", []).append(it)
        for emp in sorted(por_emp):
            L.append(f"### {md_escape(emp)} ({len(por_emp[emp])})")
            L.append("")
            L.extend(bloco_noticia(it) for it in por_emp[emp])
            L.append("")
    else:
        L.append("_Nenhuma._")
        L.append("")

    # -- o que o Axel anunciou -----------------------------------------------------------------
    posts = sorted(DISCORD_DIR.glob(f"{dia}*.md")) if DISCORD_DIR.is_dir() else []
    if posts:
        L.append(f"## Publicado no Discord ({len(posts)})")
        L.append("")
        L.append(
            "Cópia verbatim do que o Axel anunciou no canal público, gravada pela própria rotina "
            "de anúncio. Fecha o ciclo do dia: o que foi coletado, o que virou texto completo na "
            "biblioteca, e o que a comunidade efetivamente viu."
        )
        L.append("")
        for p in posts:
            try:
                conteudo = p.read_text(encoding="utf-8").strip()
            except OSError:
                continue
            L.append(f"<details><summary><code>{p.name}</code></summary>")
            L.append("")
            L.append("```text")
            L.append(conteudo.replace("```", "`​``"))
            L.append("```")
            L.append("")
            L.append("</details>")
            L.append("")

    L.append("---")
    L.append("")
    L.append(
        "Gerado por `alchemia-ai/alchemia-news/pipeline/research_export.py`. Regenerar este dia: "
        f"`python -m pipeline.research_export --date {dia}`. O arquivo é reescrito na íntegra a "
        "cada execução (é derivado, não append-only) — a fonte de verdade continua sendo os JSONs "
        "do `alchemia-news` e a própria `alchemia-library`."
    )
    L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Exporta o dia do Alchemia News para alchemia-science")
    ap.add_argument("--date", default=date.today().isoformat(), help="Dia a exportar (AAAA-MM-DD, default: hoje)")
    ap.add_argument("--no-pdf", action="store_true", help="Não tenta colher texto completo")
    ap.add_argument("--max-pdf", type=int, default=6, help="Teto de PDFs baixados por execução (default 6; 0 desliga)")
    ap.add_argument("--max-mb", type=float, default=60.0, help="Teto de tamanho por PDF em MB (default 60)")
    ap.add_argument("--max-total-mb", type=float, default=150.0,
                    help="Teto de volume TOTAL baixado por execução em MB (default 150)")
    ap.add_argument("--min-free-gb", type=float, default=20.0, help="Piso de espaço livre em disco (default 20 GB)")
    ap.add_argument("--dry-run", action="store_true", help="Não escreve nada em disco; só relata")
    args = ap.parse_args()

    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print(f"--date invalido: {args.date} (esperado AAAA-MM-DD)", file=sys.stderr)
        return 2

    if not SCIENCE_ROOT.is_dir():
        print(f"alchemia-science nao encontrado em {SCIENCE_ROOT}", file=sys.stderr)
        return 1

    buckets: dict[str, list[dict]] = {"article": [], "news": [], "company": [], "newsletter": []}
    for fname, _label, key in SECOES:
        dados = load_json(DATA_DIR / fname, [])
        if not isinstance(dados, list):
            continue
        buckets[key] = [it for it in dados if isinstance(it, dict) and dia_do_item(it) == args.date]

    # Newsletters chegam dentro de news.json (são notícia), mas ganham seção própria no radar:
    # veículo curado do nicho (Drug Hunter, Longevity.Technology) tem sinal muito mais alto que o
    # feed genérico do Google News, e misturar os dois esconde o que mais interessa ao fundador.
    buckets["newsletter"] = [it for it in buckets["news"] if it.get("source_type") == "newsletter"]
    buckets["news"] = [it for it in buckets["news"] if it.get("source_type") != "newsletter"]

    total = sum(len(v) for v in buckets.values())
    print(f"[research_export] {args.date}: {len(buckets['article'])} artigos, "
          f"{len(buckets['news'])} noticias, {len(buckets['company'])} de empresas.")

    if total == 0:
        print("[research_export] nada no radar deste dia - nenhum arquivo gerado.")
        return 0

    relato: list[str] = []
    pdfs, avisos = colher_pdfs(buckets["article"], args, relato)
    for linha in relato:
        print(linha)
    for aviso in avisos:
        # Os avisos vão para o markdown COM emoji e marcação; o stdout precisa ser ASCII puro.
        # Motivo real: este script roda pelo Task Scheduler, cujo console é cp1252 — um `⏭️` no
        # stdout levanta UnicodeEncodeError e derruba a execução inteira por causa de um caractere
        # decorativo. O `.cmd` já exporta PYTHONIOENCODING=utf-8, mas depender disso seria uma
        # bomba-relógio para qualquer outro chamador.
        limpo = re.sub(r"[*`_]", "", aviso)
        # Transliterar, não descartar: `.encode("ascii","ignore")` sozinho transformaria
        # "execução" em "execuo" — o log fica ilegível justamente na linha que explica um
        # comportamento incomum. NFKD separa o acento da letra, e aí o descarte só come o acento.
        dobrado = "".join(
            c for c in unicodedata.normalize("NFKD", limpo) if not unicodedata.combining(c)
        )
        print("[research_export] " + dobrado.encode("ascii", "ignore").decode("ascii").strip())

    # Contagem por desfecho — sem isso a colheita seria uma caixa-preta para quem lê só o stdout
    # (a rotina do Baker roda sem ninguém olhando, e "0 baixados" tem causas muito diferentes).
    if pdfs:
        contagem: dict[str, int] = {}
        for v in pdfs.values():
            contagem[v["estado"]] = contagem.get(v["estado"], 0) + 1
        print("[research_export] desfecho da colheita: "
              + ", ".join(f"{k}={n}" for k, n in sorted(contagem.items())))
        for v in pdfs.values():
            if v["estado"] in ("falhou", "grande_demais"):
                print(f"[research_export]   ! {v['estado']}: {v['motivo']}")

    meta = load_json(DATA_DIR / "meta.json", {})
    md = montar_markdown(args.date, buckets, meta, pdfs, avisos)
    destino = RESEARCH_DIR / f"{args.date}-alchemia-news-radar.md"

    if args.dry_run:
        print(f"[research_export] dry-run: escreveria {destino} ({len(md)} chars)")
        return 0

    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    destino.write_text(md, encoding="utf-8")
    baixados = sum(1 for v in pdfs.values() if v.get("estado") == "baixado")
    print(f"[research_export] escrito: {destino}")
    print(f"[research_export] PDFs novos na alchemia-library: {baixados}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
