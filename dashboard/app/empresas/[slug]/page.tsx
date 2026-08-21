import Link from 'next/link';
import { notFound } from 'next/navigation';
import PageHeader from '@/components/PageHeader';
import ItemCard from '@/components/ItemCard';
import { getCompanies, getCompaniesActivity } from '@/lib/data';
import { CATEGORY_LABELS } from '@/lib/types';

export const dynamic = 'force-dynamic';

export default async function EmpresaDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const [companies, allActivity] = await Promise.all([getCompanies(), getCompaniesActivity()]);
  const company = companies.find((c) => c.slug === slug);
  if (!company) notFound();

  const activity = allActivity.filter((item) => item.company_slug === slug);

  return (
    <div>
      <Link href="/empresas" className="mb-4 inline-block font-mono text-[11px] text-cyan-accent hover:underline">
        ← todas as empresas
      </Link>
      <PageHeader
        title={company.name}
        description={company.url}
        right={
          <a
            href={company.url}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg border border-cyan-accent/30 bg-cyan-accent/10 px-4 py-2 font-mono text-[12px] text-cyan-accent hover:bg-cyan-accent/20"
          >
            visitar site →
          </a>
        }
      />

      <div className="mb-6 flex items-center gap-3">
        <span className="rounded-full border border-white/10 px-3 py-1 font-mono text-[11px] text-slate-400">
          {CATEGORY_LABELS[company.category] ?? company.category}
        </span>
        <span className="rounded-full border border-white/10 px-3 py-1 font-mono text-[11px] text-slate-400">
          {activity.length} menções coletadas
        </span>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {activity.map((item) => (
          <ItemCard key={item.dedupe_key} item={item} />
        ))}
      </div>
      {activity.length === 0 ? (
        <p className="text-sm text-slate-400">
          Nenhuma menção coletada ainda para esta empresa. O pipeline roda 3x/dia — rode manualmente com{' '}
          <code className="text-cyan-accent">python pipeline/run_all.py</code> para popular agora.
        </p>
      ) : null}
    </div>
  );
}
