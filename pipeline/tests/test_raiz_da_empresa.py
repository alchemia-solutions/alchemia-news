"""Teste da busca por marcador de `research_export.achar_raiz_da_empresa` (criado em 2026-09-28).

Sem rede, sem pytest (o venv do pipeline não o tem) e sem escrever fora de um diretório
temporário: nunca em `pipeline/data/`, nunca em `alchemia-science/`. Da raiz do repositório:

    pipeline/.venv/Scripts/python.exe -m unittest pipeline.tests.test_raiz_da_empresa -v

Testa a regra nos dois sentidos. Acha a raiz nas árvores que existem (a nova, a antiga e a do
runner do Actions, que é a mesma forma sob o workspace) e devolve None quando o marcador falta,
inclusive quando o único `alchemia-science/` está DENTRO do repositório.

A última classe confere a árvore real onde este arquivo está: exige que um ancestral do checkout
tenha `alchemia-science/`. Na estação isso vale; num checkout avulso do Radar, sem a empresa em
volta, ela falha de propósito, porque ali o `research_export` também não teria para onde escrever.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
import uuid
from pathlib import Path

RAIZ_DO_REPO = Path(__file__).resolve().parents[2]
if str(RAIZ_DO_REPO) not in sys.path:
    sys.path.insert(0, str(RAIZ_DO_REPO))

from pipeline import research_export as rx  # noqa: E402


class AcharRaizDaEmpresa(unittest.TestCase):
    """Árvores montadas num diretório temporário, com um marcador de nome único."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name).resolve()
        # Nome único por teste: nenhum ancestral do diretório temporário pode ter uma pasta com
        # esse nome, então o resultado depende só da árvore montada aqui (estação ou runner).
        self.marcador = f"marcador-{uuid.uuid4().hex}"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _repo(self, *partes: str) -> Path:
        repo = self.base.joinpath(*partes)
        (repo / "pipeline").mkdir(parents=True)
        return repo

    def test_arvore_nova(self) -> None:
        repo = self._repo("empresa", "alchemia-ai", "softwares", "internos", "alchemia-radar")
        (self.base / "empresa" / self.marcador).mkdir()
        self.assertEqual(rx.achar_raiz_da_empresa(repo, self.marcador), self.base / "empresa")

    def test_arvore_antiga(self) -> None:
        repo = self._repo("empresa", "alchemia-ai", "alchemia-news")
        (self.base / "empresa" / self.marcador).mkdir()
        self.assertEqual(rx.achar_raiz_da_empresa(repo, self.marcador), self.base / "empresa")

    def test_contraprova_da_aritmetica_antiga(self) -> None:
        # O defeito de 2026-09-28: na árvore nova, dois `.parent` caem em `alchemia-ai/softwares`.
        repo = self._repo("empresa", "alchemia-ai", "softwares", "internos", "alchemia-radar")
        (self.base / "empresa" / self.marcador).mkdir()
        self.assertFalse((repo.parent.parent / self.marcador).is_dir())
        self.assertEqual(rx.achar_raiz_da_empresa(repo, self.marcador), self.base / "empresa")

    def test_sem_marcador_devolve_none(self) -> None:
        repo = self._repo("empresa", "alchemia-ai", "softwares", "internos", "alchemia-radar")
        self.assertIsNone(rx.achar_raiz_da_empresa(repo, self.marcador))

    def test_marcador_dentro_do_repositorio_nao_conta(self) -> None:
        repo = self._repo("empresa", "alchemia-ai", "softwares", "internos", "alchemia-radar")
        (repo / self.marcador).mkdir()
        self.assertIsNone(rx.achar_raiz_da_empresa(repo, self.marcador))

    def test_arquivo_com_o_nome_do_marcador_nao_conta(self) -> None:
        repo = self._repo("empresa", "alchemia-ai", "softwares", "internos", "alchemia-radar")
        (self.base / "empresa" / self.marcador).write_text("arquivo, nao pasta", encoding="utf-8")
        self.assertIsNone(rx.achar_raiz_da_empresa(repo, self.marcador))

    def test_para_no_ancestral_mais_proximo(self) -> None:
        repo = self._repo("fora", "empresa", "alchemia-ai", "softwares", "internos", "alchemia-radar")
        (self.base / "fora" / self.marcador).mkdir()
        (self.base / "fora" / "empresa" / self.marcador).mkdir()
        self.assertEqual(
            rx.achar_raiz_da_empresa(repo, self.marcador), self.base / "fora" / "empresa"
        )


class ResolucaoNaArvoreReal(unittest.TestCase):
    """O módulo, importado de onde está, resolve para uma raiz que tem `alchemia-science/`."""

    def test_raiz_resolvida_contem_o_marcador_real(self) -> None:
        self.assertIsNotNone(rx._RAIZ_ACHADA, "nenhum ancestral deste checkout tem alchemia-science/")
        self.assertTrue(rx.SCIENCE_ROOT.is_dir())
        self.assertEqual(rx.SCIENCE_ROOT.name, "alchemia-science")
        self.assertIn(rx.COMPANY_ROOT, rx.RADAR_ROOT.parents)


if __name__ == "__main__":
    unittest.main(verbosity=2)
