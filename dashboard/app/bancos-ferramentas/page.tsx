import PageHeader from '@/components/PageHeader';
import { getArticles, getNews, getResources } from '@/lib/data';
import { RESOURCE_TYPE_LABELS } from '@/lib/types';

export const dynamic = 'force-dynamic';

export default function BancosFerramentasPage() {
  const resources = getResources();
  const allText = [...getArticles(), ...getNews()];

  const byType = resources.reduce<Record<string, typeof resources>>((acc, r) => {
    (acc[r.type] ??= []).push(r);
    return acc;
  }, {});

  function recentMentions(resourceName: string) {
    const needle = resourceName.toLowerCase();
    return allText.filter((item) => item.title.toLowerCase().includes(needle)).slice(0, 3);
  }

  return (
    <div>
      <PageHeader
        title="Bancos & Ferramentas"
        description="Diretório de referência dos bancos de moléculas e ferramentas de CADD acompanhados pela Alchemia — inclui as fontes já usadas no Alchemia Database/Athanor e o ecossistema mais amplo do nicho. Cada entrada é cruzada contra os artigos/notícias coletados para mostrar menções recentes."
      />

      {Object.entries(byType).map(([type, list]) => (
        <div key={type} className="mb-10">
          <h2 className="mb-3 font-mono text-[12px] uppercase tracking-wide text-slate-400">
            {RESOURCE_TYPE_LABELS[type] ?? type}
          </h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {list.map((resource) => {
              const mentions = recentMentions(resource.name);
              return (
                <div key={resource.slug} className="alchemia-card p-5">
                  <div className="mb-2 flex items-start justify-between gap-3">
                    <div>
                      <h3 className="font-medium text-slate-100">{resource.name}</h3>
                      <p className="font-mono text-[11px] text-slate-500">{resource.full_name}</p>
                    </div>
                    <a
                      href={resource.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="whitespace-nowrap rounded border border-cyan-accent/30 px-2 py-1 font-mono text-[11px] text-cyan-accent hover:bg-cyan-accent/10"
                    >
                      abrir ↗
                    </a>
                  </div>
                  <p className="mb-3 text-[13px] leading-relaxed text-slate-400">{resource.description}</p>
                  <p className="mb-3 font-mono text-[11px] text-status-start">📄 {resource.license_note}</p>
                  {mentions.length > 0 ? (
                    <div className="border-t border-white/5 pt-3">
                      <p className="mb-1.5 font-mono text-[10px] uppercase tracking-wide text-slate-500">
                        Menções recentes
                      </p>
                      {mentions.map((m) => (
                        <a
                          key={m.dedupe_key}
                          href={m.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="block truncate text-[12px] text-slate-400 hover:text-cyan-accent"
                        >
                          · {m.title}
                        </a>
                      ))}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
