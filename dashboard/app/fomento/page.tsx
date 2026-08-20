import PageHeader from '@/components/PageHeader';
import FundingChannelCard from '@/components/FundingChannelCard';
import DocumentChecklist from '@/components/DocumentChecklist';
import OpportunityFilterBar from '@/components/OpportunityFilterBar';
import type { OpportunityFilterEntry } from '@/components/OpportunityFilterBar';
import { getFundingChannels } from '@/lib/data';
import { FUNDING_SCOPE_LABELS } from '@/lib/types';

export const dynamic = 'force-dynamic';

export default async function FomentoPage() {
  const channels = await getFundingChannels();
  const recommended = channels.filter((c) => c.priority_alchemia === 'alta');

  const entries: OpportunityFilterEntry[] = channels.map((channel) => ({
    slug: channel.slug,
    category: channel.scope,
    priority: channel.priority_alchemia,
    searchText: [
      channel.name,
      channel.full_name,
      channel.priority_note,
      ...(channel.programs?.map((p) => `${p.name} ${p.note}`) ?? []),
    ].join(' '),
    node: <FundingChannelCard channel={channel} />,
  }));

  return (
    <div>
      <PageHeader
        title="Fomento"
        description="Canais de editais de fomento à pesquisa, inovação e startups — federal, estadual (SP), universidades/ICTs, saúde, fundações privadas e internacional. Catálogo curado, direcional — confirmar sempre no portal/PDF oficial antes de qualquer decisão de submissão."
      />

      {channels.length === 0 ? (
        <p className="mb-8 text-sm text-slate-500">
          Catálogo ainda não carregado — verifique <code className="text-cyan-accent">pipeline/config/funding_channels.yaml</code>.
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
                o perfil de biotech/CADD/oncologia molecular da empresa (seção 9).
              </p>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                {recommended.map((channel) => (
                  <FundingChannelCard key={channel.slug} channel={channel} />
                ))}
              </div>
            </div>
          ) : null}

          <div className="mb-10">
            <DocumentChecklist />
          </div>

          <h2 className="mb-3 font-mono text-[12px] uppercase tracking-wide text-slate-400">
            Todos os canais
          </h2>
          <OpportunityFilterBar entries={entries} categoryLabels={FUNDING_SCOPE_LABELS} categoryFieldLabel="Escopo" />
        </>
      )}
    </div>
  );
}
