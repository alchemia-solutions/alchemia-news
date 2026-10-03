"""A carga inicial (spec 2026-10-02-radar-na-vm-postgres, critérios 1, 2, 3 e 4).

A primeira classe prova as regras de fusão, sem git e sem banco. A segunda carrega o acervo REAL (os JSON do
`origin/main` e todo o histórico do git deste checkout) num banco descartável com o esquema da 0024 do System, duas
vezes, e confere:
  1. `count(*)` de `radar.item` igual ao total único que a montagem informou, sem tolerância;
  2. as chaves de 2026-09-07 ausentes do `origin/main` (as 3.464 da spec, contadas por arquivo) estão no banco, e as
     de `companies_activity.json` com empresa;
  3. a segunda carga (agora pelo pacote, o caminho da VM) dá 0 inserções e 0 atualizações;
  4. toda chave do `companies_activity.json` de hoje tem `company_slug` no banco.
Precisa de PG_DESCARTAVEL_URL e de `origin/main` com histórico (leva cerca de meio minuto).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

PIPELINE = Path(__file__).resolve().parents[1]
for p in (PIPELINE, PIPELINE / "tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import migrar_para_postgres as mig  # noqa: E402
from collectors import common  # noqa: E402
from pg_descartavel import Banco, precisa_de_banco  # noqa: E402

T1 = datetime(2026, 9, 1, tzinfo=timezone.utc)
T2 = datetime(2026, 9, 5, tzinfo=timezone.utc)


def rec(**kw) -> dict:
    base = {"kind": "news", "title": "t", "url": "https://a.org/1", "source": "S", "source_type": "news",
            "published_date": None, "collected_at": "2026-09-03T00:00:00+00:00", "authors": [], "summary": "",
            "doi": None, "company_slug": None, "keywords_matched": [], "extra": {}}
    base.update(kw)
    return base


class RegrasDeFusao(unittest.TestCase):
    def test_coletado_mais_antigo_empresa_vence_termos_unidos_resto_do_mais_recente(self):
        u = mig.Uniao()
        k = u.fundir(rec(company_slug="butantan", keywords_matched=["CADD"], summary="velho",
                         collected_at="2026-09-02T00:00:00+00:00"), "news", T1)
        u.fundir(rec(keywords_matched=["vacina"], summary="novo", title="título novo",
                     collected_at="2026-09-04T00:00:00+00:00"), "news", T2)
        r = u.itens[k]
        self.assertEqual(r["collected_at"], "2026-09-02T00:00:00+00:00")
        self.assertEqual(r["company_slug"], "butantan")  # o registro mais novo veio sem empresa: não apaga
        self.assertEqual(r["keywords_matched"], ["CADD", "vacina"])
        self.assertEqual((r["summary"], r["title"]), ("novo", "título novo"))
        self.assertEqual((u.primeiro[k], u.ultimo[k]), (T1, T2))

    def test_campo_vazio_do_mais_recente_nao_apaga(self):
        u = mig.Uniao()
        k = u.fundir(rec(summary="tem resumo", authors=["A"]), "news", T1)
        u.fundir(rec(summary="", authors=[]), "news", T2)
        self.assertEqual((u.itens[k]["summary"], u.itens[k]["authors"]), ("tem resumo", ["A"]))

    def test_supabase_so_preenche_ausente(self):
        u = mig.Uniao()
        k = u.fundir(rec(summary="do git"), "news", T1)
        # a linha do Supabase traz a dedupe_key gravada (coluna própria): é ela que identifica, não o recálculo
        self.assertFalse(u.so_ausente(rec(summary="do supabase", doi="10.1/x", dedupe_key=k), T2))
        self.assertEqual((u.itens[k]["summary"], u.itens[k]["doi"]), ("do git", "10.1/x"))
        self.assertTrue(u.so_ausente(rec(url="https://a.org/2"), T2))
        self.assertEqual(len(u.itens), 2)

    def test_kind_ausente_vem_do_arquivo(self):
        u = mig.Uniao()
        r = rec()
        del r["kind"]
        k = u.fundir(r, "article", T1)
        self.assertEqual(u.itens[k]["kind"], "article")


def _tem_historico() -> bool:
    try:
        for ref in ("origin/main", "6800a38^{commit}"):
            subprocess.run(["git", "rev-parse", "--verify", ref], cwd=PIPELINE.parent, capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


@precisa_de_banco
@unittest.skipUnless(_tem_historico(), "sem origin/main e 6800a38 neste checkout")
class CargaReal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.banco = Banco()
        cls.url = cls.banco.url("alchemia_radar")
        cls.carga = mig.montar(common.REPO_ROOT, "origin/main")
        cls.r0 = mig.carregar(cls.url, cls.carga, dry_run=True)
        cls.r1 = mig.carregar(cls.url, cls.carga)
        with tempfile.TemporaryDirectory() as tmp:
            pacote = Path(tmp) / "carga.json.gz"
            mig.salvar_pacote(cls.carga, pacote)
            cls.r2 = mig.carregar(cls.url, mig.ler_pacote(pacote))
        print("\n[carga] " + json.dumps({"relatorio": {k: cls.carga.relatorio[k] for k in ("uniao", "origens", "perdidas")},
                                         "primeira": cls.r1["itens"], "segunda": cls.r2["itens"]}, ensure_ascii=False),
              file=sys.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.banco.apagar()

    def test_0_dry_run_conta_e_nao_grava(self):
        self.assertEqual(self.r0["antes"]["item"], 0)
        self.assertEqual(self.r0["chaves_da_carga"], self.carga.relatorio["uniao"])
        self.assertNotIn("depois", self.r0)
        self.assertEqual(self.r1["antes"]["item"], 0)  # a carga de verdade, logo depois, achou o banco vazio

    def test_1_contagem_igual_ao_total_unico(self):
        self.assertEqual(self.banco.como_super("select count(*) from radar.item")[0][0], self.carga.relatorio["uniao"])
        self.assertEqual(self.carga.relatorio["linhas"], self.carga.relatorio["uniao"])
        self.assertEqual(self.carga.relatorio["recusados"], [])
        # a versão de 2026-09-07 que não parseia é contada pelo commit, não engolida
        self.assertIn("d5eb59a", {v["commit"] for v in self.carga.relatorio["versoes_que_nao_parseiam"]})

    def test_2_chaves_de_2026_09_07_voltam(self):
        conf = self.carga.conferencia["6800a38"]
        self.assertGreater(len(conf["chaves"]), 0)
        with self.subTest("todas no banco"):
            ((n,),) = self.banco.como_super("select count(*) from radar.item where dedupe_key = any(%s)", (conf["chaves"],))
            self.assertEqual(n, len(conf["chaves"]))
        with self.subTest("as de empresa, com empresa"):
            ((n,),) = self.banco.como_super("select count(*) from radar.item where dedupe_key = any(%s) and company_slug is null",
                                            (conf["de_empresa"],))
            self.assertEqual(n, 0)

    def test_3_segunda_carga_nao_muda_nada(self):
        self.assertEqual((self.r2["itens"]["novos"], self.r2["itens"]["atualizados"]), (0, 0))
        self.assertEqual(self.r2["execucoes_novas"], 0)
        self.assertEqual(self.r2["newsletters"], {"novas": 0, "atualizadas": 0})
        self.assertEqual(self.r2["depois"], self.r1["depois"])

    def test_4_toda_chave_de_companies_activity_tem_empresa(self):
        dado = json.loads(subprocess.run(["git", "show", "origin/main:pipeline/data/companies_activity.json"],
                                         cwd=PIPELINE.parent, capture_output=True, check=True).stdout)
        chaves = [r.get("dedupe_key") or common.dedupe_key(r) for r in dado]
        ((n, sem),) = self.banco.como_super(
            "select count(*), count(*) filter (where company_slug is null) from radar.item where dedupe_key = any(%s)", (chaves,))
        self.assertEqual((n, sem), (len(set(chaves)), 0))

    def test_5_depois_da_primeira_coleta_da_vm_nenhum_snapshot_entra(self):
        # a carga final da virada (R6) não pode pôr um snapshot do Actions à frente da última coleta real em radar.meta:
        # a view escolhe pelo maior id, e até um snapshot mais antigo ganharia id maior
        self.banco.como_super("insert into radar.execucao (origem, iniciada_em, terminada_em, estado) "
                              "values ('agendada', '2026-10-05T10:00Z', '2026-10-05T10:03Z', 'ok')")
        exe = [{"iniciada_em": t, "terminada_em": t, "estado": "ok", "duracao_s": 1, "coletores": {}, "totais": {}}
               for t in ("2026-10-04T09:40:00+00:00", "2026-10-05T15:40:00+00:00")]
        sintetica = mig.Carga("teste", "0" * 40, [], exe, [], self.carga.catalogos, {})
        r = mig.carregar(self.url, sintetica)
        self.assertEqual((r["execucoes_novas"], r["execucoes_puladas_por_haver_coleta_da_vm"]), (0, 2))
        ((origem,),) = self.banco.como("alchemia_app", "select e.origem from radar.meta m join radar.execucao e "
                                                       "on e.terminada_em = m.last_run_finished")
        self.assertEqual(origem, "agendada")

    def test_execucoes_newsletters_catalogos(self):
        self.assertEqual(self.r1["depois"]["execucao_importada"], self.carga.relatorio["execucoes"])
        self.assertEqual(self.r1["depois"]["newsletter"], self.carga.relatorio["newsletters"])
        self.assertEqual(self.r1["depois"]["catalogo"], sum(self.carga.relatorio["catalogos"].values()))
        ids = [r[0] for r in self.banco.como_super("select id from radar.execucao order by iniciada_em")]
        self.assertEqual(ids, sorted(ids))  # o id segue a ordem do carimbo


if __name__ == "__main__":
    unittest.main()
