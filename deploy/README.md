# O Radar na VM: roteiro de deploy

Para o Gabriel Furniel (Tech) e o fundador. Spec: [`docs/specs/2026-10-02-radar-na-vm-postgres.md`](../docs/specs/2026-10-02-radar-na-vm-postgres.md)
(aprovada, decisions-log (ee)). Estado em 2026-10-02: o código do Radar está pronto e testado na estação contra um
Postgres descartável; **nada disto rodou na VM**, e o GitHub Actions segue como escritor único de `pipeline/data/`
até a virada (R6).

## O que é

O contêiner `radar` roda no Compose do System (`alchemia-system/compose.yaml`, serviço `radar`, atrás do perfil
`radar`). A imagem sai do [`Dockerfile`](../Dockerfile) deste repositório (`python:3.12-slim`, usuário 10001, sem
`pipeline/data/`). O processo é `python -m pipeline.agendador`: dorme até o próximo horário de `RADAR_HORARIOS_UTC`
(padrão `09:40,15:40,21:40`, em UTC) e roda `python -m pipeline.run_all --destino postgres --origem agendada` num
processo filho, que grava no esquema `radar` do banco do System com o papel `alchemia_radar`.

Cada coleta:

1. toma a trava consultiva do Postgres (outra coleta em curso: sai 0 com `radar.execucao.ocupado`);
2. confere as colunas de `radar.*` contra o que o código grava (divergência: sai 1 com a diferença no log);
3. abre a linha em `radar.execucao` com `estado = 'rodando'` e roda os coletores;
4. numa transação: upsert dos itens (só preenche campo vazio), dos quatro catálogos YAML e o fechamento da execução
   (`ok`, `parcial` se alguma fonte falhou, `falhou` se todas falharam).

O System lê ao vivo (`radar.item`, a view `radar.meta`, `radar.catalogo`, `radar.newsletter`): a execução aparece
inteira no pedido seguinte ao commit.

## Pré-requisitos (do System e da Tech)

| O quê | Onde | Como conferir |
|---|---|---|
| A migração `0024_radar` aplicada | System, serviço `migrar` | `select table_name, table_type from information_schema.tables where table_schema = 'radar'` lista 4 `BASE TABLE` e a `VIEW` `meta` |
| O papel `alchemia_radar` com as concessões da spec | `packages/core/sql/papeis.sql`, gerado pelo `papeis.ts` do System | `\dp radar.*` no `psql`: `alchemia_radar` com `arw` em `item`, `execucao` e `newsletter`, `arwd` em `catalogo` |
| A senha do papel | o `producao.env` do System, na VM e fora do git: `PG_SENHA_RADAR`, só os caracteres que a URL aceita, como as outras senhas | o serviço `papeis` roda o `ALTER ROLE ... PASSWORD` só quando a variável existe |
| O clone do Radar | `/home/ubuntu/alchemia-radar`, `git clone https://github.com/alchemia-solutions/alchemia-radar` (público; atualizado só por `git pull`) | `git -C /home/ubuntu/alchemia-radar log -1 --format=%h` |
| Backup do banco com restauração testada | Tech (critério 15) | **antes** de o Actions parar: hoje o git é o único histórico do Radar |

Nenhum segredo entra no contêiner além da URL do banco. O serviço `radar` **não** usa `env_file:`: o `producao.env`
tem as senhas de todos os papéis.

## Roteiro

Todos os comandos da VM rodam em `/home/ubuntu/alchemia-system`, com `--env-file deploy/producao.env`.

### R0. Preparo (fundador e Tech)

- **Export do Supabase (fundador, com a credencial dele; nenhum agente roda).** Na estação, na raiz deste
  repositório, em PowerShell:

  ```powershell
  $env:SUPABASE_SERVICE_ROLE_KEY = "<cole aqui; nunca num arquivo>"
  pipeline\.venv\Scripts\python.exe -m pipeline.exportar_supabase --destino C:\Users\AryelBezerra\alchemia-workdata\radar-supabase-export
  Remove-Item Env:SUPABASE_SERVICE_ROLE_KEY
  ```

  Grava um JSON por tabela (sete) e um `manifesto.json` com a contagem de linhas e o sha256 de cada arquivo. A
  contagem do manifesto é a que o critério 14 pede registrar antes de desligar o projeto. O script só lê, recusa um
  destino dentro da pasta da empresa (o export leva nomes de autores: fora do Drive, apagar depois da conferência) e
  recusa terminar se a contagem do servidor não bater (rode longe de 09:40, 15:40 e 21:40 UTC, quando o Actions grava).
- **Backup** agendado do banco e uma restauração testada (Tech).
- Conferir na VM se o `rclone` corta `articles.json` (spec, "O que o System lê hoje", hipótese 2):
  `grep -n "max-size\|delete-excluded" ~/sync-vault.sh`.

### R2. A imagem

```bash
cd /home/ubuntu/alchemia-radar && git pull --ff-only
export RADAR_RELEASE=$(git -C /home/ubuntu/alchemia-radar rev-parse --short=12 HEAD)
docker build -t alchemia-radar:$RADAR_RELEASE --build-arg RADAR_VERSAO=$RADAR_RELEASE /home/ubuntu/alchemia-radar
docker run --rm alchemia-radar:$RADAR_RELEASE python -m pipeline.agendador --proximos 3   # os próximos três disparos, em UTC
```

O `compose-build.yaml` do System ainda não tem o serviço `radar` (conferido em 2026-10-02); até ter, construa pelo
`docker build` acima. A wheel do `psycopg[binary]` para aarch64 se confirma neste passo (spec, lente 3).

### R3. A carga do acervo

A carga tem duas metades, porque o histórico do git mora na estação e o banco só na rede interna da VM.

1. **Na estação**, com o checkout do Radar em dia (`git fetch`):

   ```bash
   pipeline/.venv/Scripts/python.exe -m pipeline.migrar_para_postgres --dry-run
   pipeline/.venv/Scripts/python.exe -m pipeline.migrar_para_postgres \
     --salvar-pacote /c/Users/AryelBezerra/alchemia-workdata/radar-carga.json.gz \
     [--supabase /c/Users/AryelBezerra/alchemia-workdata/radar-supabase-export]
   ```

   O `--dry-run` imprime, por origem (JSON do `origin/main`, histórico do git, export do Supabase), quantas chaves há
   e quantas são novas na união, as versões que não parseiam (o merge `d5eb59a` de 2026-09-07) e a conferência de
   2026-09-07. O evento `radar.carga.pacote` traz o sha256 do arquivo.
2. **Copiar** o pacote para a VM (`scp`) numa pasta fora do vault, por exemplo `/home/ubuntu/radar-carga/`, e conferir
   o sha256 (`sha256sum`).
3. **Na VM**, com a imagem do R2:

   ```bash
   docker compose --env-file deploy/producao.env --profile radar run --rm \
     -v /home/ubuntu/radar-carga:/carga:ro radar \
     python -m pipeline.migrar_para_postgres --pacote /carga/radar-carga.json.gz --dry-run
   docker compose --env-file deploy/producao.env --profile radar run --rm \
     -v /home/ubuntu/radar-carga:/carga:ro radar \
     python -m pipeline.migrar_para_postgres --pacote /carga/radar-carga.json.gz
   ```

   O evento `radar.carga.fim` traz as contagens antes e depois, `chaves_da_carga_no_banco` (igual ao total da carga) e
   `recuperadas` por commit de 2026-09-07. Saída 1 com `radar.carga.divergente` se alguma conferência falhar. Rodar de
   novo é seguro: a segunda carga dá 0 inserções e 0 atualizações.

### R4. A sombra (7 dias, critério 8)

O Actions continua gravando o git; a VM grava o banco, 20 minutos depois, para não somar as rajadas nas fontes:

```bash
# deploy/producao.env:  RADAR_HORARIOS_UTC=10:00,16:00,22:00
docker compose --env-file deploy/producao.env --profile radar run --rm radar python -m pipeline.run_all   # um ciclo à mão
docker compose --env-file deploy/producao.env --profile radar up -d --no-build radar
docker compose --env-file deploy/producao.env logs -f radar
```

O log é uma linha JSON por evento: `radar.agendador.espera` (o próximo disparo), `radar.execucao.inicio`,
`radar.coletor` (um por coletor: `count`, `segundos`, `erro`), `radar.execucao.fim` ou `.parcial` (com os totais),
`radar.execucao.ocupado`, `radar.execucao.falhou` (com o motivo; a URL do banco nunca aparece) e `radar.log` (as
mensagens dos coletores). Durante a sombra, meça a cada execução `docker stats --no-stream` (CPU e memória na VM não
foram medidas).

A primeira coleta depois da carga conta como `atualizados` os itens que ela reencontra, porque o acervo importado tem
`coletores` vazio e a coleta preenche (medido na estação em 2026-10-02, uma coleta real sobre a carga: 30 novos e
1.774 atualizados, de 1.966 itens colhidos antes da fusão por chave). Da
segunda em diante, `atualizados` volta a ser só mudança de campo.

Rollback da imagem: `RADAR_RELEASE=<sha anterior> docker compose --env-file deploy/producao.env --profile radar up -d --no-build radar`.

### R6. A virada (fundador, Tech e Radar)

Só depois do backup testado e da sombra aprovada. Nada disto foi feito; está preparado:

| O que sai | Quem | Como |
|---|---|---|
| `.github/workflows/coleta.yml` e `research-export.yml` | fundador (push) | apagar os dois arquivos, ou trocar o `on:` por só `workflow_dispatch: {}`. Renomear um exige renomear o outro (o gatilho `workflow_run` casa pelo `name:`) |
| A carga final | Radar | depois do último commit `coleta automática`, gerar e carregar um pacote novo do `origin/main` (R3): idempotente, só entra o item que o Actions colheu e a VM não. Os snapshots de execução do Actions não entram mais (`execucoes_puladas_por_haver_coleta_da_vm`): a view `radar.meta` escolhe pelo maior id, e um snapshot importado depois tomaria o lugar da última coleta real |
| `pipeline/data/` no repositório público (D5) | fundador | congelar com um `README.md` datado, por exemplo: "Parou em AAAA-MM-DD. O dado do Radar vive no banco do System (`system-prod`, esquema `radar`); estes arquivos são o arquivo histórico até aquela data." |
| `pipeline/sync_supabase.py`, `supabase/`, o MCP `supabase` do `.mcp.json` | fundador decide (D5) | Lixeira (`harness/lixeira.py`) ou ficam como registro |
| O projeto Supabase e o segredo `SUPABASE_SERVICE_ROLE_KEY` do Actions; `dashboard/.env.local` (risk-log 15) | fundador | depois do export do R0 e da contagem registrada |
| O clone `~/alchemia-news` na VM (nome antigo) | Tech | remover depois da virada |
| `research_export.py` (Etapa 1b, D6) | — | suspenso: lê os JSON, e uma spec de Science o aponta para o banco |
| `AGENTS.md`, `README.md`, a skill `news-intelligence-pipeline`, o nó e o hub no vault | Radar | o escritor único passa a ser o contêiner `radar` |

## Conferir sem a VM

```bash
# um Postgres descartável no WSL, numa porta própria
ALC_PG_PORTA=55431 bash ../alchemia-system/scripts/dev/pg-descartavel.sh up       # imprime a URL do superusuário
PG_DESCARTAVEL_URL=<a URL> pipeline/.venv/Scripts/python.exe -m unittest discover -s pipeline/tests -v
ALC_PG_PORTA=55431 bash ../alchemia-system/scripts/dev/pg-descartavel.sh down
```

Os testes montam o banco como produção (o `papeis.sql` do System, as migrações do System até a `0024_radar`, o
`papeis.sql` de novo) e cobrem: upsert idempotente e só-preenche-vazio, coleta duas vezes sem rede, trava, fonte fora
do ar, banco fora do ar, contrato divergente, execução órfã, catálogos, o papel mínimo nos dois sentidos e a carga real
do acervo, duas vezes.
