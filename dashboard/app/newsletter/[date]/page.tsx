import Link from 'next/link';
import { notFound } from 'next/navigation';
import PageHeader from '@/components/PageHeader';
import MarkdownLite from '@/components/MarkdownLite';
import { getNewsletterByDate, formatDate } from '@/lib/data';

export const dynamic = 'force-dynamic';

// Conteúdo completo de uma edição -- só abre quando o usuário clica a partir da
// lista em /newsletter (2026-08-20, mais tarde, a pedido do fundador: antes o texto
// inteiro já vinha exposto na lista).
export default async function NewsletterDetailPage({ params }: { params: Promise<{ date: string }> }) {
  const { date } = await params;
  const edition = await getNewsletterByDate(date);
  if (!edition) notFound();

  return (
    <div>
      <Link href="/newsletter" className="mb-4 inline-block font-mono text-[11px] text-cyan-accent hover:underline">
        ← todas as edições
      </Link>
      <PageHeader title={`Newsletter — ${formatDate(edition.date)}`} description="Publicada pela rotina do Axel — somente leitura aqui." />
      <div className="alchemia-card p-6">
        <MarkdownLite content={edition.content} />
      </div>
    </div>
  );
}
