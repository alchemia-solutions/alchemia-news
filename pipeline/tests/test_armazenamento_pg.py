"""O escritor do Radar no Postgres (spec 2026-10-02-radar-na-vm-postgres, critérios 3, 5, 6 e 7), nos dois sentidos.

Sem rede: os coletores são trocados por dublês. Os testes com banco usam o esquema REAL do System (migração 0024) num
cluster descartável (pipeline/tests/pg_descartavel.py) e são pulados sem PG_DESCARTAVEL_URL. Da raiz do repositório:

    PG_DESCARTAVEL_URL=<url> pipeline/.venv/Scripts/python.exe -m unittest pipeline.tests.test_armazenamento_pg -v
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

PIPELINE = Path(__file__).resolve().parents[1]
for p in (PIPELINE, PIPELINE / "tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import armazenamento_pg as apg  # noqa: E402
import run_all  # noqa: E402
from collectors import common  # noqa: E402
from pg_descartavel import Banco, precisa_de_banco  # noqa: E402

AGORA = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)


def item(url: str, **kw) -> dict:
    base = {"kind": "news", "title": f"t {url}", "url": url, "source": "Fonte", "source_type": "news",
            "published_date": "2026-10-01", "collected_at": "2026-10-02T10:00:00+00:00", "authors": [],
            "summary": "", "doi": None, "company_slug": None, "keywords_matched": ["CADD"], "extra": {}}
    base.update(kw)
    base["dedupe_key"] = common.dedupe_key(base)
    return base


def eventos(saida: str) -> list[dict]:
    out = []
    for linha in saida.splitlines():
        try:
            out.append(json.loads(linha))
        except ValueError:
            continue
    return out


# --- sem banco ------------------------------------------------------------------------------------

class SemBanco(unittest.TestCase):
    def test_data_1970_vira_nula_e_data_ruim_tambem(self):
        self.assertIsNone(apg.data_publicada("1970-01-01"))
        self.assertIsNone(apg.data_publicada("2026-02-31"))
        self.assertEqual(apg.data_publicada("2026-10-01T08:00:00Z"), "2026-10-01")

    def test_chave_acima_do_limite_e_recusada_com_motivo(self):
        lote = apg.Lote()
        lote.acrescentar(item("https://x.org/" + secrets.token_hex(1500)), visto_em=AGORA)
        self.assertEqual(len(lote.linhas), 0)
        self.assertIn("bytes", lote.recusados[0]["motivo"])

    def test_chave_real_mais_longa_cabe(self):
        # 1.030 caracteres é a dedupe_key mais longa medida no acervo (spec, "Comprimentos")
        url = "https://news.google.com/rss/articles/" + "a" * (1030 - len("url:https://news.google.com/rss/articles/"))
        lote = apg.Lote()
        lote.acrescentar(item(url), visto_em=AGORA)
        self.assertEqual(len(next(iter(lote.linhas))), 1030)

    def test_mesma_chave_no_lote_funde_empresa_e_termos(self):
        lote = apg.Lote()
        lote.acrescentar(item("https://a.org/1", keywords_matched=["CADD"]), coletores=["googlenews"], visto_em=AGORA)
        lote.acrescentar(item("https://a.org/1", company_slug="butantan", keywords_matched=["vacina"], summary="s"),
                         coletores=["companies"], visto_em=AGORA)
        (linha,) = lote.linhas.values()
        self.assertEqual(linha["company_slug"], "butantan")
        self.assertEqual(linha["keywords_matched"], ["CADD", "vacina"])
        self.assertEqual(linha["coletores"], ["googlenews", "companies"])
        self.assertEqual(linha["summary"], "s")

    def test_nul_some_do_texto(self):
        linha = apg.para_linha(item("https://a.org/n", title="a\x00b"), visto_em=AGORA)
        self.assertEqual(linha["title"], "ab")

    def test_estado(self):
        self.assertEqual(apg.estado_da_execucao({"a": {"count": 1, "error": None}, "b": {"skipped": True}}), "ok")
        self.assertEqual(apg.estado_da_execucao({"a": {"count": 1, "error": None}, "b": {"count": 0, "error": "x"}}), "parcial")
        self.assertEqual(apg.estado_da_execucao({"a": {"count": 0, "error": "x"}}), "falhou")

    def test_sem_segredo_tira_a_senha(self):
        senha = secrets.token_hex(8)  # montada na hora: nenhum literal de URL com senha no repositório
        url = "postgres://alchemia_radar:" + senha + "@db:5432/system_prod"
        msg = apg.sem_segredo(f"falhou em {url} com {senha}", url)
        self.assertNotIn(senha, msg)

    def test_catalogo_vazio_ou_repetido_e_recusado(self):
        with self.assertRaises(apg.CatalogoInvalido):
            apg.entradas_de_catalogo("companies", {"companies": []})
        with self.assertRaises(apg.CatalogoInvalido):
            apg.entradas_de_catalogo("companies", {"companies": [{"slug": "a"}, {"slug": "a"}]})
        self.assertEqual(len(apg.entradas_de_catalogo("companies", {"companies": [{"slug": "a"}, {"slug": "b"}]})), 2)


class ImportarCommonNaoCriaPastas(unittest.TestCase):
    """Na VM o contêiner é só-leitura: importar o pipeline não pode criar `pipeline/data/` (spec, "Escrita idempotente")."""

    def test_import_numa_copia_sem_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "pipeline"
            shutil.copytree(PIPELINE / "collectors", destino / "collectors", ignore=shutil.ignore_patterns("__pycache__", "data", "logs"))
            shutil.copytree(PIPELINE / "config", destino / "config")
            r = subprocess.run([sys.executable, "-B", "-c", "from collectors import common"], cwd=destino, capture_output=True)
            self.assertEqual(r.returncode, 0, r.stderr.decode(errors="replace"))
            self.assertFalse((destino / "data").exists())
            self.assertFalse((destino / "logs").exists())


class DestinoJsonSegueIgual(unittest.TestCase):
    """O modo do Actions (`--destino json`, o padrão) continua gravando os mesmos arquivos, agora numa pasta temporária."""

    def test_grava_os_quatro_json_e_o_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            alvos = {"ARTICLES_PATH": d / "articles.json", "NEWS_PATH": d / "news.json",
                     "COMPANIES_ACTIVITY_PATH": d / "companies_activity.json", "META_PATH": d / "meta.json"}
            colheita = {"pubmed": [item("https://doi.org/10.1/a", kind="article", doi="10.1/a")],
                        "googlenews": [item("https://n.org/1")], "companies": [item("https://n.org/2", company_slug="x")]}
            with dubles(colheita), contextlib.ExitStack() as pilha, contextlib.redirect_stdout(io.StringIO()), \
                    mock.patch.dict(os.environ, {"RADAR_DESTINO": ""}):
                for nome, caminho in alvos.items():
                    pilha.enter_context(mock.patch.object(run_all, nome, caminho))
                pilha.enter_context(mock.patch.object(common, "RUNS_DIR", d / "runs"))
                self.assertEqual(run_all.main([]), 0)
            meta = json.loads(alvos["META_PATH"].read_text(encoding="utf-8"))
            self.assertEqual((meta["totals"]["articles"], meta["totals"]["news"], meta["totals"]["companies_activity"]), (1, 2, 1))
            self.assertEqual(len(list((d / "runs").glob("*-pipeline_run.json"))), 1)


# --- com banco ------------------------------------------------------------------------------------

def dubles(colheita: dict[str, list[dict] | Exception]):
    """Troca `run_all._funcao` por funções sem rede; chave ausente devolve lista vazia."""
    def funcao(chave, _dias):
        def f():
            v = colheita.get(chave, [])
            if isinstance(v, Exception):
                raise v
            return [dict(x) for x in v]
        return f
    return mock.patch.object(run_all, "_funcao", funcao)


@precisa_de_banco
class ComBanco(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.banco = Banco()
        cls.url = cls.banco.url("alchemia_radar")
        print(f"\n[concessões: {cls.banco.fonte_das_concessoes}]", file=sys.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.banco.apagar()

    def setUp(self):
        self.banco.como_super("truncate radar.item, radar.catalogo, radar.newsletter, radar.execucao restart identity cascade")

    def coletar(self, colheita, *args) -> tuple[int, list[dict]]:
        saida = io.StringIO()
        with dubles(colheita), mock.patch.dict(os.environ, {"DATABASE_URL_RADAR": self.url}), \
                mock.patch.object(common, "save_json", side_effect=AssertionError("modo postgres gravou arquivo")), \
                contextlib.redirect_stdout(saida):
            codigo = run_all.main(["--destino", "postgres", *args])
        return codigo, eventos(saida.getvalue())

    # critério 3: upsert idempotente e só-preenche-vazio
    def test_upsert_idempotente_e_so_preenche_vazio(self):
        linhas = [apg.para_linha(item(f"https://a.org/{i}"), visto_em=AGORA) for i in range(3)]
        with apg.conectar(self.url) as c, c.transaction(), c.cursor() as cur:
            primeira = apg.gravar_itens(cur, linhas)
        with apg.conectar(self.url) as c, c.transaction(), c.cursor() as cur:
            segunda = apg.gravar_itens(cur, linhas)
        self.assertEqual(primeira.total(), (3, 0))
        self.assertEqual(segunda.total(), (0, 0))

        com_resumo = apg.para_linha(item("https://a.org/0", summary="novo", company_slug="x", keywords_matched=["vacina"],
                                         collected_at="2026-09-01T00:00:00+00:00"), visto_em=AGORA + timedelta(hours=1))
        with apg.conectar(self.url) as c, c.transaction(), c.cursor() as cur:
            apg.gravar_itens(cur, [com_resumo])
        with apg.conectar(self.url) as c, c.transaction(), c.cursor() as cur:
            outro = apg.gravar_itens(cur, [apg.para_linha(item("https://a.org/0", summary="NÃO deve entrar"), visto_em=AGORA)])
        ((summary, slug, kws, coletado, vista),) = self.banco.como_super(
            "select summary, company_slug, keywords_matched, collected_at, vista_em from radar.item where dedupe_key = %s",
            (com_resumo["dedupe_key"],))
        self.assertEqual((summary, slug, kws), ("novo", "x", ["CADD", "vacina"]))
        self.assertEqual(coletado, datetime(2026, 9, 1, tzinfo=timezone.utc))  # o mais antigo visto
        self.assertEqual(vista, AGORA + timedelta(hours=1))  # vista_em não volta no tempo
        self.assertEqual(outro.total(), (0, 0))
        self.assertEqual(self.banco.como_super("select count(*) from radar.item")[0][0], 3)

    def test_banco_recusa_chave_grande_incompressivel(self):
        # o contrário do Lote: o `check` do banco também segura (e o texto aleatório não comprime antes de conferir)
        import psycopg
        chave = "url:" + secrets.token_hex(1500)
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.banco.como("alchemia_radar",
                            "insert into radar.item (dedupe_key, kind, title, url, source, source_type, collected_at, vista_em) "
                            "values (%s, 'news', 't', 'u', 's', 'news', now(), now())", (chave,))

    # critério 3: a coleta duas vezes contra a mesma resposta das fontes dá zero novos na segunda
    def test_coleta_duas_vezes_sem_rede(self):
        colheita = {
            "pubmed": [item("https://doi.org/10.1/a", kind="article", doi="10.1/a", source="PubMed", source_type="journal")],
            "googlenews": [item("https://n.org/1"), item("https://n.org/2")],
            "companies": [item("https://n.org/2", company_slug="butantan")],
        }
        c1, ev1 = self.coletar(colheita)
        c2, ev2 = self.coletar(colheita)
        self.assertEqual((c1, c2), (0, 0))
        fim1 = next(e for e in ev1 if e["evento"] == "radar.execucao.fim")
        fim2 = next(e for e in ev2 if e["evento"] == "radar.execucao.fim")
        self.assertEqual((fim1["totais"]["new_articles_this_run"], fim1["totais"]["new_news_this_run"]), (1, 2))
        self.assertEqual(fim1["totais"]["companies_activity"], 1)  # o item achado pelos dois coletores ganhou a empresa
        self.assertEqual((fim2["totais"]["new_articles_this_run"], fim2["totais"]["new_news_this_run"]), (0, 0))
        self.assertEqual(sum(fim2["atualizados"].values()), 0)
        execs = self.banco.como_super("select estado, origem, terminada_em is not null from radar.execucao order by id")
        self.assertEqual(execs, [("ok", "manual", True), ("ok", "manual", True)])
        ((col,),) = self.banco.como_super("select coletores from radar.item where dedupe_key = %s", (colheita["companies"][0]["dedupe_key"],))
        self.assertEqual(col, ["googlenews", "companies"])
        # a leitura do System: a view do contrato de meta.json mostra a execução que acabou de terminar
        ((fim,),) = self.banco.como("alchemia_app", "select last_run_finished from radar.meta")
        ((ultima,),) = self.banco.como_super("select max(terminada_em) from radar.execucao")
        self.assertEqual(fim, ultima)

    # critério 6: uma execução por vez
    def test_trava_ocupada_sai_sem_gravar(self):
        with apg.conectar(self.url) as outra:
            self.assertTrue(apg.tentar_trava(outra))
            codigo, ev = self.coletar({"googlenews": [item("https://n.org/1")]})
        self.assertEqual(codigo, 0)
        self.assertIn("radar.execucao.ocupado", [e["evento"] for e in ev])
        self.assertEqual(self.banco.como_super("select count(*) from radar.execucao")[0][0], 0)
        self.assertEqual(self.banco.como_super("select count(*) from radar.item")[0][0], 0)

    # critério 7: fonte fora do ar dá `parcial`, com o erro no coletor e os itens dos outros preservados
    def test_fonte_fora_do_ar_e_parcial(self):
        parcial = common.ColetaParcial("feed 2 caiu", itens=[item("https://f.org/sobrou")])
        codigo, ev = self.coletar({"googlenews": [item("https://n.org/1")], "biorxiv": RuntimeError("HTTP 503"),
                                   "newsletters": parcial})
        self.assertEqual(codigo, 0)
        self.assertIn("radar.execucao.parcial", [e["evento"] for e in ev])
        ((estado, coletores),) = self.banco.como_super("select estado, coletores from radar.execucao")
        self.assertEqual(estado, "parcial")
        self.assertIn("HTTP 503", coletores["biorxiv"]["error"])
        self.assertEqual(coletores["biorxiv"]["count"], 0)
        self.assertEqual(coletores["newsletters"]["count"], 1)
        self.assertIsNone(coletores["pubmed"]["error"])  # zero sem erro continua distinguível de zero por falha
        self.assertEqual(self.banco.como_super("select count(*) from radar.item")[0][0], 2)

    # critério 7: banco fora do ar dá saída 1 e log, sem arquivo e sem a senha na saída
    def test_banco_fora_do_ar(self):
        senha = secrets.token_hex(8)
        url = "postgres://alchemia_radar:" + senha + "@127.0.0.1:1/system_prod"
        saida = io.StringIO()
        with dubles({}), mock.patch.dict(os.environ, {"DATABASE_URL_RADAR": url}), \
                mock.patch.object(common, "save_json", side_effect=AssertionError("gravou arquivo")), \
                contextlib.redirect_stdout(saida):
            codigo = run_all.main(["--destino", "postgres"])
        self.assertEqual(codigo, 1)
        self.assertIn("radar.execucao.falhou", [e["evento"] for e in eventos(saida.getvalue())])
        self.assertNotIn(senha, saida.getvalue())

    def test_contrato_divergente_falha_alto(self):
        self.banco.como_super("alter table radar.item add column so_do_system text")
        try:
            codigo, ev = self.coletar({"googlenews": [item("https://n.org/1")]})
        finally:
            self.banco.como_super("alter table radar.item drop column so_do_system")
        self.assertEqual(codigo, 1)
        falha = next(e for e in ev if e["evento"] == "radar.execucao.falhou")
        self.assertIn("so_do_system", falha["diferenca"])
        self.assertEqual(self.banco.como_super("select count(*) from radar.execucao")[0][0], 0)
        # e o sentido contrário: com o esquema de volta, o contrato confere
        with apg.conectar(self.url) as c:
            apg.conferir_contrato(c)

    def test_execucao_orfa_vira_falhou(self):
        self.banco.como_super("insert into radar.execucao (origem, iniciada_em, estado) values ('agendada', now() - interval '1 day', 'rodando')")
        codigo, _ = self.coletar({})
        self.assertEqual(codigo, 0)
        self.assertEqual(self.banco.como_super("select estado from radar.execucao order by id"), [("falhou",), ("ok",)])

    def test_catalogo_remove_slug_que_saiu_e_recusa_yaml_vazio(self):
        cats = {t: [{"slug": "a", "posicao": 0, "dados": {"slug": "a"}}, {"slug": "b", "posicao": 1, "dados": {"slug": "b"}}]
                for t in apg.TIPOS_DE_CATALOGO}
        with apg.conectar(self.url) as c, c.transaction(), c.cursor() as cur:
            apg.gravar_catalogos(cur, cats)
        cats["companies"] = cats["companies"][:1]
        with apg.conectar(self.url) as c, c.transaction(), c.cursor() as cur:
            res = apg.gravar_catalogos(cur, cats)
        self.assertEqual(res["companies"]["removidos"], 1)
        cats["resources"] = []
        with self.assertRaises(apg.CatalogoInvalido), apg.conectar(self.url) as c, c.transaction(), c.cursor() as cur:
            apg.gravar_catalogos(cur, cats)
        self.assertEqual(self.banco.como_super("select count(*) from radar.catalogo where tipo = 'resources'")[0][0], 2)

    def test_catalogos_reais_entram_na_ordem_do_yaml(self):
        self.coletar({})
        ((n,),) = self.banco.como_super("select count(*) from radar.catalogo where tipo = 'companies'")
        self.assertEqual(n, len(common.load_companies()))
        ((primeiro,),) = self.banco.como("alchemia_app", "select dados->>'slug' from radar.catalogo where tipo = 'companies' order by posicao limit 1")
        self.assertEqual(primeiro, common.load_companies()[0]["slug"])


# critério 5: mínimo privilégio nos dois sentidos
@precisa_de_banco
class PapelMinimo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.banco = Banco()

    @classmethod
    def tearDownClass(cls):
        cls.banco.apagar()

    def negado(self, papel, texto):
        import psycopg
        with self.assertRaises(psycopg.errors.InsufficientPrivilege, msg=f"{papel}: {texto}"):
            self.banco.como(papel, texto)

    def test_radar_le_e_escreve_o_esquema_radar(self):
        self.banco.como("alchemia_radar", "insert into radar.item (dedupe_key, kind, title, url, source, source_type, collected_at, vista_em) "
                                          "values ('url:https://p.org/1', 'news', 't', 'u', 's', 'news', now(), now())")
        self.assertEqual(self.banco.como("alchemia_radar", "select count(*) from radar.item")[0][0], 1)
        self.banco.como("alchemia_radar", "select * from radar.meta")
        self.banco.como("alchemia_radar", "insert into radar.execucao (origem, iniciada_em, estado) values ('manual', now(), 'rodando')")

    def test_radar_nao_alcanca_public_nem_ddl_nem_delete(self):
        self.negado("alchemia_radar", 'select * from public."user"')
        self.negado("alchemia_radar", "create table radar.intrusa (x int)")
        self.negado("alchemia_radar", "create table public.intrusa (x int)")
        self.negado("alchemia_radar", "delete from radar.item")
        self.negado("alchemia_radar", "drop table radar.item")
        self.negado("alchemia_radar", "select * from drizzle.__drizzle_migrations")

    def test_app_so_le_o_radar(self):
        self.banco.como("alchemia_app", "select count(*) from radar.item")
        self.banco.como("alchemia_app", "select * from radar.meta")
        self.negado("alchemia_app", "insert into radar.item (dedupe_key, kind, title, url, source, source_type, collected_at, vista_em) "
                                    "values ('url:https://p.org/2', 'news', 't', 'u', 's', 'news', now(), now())")
        self.negado("alchemia_app", "delete from radar.catalogo")


if __name__ == "__main__":
    unittest.main()
