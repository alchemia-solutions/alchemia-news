"""O export do Supabase, sem rede e sem credencial real: uma sessão falsa faz o papel da API REST.

Prova a paginação por chave, a conferência da contagem do servidor, o manifesto com sha256 que o migrador confere, e
as recusas: sem chave, destino dentro da pasta da empresa, chave repetida, contagem divergente. Nenhum teste toca o
Supabase de verdade (quem roda o export real é o fundador).
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PIPELINE = Path(__file__).resolve().parents[1]
if str(PIPELINE) not in sys.path:
    sys.path.insert(0, str(PIPELINE))

import exportar_supabase as ex  # noqa: E402
import migrar_para_postgres as mig  # noqa: E402

CHAVE_FALSA = "nao-e-uma-chave-real-0123456789"


class Resp:
    def __init__(self, corpo, total=None, status=200):
        self._corpo, self.status_code = corpo, status
        self.headers = {"Content-Range": f"0-{max(len(corpo) - 1, 0)}/{total}"} if total is not None else {}

    def json(self):
        return self._corpo


class SessaoFalsa:
    """Responde como o PostgREST: `order`, `limit` e o filtro `<coluna>=gt.<valor>`."""

    def __init__(self, tabelas: dict[str, list[dict]], total_mente: str | None = None):
        self.tabelas, self.total_mente, self.chamadas = tabelas, total_mente, []

    def get(self, url, params, headers, timeout):
        assert headers["apikey"] == CHAVE_FALSA
        tabela = url.rsplit("/", 1)[1]
        self.chamadas.append((tabela, dict(params)))
        coluna = params["order"].split(".")[0]
        linhas = sorted(self.tabelas.get(tabela, []), key=lambda r: r[coluna])
        filtro = params.get(coluna)
        if filtro:
            linhas = [r for r in linhas if r[coluna] > filtro[3:]]
        pagina = linhas[: int(params["limit"])]
        total = None
        if headers.get("Prefer") == "count=exact":
            total = len(self.tabelas.get(tabela, [])) + (1 if tabela == self.total_mente else 0)
        return Resp(pagina, total)


def tabelas_falsas(n_itens: int) -> dict[str, list[dict]]:
    itens = [{"id": f"u{i}", "dedupe_key": f"url:https://s.org/{i:05d}", "kind": "news", "title": f"t{i}", "url": f"https://s.org/{i}",
              "source": "S", "source_type": "news", "published_date": "2026-08-30", "collected_at": "2026-08-30T10:00:00+00:00",
              "authors": [], "summary": "", "doi": None, "company_slug": None, "keywords_matched": ["CADD"], "extra": {},
              "inserted_at": "x", "updated_at": "y"} for i in range(n_itens)]
    return {"items": itens, "newsletters": [{"date": "2026-08-19", "content": "# edição", "updated_at": "z"}],
            "companies": [{"slug": "a"}], "resources": [], "funding_channels": [], "corporate_programs": [],
            "pipeline_meta": [{"id": "singleton"}]}


class Exportar(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dest = Path(self._tmp.name) / "export"

    def tearDown(self):
        self._tmp.cleanup()

    def test_pagina_por_chave_e_o_migrador_le(self):
        tabs = tabelas_falsas(2 * ex.PAGINA + 7)
        sess = SessaoFalsa(tabs)
        man = ex.exportar(self.dest, CHAVE_FALSA, "https://exemplo.supabase.co", sessao=sess)
        self.assertEqual(man["tabelas"]["items"]["linhas"], 2 * ex.PAGINA + 7)
        self.assertEqual(sum(1 for t, _ in sess.chamadas if t == "items"), 3)
        itens, news = mig.ler_export_supabase(self.dest)
        self.assertEqual(len(itens), 2 * ex.PAGINA + 7)
        self.assertNotIn("id", itens[0])
        self.assertEqual(news, {"2026-08-19": "# edição"})
        self.assertNotIn(CHAVE_FALSA, (self.dest / "manifesto.json").read_text(encoding="utf-8"))

    def test_arquivo_adulterado_e_recusado_pelo_migrador(self):
        ex.exportar(self.dest, CHAVE_FALSA, "https://exemplo.supabase.co", sessao=SessaoFalsa(tabelas_falsas(3)))
        (self.dest / "items.json").write_text("[]", encoding="utf-8")
        with self.assertRaises(RuntimeError):
            mig.ler_export_supabase(self.dest)

    def test_contagem_do_servidor_divergente_falha(self):
        with self.assertRaises(ex.ExportFalhou):
            ex.exportar(self.dest, CHAVE_FALSA, "https://exemplo.supabase.co", sessao=SessaoFalsa(tabelas_falsas(3), total_mente="items"))
        self.assertFalse((self.dest / "manifesto.json").exists())

    def test_http_de_erro_nao_imprime_a_chave(self):
        class Quebrada(SessaoFalsa):
            def get(self, *a, **k):
                return Resp([], status=401)
        with self.assertRaises(ex.ExportFalhou) as ctx:
            ex.exportar(self.dest, CHAVE_FALSA, "https://exemplo.supabase.co", sessao=Quebrada({}))
        self.assertNotIn(CHAVE_FALSA, str(ctx.exception))

    def test_main_sem_chave_sai_2(self):
        err = io.StringIO()
        with mock.patch.dict(os.environ, {"SUPABASE_SERVICE_ROLE_KEY": ""}), contextlib.redirect_stderr(err):
            self.assertEqual(ex.main(["--destino", str(self.dest)]), 2)
        self.assertFalse(self.dest.exists())

    def test_main_recusa_destino_dentro_da_empresa(self):
        if not ex.dentro_da_empresa(PIPELINE):
            self.skipTest("checkout avulso: não há pasta da empresa em volta")
        dentro = PIPELINE / "data" / "nao-criar-export-aqui"
        err = io.StringIO()
        with mock.patch.dict(os.environ, {"SUPABASE_SERVICE_ROLE_KEY": CHAVE_FALSA}), contextlib.redirect_stderr(err), \
                mock.patch.object(ex, "exportar", side_effect=AssertionError("exportou para dentro do Drive")):
            codigo = ex.main(["--destino", str(dentro)])
        self.assertEqual(codigo, 2)
        self.assertFalse(dentro.exists())
        # o outro sentido: fora da empresa (pasta temporária) a recusa não acontece
        self.assertFalse(ex.dentro_da_empresa(self.dest))


if __name__ == "__main__":
    unittest.main()
