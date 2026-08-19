import PageHeader from '@/components/PageHeader';
import ItemCard from '@/components/ItemCard';
import { getArticles } from '@/lib/data';
import { SOURCE_TYPE_LABELS } from '@/lib/types';

export const dynamic = 'force-dynamic';

export default function ArtigosPage({
  searchParams,
}: {
  searchParams: { fonte?: string };
}) {
  const all = getArticles();
  const fonteFiltro = searchParams.fonte;
  const filtered = fonteFiltro ? all.filter((i) => i.source === fonteFiltro) : all;

  const sourceCounts = Object.entries(
    all.reduce<Record<string, number>>((acc, i) => {
      acc[i.source] = (acc[i.source] ?? 0) + 1;
      return acc;
    }, {})
  ).sort((a, b) => b[1] - a[1]);

  return (
    <div>
      <PageHeader
        title="Artigos & Papers"
        description="Artigos publicados e preprints dos últimos ~6 meses no nicho de Computer-Aided Drug Design e AI Drug Discovery — PubMed, bioRxiv, arXiv, ChemRxiv e SciELO (os dois últimos via índice Crossref, já que o acesso direto a esses dois é bloqueado nesta rede)."
      />

      <div className="mb-6 flex flex-wrap gap-2">
        <a
          href="/artigos"
          className={`rounded-full border px-3 py-1 font-mono text-[11px] ${
            !fonteFiltro ? 'border-cyan-accent bg-cyan-accent/10 text-cyan-accent' : 'border-white/10 text-slate-400 hover:border-white/30'
          }`}
        >
          Todas ({all.length})
        </a>
        {sourceCounts.map(([source, count]) => (
          <a
            key={source}
            href={`/artigos?fonte=${encodeURIComponent(source)}`}
            className={`rounded-full border px-3 py-1 font-mono text-[11px] ${
              fonteFiltro === source
                ? 'border-cyan-accent bg-cyan-accent/10 text-cyan-accent'
                : 'border-white/10 text-slate-400 hover:border-white/30'
            }`}
          >
            {source} ({count})
          </a>
        ))}
      </div>

      <div className="mb-4 flex gap-4 font-mono text-[11px] text-slate-500">
        {Object.entries(SOURCE_TYPE_LABELS).map(([key, label]) => (
          <span key={key}>{label}</span>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((item) => (
          <ItemCard key={item.dedupe_key} item={item} />
        ))}
      </div>
      {filtered.length === 0 ? <p className="text-sm text-slate-500">Nenhum artigo encontrado para este filtro.</p> : null}
    </div>
  );
}
