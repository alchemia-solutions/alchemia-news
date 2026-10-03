#!/usr/bin/env python
"""O agendador do contêiner `radar` na VM (spec docs/specs/2026-10-02-radar-na-vm-postgres.md, "O serviço").

Dorme até o próximo horário de RADAR_HORARIOS_UTC, roda uma coleta num processo filho
(`python -m pipeline.run_all --destino postgres --origem agendada`) e volta a dormir. Sem cron do host e sem
dependência nova. Os horários ficam em UTC para a imagem slim não depender de `tzdata` (o Brasil não tem horário
de verão desde 2019): o padrão 09:40, 15:40 e 21:40 UTC são os 06:40, 12:40 e 18:40 de Brasília, os mesmos do
`coleta.yml`.

A coleta roda num processo filho para que memória e estado de módulo de uma execução nunca passem para a
seguinte, e para que uma exceção dela não derrube o agendador. Horário perdido (contêiner fora do ar na hora)
não é recuperado: a próxima coleta é a do próximo horário. A sobreposição é impossível de qualquer forma,
porque a própria coleta toma a trava consultiva do Postgres.

    python -m pipeline.agendador                 # o CMD da imagem
    python -m pipeline.agendador --proximos 3    # só mostra os três próximos disparos e sai
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone

PADRAO_UTC = "09:40,15:40,21:40"


def ler_horarios(texto: str) -> list[tuple[int, int]]:
    """`HH:MM` separados por vírgula, em UTC. Inválido levanta ValueError com o trecho ruim (o contêiner não sobe)."""
    out = set()
    for parte in (texto or "").split(","):
        parte = parte.strip()
        if not parte:
            continue
        try:
            h, m = parte.split(":")
            hh, mm = int(h), int(m)
        except ValueError:
            raise ValueError(f"RADAR_HORARIOS_UTC: {parte!r} não é HH:MM") from None
        if not (0 <= hh < 24 and 0 <= mm < 60):
            raise ValueError(f"RADAR_HORARIOS_UTC: {parte!r} fora de 00:00..23:59")
        out.add((hh, mm))
    if not out:
        raise ValueError("RADAR_HORARIOS_UTC vazio")
    return sorted(out)


def proximo_horario(agora: datetime, horarios: list[tuple[int, int]]) -> datetime:
    """O primeiro horário estritamente depois de `agora` (UTC), hoje ou amanhã."""
    agora = agora.astimezone(timezone.utc)
    for dia in (0, 1):
        base = (agora + timedelta(days=dia)).replace(second=0, microsecond=0)
        for hh, mm in horarios:
            alvo = base.replace(hour=hh, minute=mm)
            if alvo > agora:
                return alvo
    raise AssertionError("inalcançável: sempre há um horário em até 24 h")


def _evento(nome: str, **campos) -> None:
    linha = {"evento": nome, "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), **campos}
    print(json.dumps(linha, ensure_ascii=False), flush=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Agendador da coleta do Radar (contêiner da VM)")
    ap.add_argument("--proximos", type=int, default=0, help="Só imprime os N próximos disparos e sai")
    args = ap.parse_args(argv)

    horarios = ler_horarios(os.environ.get("RADAR_HORARIOS_UTC") or PADRAO_UTC)
    if args.proximos:
        t = datetime.now(timezone.utc)
        for _ in range(args.proximos):
            t = proximo_horario(t, horarios)
            print(t.isoformat())
        return 0

    parar = threading.Event()
    filho: dict[str, subprocess.Popen | None] = {"p": None}

    def ao_sinal(signum, _frame):  # o Docker manda SIGTERM ao PID 1 no `stop`
        parar.set()
        p = filho["p"]
        if p is not None and p.poll() is None:
            p.send_signal(signum)

    signal.signal(signal.SIGTERM, ao_sinal)
    signal.signal(signal.SIGINT, ao_sinal)

    _evento("radar.agendador.inicio", horarios_utc=[f"{h:02d}:{m:02d}" for h, m in horarios])
    while not parar.is_set():
        alvo = proximo_horario(datetime.now(timezone.utc), horarios)
        _evento("radar.agendador.espera", proximo=alvo.isoformat())
        while not parar.is_set():
            falta = (alvo - datetime.now(timezone.utc)).total_seconds()
            if falta <= 0:
                break
            parar.wait(min(falta, 60))
        if parar.is_set():
            break
        cmd = [sys.executable, "-m", "pipeline.run_all", "--destino", "postgres", "--origem", "agendada"]
        filho["p"] = subprocess.Popen(cmd)
        codigo = filho["p"].wait()
        filho["p"] = None
        _evento("radar.agendador.coleta", saida=codigo)
    _evento("radar.agendador.fim")
    return 0


if __name__ == "__main__":
    sys.exit(main())
