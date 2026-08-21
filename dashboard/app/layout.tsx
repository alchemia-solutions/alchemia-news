import type { Metadata } from 'next';
import AutoRefresh from '@/components/AutoRefresh';
import PipelineHealthBanner from '@/components/PipelineHealthBanner';
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
        {/* Primeiro elemento focável da página: pula os 17 links da sidebar, que de outro modo
            são atravessados por teclado em toda navegação. Visível só ao receber foco. */}
        <a href="#conteudo" className="skip-link">
          Pular para o conteúdo
        </a>
        {/* Revalida os server components a cada 5 min (pausa com a aba oculta) — ver AutoRefresh.tsx */}
        <AutoRefresh />
        <Sidebar />
        {/* `md:ml-60` e não `ml-60`: abaixo de 768px a sidebar é gaveta off-canvas e o conteúdo
            ocupa a largura inteira. Ver Sidebar.tsx para a medição que motivou isto. */}
        <main id="conteudo" className="min-h-screen px-4 py-6 sm:px-6 md:ml-60 md:px-8 md:py-8">
          <div className="mx-auto max-w-6xl">
            <PipelineHealthBanner />
            {children}
          </div>
        </main>
      </body>
    </html>
  );
}
