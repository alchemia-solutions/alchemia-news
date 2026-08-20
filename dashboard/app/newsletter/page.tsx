import Link from 'next/link';
import PageHeader from '@/components/PageHeader';
import { getNewsletters, formatDate, previewNewsletter } from '@/lib/data';

export const dynamic = 'force-dynamic';

// 2026-08-20 (mais tarde) -- virou lista navegável por data, a pedido do fundador:
// antes mostrava só a edição mais recente com o texto inteiro já aberto. Agora cada
// edição aparece como um card com prévia curta; o conteúdo completo só abre em
// /newsletter/[date] quando o usuário clica. Ver app/newsletter/[date]/page.tsx.
export default async function NewsletterPage() {
  const editions = await getNewsletters();

  return (
    <div>
      <PageHeader
        title="Newsletter"
        description="Edições diárias publicadas pela rotina do Axel — resumo estruturado de cada achado do dia, com leitura interpretativa separada ('💡 Insight Alchemia'). Este painel é somente leitura."
      />

      {editions.length === 0 ? (
        <div className="alchemia-card p-6 text-center">
          <p className="text-slate-400">Nenhuma newsletter publicada ainda.</p>
          <p className="mt-2 text-[12px] text-slate-600">
            Esta rota é somente leitura — quem publica é a rotina do Axel. Assim que a primeira
            edição existir, ela aparece aqui automaticamente.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {editions.map((edition) => {
            const { meta, excerpt } = previewNewsletter(edition.content);
            return (
              <Link
                key={edition.date}
                href={`/newsletter/${edition.date}`}
                className="alchemia-card block p-5 hover:-translate-y-0.5"
              >
                <div className="mb-1 flex items-center justify-between gap-4">
                  <h2 className="font-medium text-slate-100">{formatDate(edition.date)}</h2>
                  <span className="font-mono text-[11px] text-cyan-accent">ver completa →</span>
                </div>
                {meta ? <p className="mb-2 font-mono text-[11px] text-slate-500">{meta}</p> : null}
                {excerpt ? <p className="text-[13px] leading-relaxed text-slate-400">{excerpt}</p> : null}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
