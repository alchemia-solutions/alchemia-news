import Link from 'next/link';
import LiveClock from '@/components/LiveClock';
import StatCard from '@/components/StatCard';
import ItemCard from '@/components/ItemCard';
import { getArticles, getCompanies, getCompaniesActivity, getNews, getPipelineMeta } from '@/lib/data';

export const dynamic = 'force-dynamic'; // sempre lê o JSON mais recente do pipeline, nunca cacheia estático

export default async function HomePage() {
  const meta = getPipelineMeta();
  const [news, articles] = await Promise.all([getNews(), getArticles()]);
  const companiesActivity = getCompaniesActivity();
  const companies = getCompanies();

  const latestMixed = [...news, ...articles]
    .sort((a, b) => (b.published_date ?? '').localeCompare(a.published_date ?? ''))
    .slice(0, 9);

  const topCompanies = Object.entries(
    companiesActivity.reduce<Record<string, number>>((acc, item) => {
      if (item.company_slug) acc[item.company_slug] = (acc[item.company_slug] ?? 0) + 1;
      return acc;
    }, {})
  )
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);

  return (
    <div>
      <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.25em] text-cyan-accent">Alchemia Solutions</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight text-white">
            Painel de Inteligência <span className="text-gradient-cyan">CADD &amp; AI Drug Discovery</span>
          </h1>
        </div>
        <LiveClock lastRunFinished={meta?.last_run_finished ?? null} />
      </div>

      <div className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Artigos & Preprints" value={articles.length} hint="PubMed · bioRxiv · arXiv · ChemRxiv · SciELO" accent="cyan" />
        <StatCard label="Notícias" value={news.length} hint="Google News · Nature · feeds" accent="progress" />
        <StatCard label="Menções de Empresas" value={companiesActivity.length} hint={`${companies.length} empresas monitoradas`} accent="done" />
        <StatCard
          label="Última coleta (duração)"
          value={meta ? `${meta.duration_seconds}s` : '—'}
          hint={meta ? `+${meta.totals.new_articles_this_run + meta.totals.new_news_this_run} itens novos` : 'pipeline ainda não rodou'}
          accent="start"
        />
      </div>

      <div className="mb-8 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-mono text-[13px] uppercase tracking-wide text-slate-400">Últimas atualizações</h2>
            <Link href="/noticias" className="font-mono text-[11px] text-cyan-accent hover:underline">
              ver todas →
            </Link>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {latestMixed.map((item) => (
              <ItemCard key={item.dedupe_key} item={item} />
            ))}
            {latestMixed.length === 0 ? (
              <p className="col-span-2 text-sm text-slate-500">
                Nenhum item coletado ainda. Rode <code className="text-cyan-accent">pipeline/run_all.py</code>.
              </p>
            ) : null}
          </div>
        </div>

        <div>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-mono text-[13px] uppercase tracking-wide text-slate-400">Empresas mais ativas</h2>
            <Link href="/empresas" className="font-mono text-[11px] text-cyan-accent hover:underline">
              ver todas →
            </Link>
          </div>
          <div className="alchemia-card divide-y divide-white/5">
            {topCompanies.map(([slug, count]) => (
              <Link
                key={slug}
                href={`/empresas/${slug}`}
                className="flex items-center justify-between px-4 py-3 text-sm hover:bg-white/5"
              >
                <span className="capitalize text-slate-200">{slug.replace(/-/g, ' ')}</span>
                <span className="font-mono text-cyan-accent">{count}</span>
              </Link>
            ))}
            {topCompanies.length === 0 ? (
              <p className="px-4 py-3 text-sm text-slate-500">Sem dados de empresas ainda.</p>
            ) : null}
          </div>

          {meta ? (
            <div className="alchemia-card mt-4 p-4">
              <h3 className="mb-2 font-mono text-[11px] uppercase tracking-wide text-slate-400">Status dos coletores</h3>
              <div className="space-y-1.5">
                {Object.entries(meta.collectors).map(([name, result]) => (
                  <div key={name} className="flex items-center justify-between text-[12px]">
                    <span className="font-mono text-slate-400">{name}</span>
                    <span
                      className={`font-mono ${
                        result.skipped
                          ? 'text-slate-500'
                          : result.error
                            ? 'text-status-risk'
                            : 'text-status-done'
                      }`}
                    >
                      {result.skipped ? 'pulado' : result.error ? 'erro' : `${result.count} itens`}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
