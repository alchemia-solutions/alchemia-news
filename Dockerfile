# A imagem do contêiner `radar` na VM (spec docs/specs/2026-10-02-radar-na-vm-postgres.md, "O serviço"; roteiro em
# deploy/README.md). Construída NA VM (aarch64), com a etiqueta igual ao sha do commit do Radar:
#
#   export RADAR_RELEASE=$(git -C /home/ubuntu/alchemia-radar rev-parse --short=12 HEAD)
#   docker build -t alchemia-radar:$RADAR_RELEASE --build-arg RADAR_VERSAO=$RADAR_RELEASE /home/ubuntu/alchemia-radar
#
# Só o pipeline entra: nada de pipeline/data/ (o acervo vive no banco), do dashboard/ congelado, do supabase/ nem de
# segredo (.dockerignore). A única credencial, DATABASE_URL_RADAR, chega pelo ambiente do Compose, nunca pela imagem.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY pipeline/requirements.txt pipeline/requirements-pg.txt /app/pipeline/
RUN pip install -r /app/pipeline/requirements-pg.txt

COPY pipeline/ /app/pipeline/
# bytecode compilado no build: o contêiner roda com o sistema de arquivos só-leitura e não grava __pycache__
RUN python -m compileall -q /app/pipeline \
 && useradd --uid 10001 --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin radar

ARG RADAR_VERSAO=sem-versao
# RADAR_DESTINO=postgres: dentro da imagem, a coleta nunca grava JSON; RADAR_LOG_JSON=1: uma linha JSON por evento
ENV RADAR_VERSAO=${RADAR_VERSAO} \
    RADAR_DESTINO=postgres \
    RADAR_LOG_JSON=1

USER 10001
# o agendador dorme até o próximo horário de RADAR_HORARIOS_UTC e roda `python -m pipeline.run_all` num processo filho.
# Disparo à mão: docker compose ... run --rm radar python -m pipeline.run_all
CMD ["python", "-m", "pipeline.agendador"]
