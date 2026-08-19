import type { Metadata } from 'next';
import AutoRefresh from '@/components/AutoRefresh';
import Sidebar from '@/components/Sidebar';
import './globals.css';

export const metadata: Metadata = {
  title: 'Alchemia News — Inteligência de CADD & AI Drug Discovery',
  description:
    'Painel de inteligência da Alchemia Solutions: notícias, artigos e movimentos de empresas no nicho de Computer-Aided Drug Design e AI Drug Discovery, atualizado 3x ao dia.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body className="alchemia-scanline-bg min-h-screen bg-navy-950 font-sans text-slate-200 antialiased">
        {/* Revalida os server components a cada 60s (pausa com a aba oculta) — ver AutoRefresh.tsx */}
        <AutoRefresh />
        <Sidebar />
        <main className="ml-60 min-h-screen px-8 py-8">
          <div className="mx-auto max-w-6xl">{children}</div>
        </main>
      </body>
    </html>
  );
}
