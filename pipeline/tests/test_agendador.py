"""O agendador do contêiner `radar`: o próximo horário em UTC e a recusa de horário inválido. Sem rede, sem banco."""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

PIPELINE = Path(__file__).resolve().parents[1]
if str(PIPELINE) not in sys.path:
    sys.path.insert(0, str(PIPELINE))

import agendador as ag  # noqa: E402

H = ag.ler_horarios(ag.PADRAO_UTC)


def utc(h: int, m: int, s: int = 0, dia: int = 2) -> datetime:
    return datetime(2026, 10, dia, h, m, s, tzinfo=timezone.utc)


class ProximoHorario(unittest.TestCase):
    def test_padrao_e_o_do_coleta_yml(self):
        self.assertEqual(H, [(9, 40), (15, 40), (21, 40)])

    def test_antes_do_primeiro(self):
        self.assertEqual(ag.proximo_horario(utc(3, 0), H), utc(9, 40))

    def test_entre_dois(self):
        self.assertEqual(ag.proximo_horario(utc(12, 0), H), utc(15, 40))

    def test_no_minuto_exato_vai_para_o_seguinte(self):
        # quem acorda às 09:40:00,1 já está atrasado para as 09:40: nunca dispara duas vezes o mesmo horário
        self.assertEqual(ag.proximo_horario(utc(9, 40, 0) + timedelta(microseconds=100), H), utc(15, 40))

    def test_depois_do_ultimo_vai_para_amanha(self):
        self.assertEqual(ag.proximo_horario(utc(22, 0), H), utc(9, 40, dia=3))

    def test_relogio_com_outro_fuso_e_convertido(self):
        brasilia = timezone(timedelta(hours=-3))
        self.assertEqual(ag.proximo_horario(datetime(2026, 10, 2, 6, 39, tzinfo=brasilia), H), utc(9, 40))

    def test_sombra_deslocada_vinte_minutos(self):
        self.assertEqual(ag.ler_horarios("22:00, 10:00,16:00"), [(10, 0), (16, 0), (22, 0)])


class HorarioInvalido(unittest.TestCase):
    def test_recusa(self):
        for ruim in ("", "9h40", "24:00", "09:60", "09:40,xx"):
            with self.subTest(ruim=ruim), self.assertRaises(ValueError):
                ag.ler_horarios(ruim)


if __name__ == "__main__":
    unittest.main()
