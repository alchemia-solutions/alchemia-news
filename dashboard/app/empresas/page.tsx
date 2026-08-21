import Link from 'next/link';
import PageHeader from '@/components/PageHeader';
import { getCompanies, getCompaniesActivity } from '@/lib/data';
import { CATEGORY_LABELS } from '@/lib/types';

export const dynamic = 'force-dynamic';

export default async function EmpresasPage() {
  const [companies, activity] = await Promise.all([getCompanies(), getCompaniesActivity()]);

  const countBySlug = activity.reduce<Record<string, number>>((acc, item) => {
    if (item.company_slug) acc[item.company_slug] = (acc[item.company_slug] ?? 0) + 1;
    return acc;
  }, {});

  const byCategory = companies.reduce<Record<string, typeof companies>>((acc, c) => {
    (acc[c.category] ??= []).push(c);
    return acc;
  }, {});

  return (
    <div>
      <PageHeader
        title="Empresas"
        description="Empresas, laboratórios e instituições monitoradas no nicho de CADD/AI Drug Discovery — referências de mercado, big techs investindo em biologia/química computacional, e instituições brasileiras. Redes sociais (LinkedIn/X/Instagram) ainda não estão nesta rodada — ver Sobre."
      />

      {Object.entries(byCategory).map(([category, list]) => (
        <div key={category} className="mb-8">
          <h2 className="mb-3 font-mono text-[12px] uppercase tracking-wide text-slate-400">
            {CATEGORY_LABELS[category] ?? category}
          </h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {list.map((company) => (
              <Link
                key={company.slug}
                href={`/empresas/${company.slug}`}
                className="alchemia-card flex items-center justify-between p-4 hover:-translate-y-0.5"
              >
                <div>
                  <p className="font-medium text-slate-100">{company.name}</p>
                  <p className="mt-0.5 font-mono text-[11px] text-slate-400">{company.url.replace(/^https?:\/\//, '')}</p>
                </div>
                <span className="rounded-full border border-cyan-accent/30 bg-cyan-accent/10 px-2.5 py-1 font-mono text-[12px] text-cyan-accent">
                  {countBySlug[company.slug] ?? 0}
                </span>
              </Link>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
