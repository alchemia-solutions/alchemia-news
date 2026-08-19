import PageHeader from '@/components/PageHeader';
import MarkdownLite from '@/components/MarkdownLite';
import { getLatestNewsletter, formatDate } from '@/lib/data';

export const dynamic = 'force-dynamic';

export default function NewsletterPage() {
  const newsletter = getLatestNewsletter();

  return (
    <div>
      <PageHeader
        title="Newsletter"
        description={
          newsletter
            ? `Edição mais recente: ${formatDate(newsletter.date)}. Publicada pela rotina do Axel — somente leitura aqui.`
            : 'Publicada pela rotina do Axel (setor alchemia-bots) — este painel só lê o que já foi publicado.'
        }
      />

      {newsletter ? (
        <div className="alchemia-card p-6">
          <MarkdownLite content={newsletter.content} />
        </div>
      ) : (
        <div className="alchemia-card p-6 text-center">
          <p className="text-slate-400">Nenhuma newsletter publicada ainda.</p>
          <p className="mt-2 text-[12px] text-slate-600">
            Esta rota é somente leitura — quem publica é a rotina do Axel, em{' '}
            <code className="text-cyan-accent">pipeline/data/newsletter/AAAA-MM-DD.md</code>. Assim
            que a primeira edição existir, ela aparece aqui automaticamente, sem rebuild.
          </p>
        </div>
      )}
    </div>
  );
}
