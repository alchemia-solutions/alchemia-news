import PageHeader from '@/components/PageHeader';
import { getPipelineMeta } from '@/lib/data';

export const dynamic = 'force-dynamic';

export default function SobrePage() {
  const meta = getPipelineMeta();

  return (
    <div>
      <PageHeader title="Sobre este painel" description="Como o Alchemia News funciona, de onde vêm os dados, e o que ele deliberadamente não cobre ainda." />

      <div className="space-y-6">
        <section className="alchemia-card p-5">
          <h2 className="mb-2 font-mono text-[13px] uppercase tracking-wide text-cyan-accent">O que é</h2>
          <p className="text-[14px] leading-relaxed text-slate-300">
            O Alchemia News é o painel interno de inteligência de mercado da Alchemia Solutions —
            reúne notícias e artigos científicos publicados sobre Computer-Aided Drug Design (CADD),
            AI Drug Discovery, engenharia de proteínas/anticorpos/vacinas e o nicho de empresas que
            investem nessa interseção entre IA e biologia/química. O pipeline de coleta roda de forma
            autônoma 3x ao dia (manhã, tarde e noite).
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
