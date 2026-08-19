# `pipeline/data/discord/` — o que o Axel publicou, verbatim

Um arquivo por publicação, nomeado `AAAA-MM-DD-HHMM.md`, contendo **cópia literal** da mensagem
que a rotina `alchemia-news-anuncio-discord` (o Axel) postou no canal `#news`.

**Por que este diretório existe.** O radar do dia
(`alchemia-science/research/AAAA-MM-DD-alchemia-news-radar.md`) é um arquivo **derivado**: o
`pipeline/research_export.py` o reescreve por inteiro a cada execução. Se o Axel escrevesse
direto nele, a próxima geração apagaria o registro. Escrevendo aqui, o `research_export` lê o
diretório e monta a seção *"Publicado no Discord"* do dia — o registro sobrevive a quantas
regenerações forem.

Com isso o radar fecha o ciclo inteiro do dia: **o que foi coletado** (pipeline determinístico),
**o que virou texto completo** na `alchemia-library` (só open access confirmado), e **o que a
comunidade efetivamente viu**.

Quem escreve: só o Passo 5 da rotina do Axel, e só depois de a publicação ter retornado exit 0.
Quem lê: `pipeline/research_export.py`.

Criado em 2026-08-18, junto da integração `alchemia-news` → `alchemia-science`/`alchemia-library`.
Ver `alchemia-ai/alchemia-news/docs/specs/2026-08-18-research-library-integration.md`.
