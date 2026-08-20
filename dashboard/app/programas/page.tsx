import PageHeader from '@/components/PageHeader';
import CorporateProgramCard from '@/components/CorporateProgramCard';
import DocumentChecklist from '@/components/DocumentChecklist';
import OpportunityFilterBar from '@/components/OpportunityFilterBar';
import type { OpportunityFilterEntry } from '@/components/OpportunityFilterBar';
import { getCorporatePrograms } from '@/lib/data';
import { CORPORATE_CATEGORY_LABELS } from '@/lib/types';

export const dynamic = 'force-dynamic';

export default async function ProgramasPage() {
  const programs = await getCorporatePrograms();
  const recommended = programs.filter((p) => p.priority_alchemia === 'alta');

  const entries: OpportunityFilterEntry[] = programs.map((program) => ({
    slug: program.slug,
    category: program.category,
    priority: program.priority_alchemia,
    searchText: [program.name, program.benefit_summary, program.eligibility_summary, program.priority_note].join(' '),
    node: <CorporateProgramCard program={program} />,
  }));

  return (
    <div>
      <PageHeader
        title="Programas Corporativos"
        description="Créditos de nuvem, SaaS para startups, aceleradoras, parques tecnológicos e hubs de inovação. Catálogo curado, direcional — tetos de crédito e critérios de elegibilidade mudam por trimestre, confirmar sempre na página oficial antes de planejar orçamento em cima deles."
      />

      {programs.length === 0 ? (
        <p className="mb-8 text-sm text-slate-500">
          Catálogo ainda não carregado — verifique <code className="text-cyan-accent">pipeline/config/corporate_programs.yaml</code>.
        </p>
      ) : (
        <>
          {recommended.length > 0 ? (
            <div className="mb-10">
              <h2 className="mb-3 font-mono text-[12px] uppercase tracking-wide text-cyan-accent">
                ★ Recomendado para a Alchemia
              </h2>
              <p className="mb-3 text-[13px] text-slate-500">
                Reproduz — sem inventar nova prioridade — a priorização que o próprio guia já faz para
                o perfil de biotech/CADD/oncologia molecular da empresa (seção 10).
              </p>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                {recommended.map((program) => (
                  <CorporateProgramCard key={program.slug} program={program} />
                ))}
              </div>
            </div>
          ) : null}

          <div className="mb-10">
            <DocumentChecklist />
          </div>

          <h2 className="mb-3 font-mono text-[12px] uppercase tracking-wide text-slate-400">
            Todos os programas
          </h2>
          <OpportunityFilterBar entries={entries} categoryLabels={CORPORATE_CATEGORY_LABELS} categoryFieldLabel="Categoria" />
        </>
      )}
    </div>
  );
}
