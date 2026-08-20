import PageHeader from '@/components/PageHeader';
import { getPipelineMeta } from '@/lib/data';

export const dynamic = 'force-dynamic';

export default async function SobrePage() {
  const meta = await getPipelineMeta();

  return (
    <div>
      <PageHeader title="Sobre este painel" description="Como o Alchemia News funciona, de onde vêm os dados, e o que ele deliberadamente não cobre ainda." />

      <div className="space-y-6">
        <section className="alchemia-card p-5">
          <h2 className="mb-2 font-mono text-[13px] uppercase tracking-wide text-cyan-accent">O que é</h2>
          <p className="text-[14px] leading-relaxed text-slate-300">
            O Alchemia News nasceu como o radar de nicho do setor que o mantém e, a partir da Fase 2
            (2026-08-19), passou a ser uma ferramenta de uso da <strong className="text-slate-100">empresa
            inteira</strong> — reúne notícias e artigos científicos sobre Computer-Aided Drug Design
            (CADD), AI Drug Discovery e engenharia de proteínas/anticorpos/vacinas; canais de editais
            de fomento à pesquisa (federal, estadual, saúde, universidades, fundações privadas,
            internacional) e programas corporativos para startups (créditos de nuvem, SaaS,
            aceleradoras, parques tecnológicos, hubs de inovação); e a newsletter publicada pela
            rotina do Axel. O pipeline de coleta de notícias/artigos roda de forma autônoma 3x ao dia
            (manhã, tarde e noite); os catálogos de fomento e programas corporativos são curadoria
            estática, não coletada automaticamente — ver seção específica abaixo.
          </p>
        </section>

        <section className="alchemia-card p-5">
          <h2 className="mb-2 font-mono text-[13px] uppercase tracking-wide text-cyan-accent">
            Fomento e programas corporativos (Fomento / Programas)
          </h2>
          <p className="text-[14px] leading-relaxed text-slate-300">
            As páginas <strong className="text-slate-100">Fomento</strong> e{' '}
            <strong className="text-slate-100">Programas</strong> são catálogos curados, transcritos e
            resumidos em palavras próprias a partir de dois guias de referência compilados pelo
            fundador, não coletados automaticamente. A priorização "Recomendado para a Alchemia" em
            cada página reproduz — sem inventar nada novo — a priorização que os próprios guias já
            fazem para o perfil de biotech/CADD/oncologia molecular da empresa.
          </p>
          <p className="mt-2 font-mono text-[12px] text-status-start">
            ⚠ Direcional — confirmar sempre na fonte/portal oficial. Valores, tetos de crédito,
            critérios de elegibilidade e prazos mudam por edição/trimestre e podem estar desatualizados
            em relação ao momento em que você está lendo.
          </p>
        </section>

        <section className="alchemia-card p-5">
          <h2 className="mb-2 font-mono text-[13px] uppercase tracking-wide text-cyan-accent">Fontes cobertas</h2>
          <ul className="space-y-1.5 text-[14px] text-slate-300">
            <li>
              <strong className="text-slate-100">Artigos e preprints:</strong> PubMed (NCBI E-utils), bioRxiv,
              arXiv (categorias q-bio), ChemRxiv e SciELO Brasil.
            </li>
            <li>
              <strong className="text-slate-100">Notícias:</strong> Google News (queries em inglês e português),
              feeds de periódicos temáticos (Nature Reviews Drug Discovery).
            </li>
            <li>
              <strong className="text-slate-100">Empresas:</strong> feeds RSS oficiais quando existem
              (OpenAI, NVIDIA, BioSolveIt, Fiocruz), com fallback via Google News quando a empresa não
              expõe um feed público estável.
            </li>
          </ul>
        </section>

        <section className="alchemia-card p-5">
          <h2 className="mb-2 font-mono text-[13px] uppercase tracking-wide text-status-risk">O que este painel NÃO faz (ainda)</h2>
          <ul className="space-y-1.5 text-[14px] text-slate-300">
            <li>
              <strong className="text-slate-100">Redes sociais</strong> (LinkedIn, X/Twitter, Instagram) das
              empresas de referência — decisão explícita de escopo desta primeira versão, feita com o
              fundador. Fica para uma rodada futura dedicada, usando as contas oficiais da Alchemia.
            </li>
            <li>
              <strong className="text-slate-100">Não é exaustivo.</strong> Um agregador automatizado nunca
              captura 100% do que é publicado — trate como um radar de alto sinal, não como cobertura total.
            </li>
            <li>
              <strong className="text-slate-100">ChemRxiv e SciELO</strong> bloqueiam acesso direto (HTTP 403)
              desta rede — os dois são cobertos via o índice público do Crossref (que indexa os DOIs de
              ambos), não pela API/site oficial diretamente.
            </li>
            <li>
              <strong className="text-slate-100">Checklist de documentos e status de candidatura</strong>{' '}
              (páginas Fomento/Programas) são salvos em <code>localStorage</code>, só neste navegador —
              não é multiusuário nem sincronizado entre pessoas/máquinas nesta fase (Fase 1).
            </li>
            <li>
              <strong className="text-slate-100">Newsletter</strong> é somente leitura aqui — quem publica
              é a rotina do Axel (setor <code>alchemia-bots</code>); se nenhuma edição existir ainda, a
              página mostra um estado vazio em vez de quebrar.
            </li>
          </ul>
        </section>

        {meta ? (
          <section className="alchemia-card p-5">
            <h2 className="mb-2 font-mono text-[13px] uppercase tracking-wide text-cyan-accent">Última execução do pipeline</h2>
            <p className="font-mono text-[12px] text-slate-400">
              Iniciada: {new Date(meta.last_run_started).toLocaleString('pt-BR')}
              <br />
              Concluída: {new Date(meta.last_run_finished).toLocaleString('pt-BR')}
              <br />
              Duração: {meta.duration_seconds}s
            </p>
          </section>
        ) : null}
      </div>
    </div>
  );
}
