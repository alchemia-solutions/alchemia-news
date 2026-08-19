'use client';

import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

// Reorganizado em 3 grupos (2026-08-19, Fase 2) -- o app deixou de ser só o radar de nicho do
// setor que o mantém e passou a cobrir também captação de recursos e comunicação, para uso da
// empresa inteira. "Sobre" fica fora dos grupos, como já estava (rodapé da sidebar). Ver
// docs/specs/2026-08-19-funding-opportunities-and-app-restructure.md.
const TOP_ITEM = { href: '/', label: 'Painel', icon: '◆' };

const NAV_GROUPS: { label: string; items: { href: string; label: string; icon: string }[] }[] = [
  {
    label: 'Inteligência de Mercado',
    items: [
      { href: '/noticias', label: 'Notícias', icon: '▤' },
      { href: '/artigos', label: 'Artigos & Papers', icon: '▧' },
      { href: '/empresas', label: 'Empresas', icon: '▣' },
      { href: '/bancos-ferramentas', label: 'Bancos & Ferramentas', icon: '▥' },
    ],
  },
  {
    label: 'Captação de Recursos',
    items: [
      { href: '/fomento', label: 'Fomento', icon: '⛁' },
      { href: '/programas', label: 'Programas', icon: '⛀' },
    ],
  },
  {
    label: 'Comunicação',
    items: [{ href: '/newsletter', label: 'Newsletter', icon: '✉' }],
  },
];

export default function Sidebar() {
  const pathname = usePathname();

  function isActive(href: string) {
    return pathname === href || (href !== '/' && pathname?.startsWith(href));
  }

  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-60 flex-col border-r border-cyan-accent/10 bg-navy-900/60 backdrop-blur-xl">
      <div className="flex items-center gap-3 px-5 py-6">
        <Image src="/alchemia-logo.png" alt="Alchemia" width={36} height={36} className="drop-shadow-[0_0_12px_rgba(41,211,245,0.35)]" />
        <div>
          <p className="font-mono text-[13px] font-semibold tracking-wide text-white">ALCHEMIA</p>
          <p className="font-mono text-[10px] tracking-[0.2em] text-cyan-accent">NEWS INTEL</p>
        </div>
      </div>

      <nav className="flex-1 space-y-5 overflow-y-auto px-3 pb-4">
        <div>
          <Link
            href={TOP_ITEM.href}
            className={`flex items-center gap-3 rounded-lg px-3 py-2.5 font-mono text-[13px] transition-colors ${
              isActive(TOP_ITEM.href)
                ? 'bg-cyan-accent/10 text-cyan-accent border border-cyan-accent/30'
                : 'text-slate-300 hover:bg-white/5 hover:text-white border border-transparent'
            }`}
          >
            <span className="text-[11px] opacity-70">{TOP_ITEM.icon}</span>
            {TOP_ITEM.label}
          </Link>
        </div>

        {NAV_GROUPS.map((group) => (
          <div key={group.label}>
            <h3 className="mb-1.5 px-3 font-mono text-[10px] uppercase tracking-[0.15em] text-slate-600">
              {group.label}
            </h3>
            <div className="space-y-1">
              {group.items.map((item) => {
                const active = isActive(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex items-center gap-3 rounded-lg px-3 py-2.5 font-mono text-[13px] transition-colors ${
                      active
                        ? 'bg-cyan-accent/10 text-cyan-accent border border-cyan-accent/30'
                        : 'text-slate-300 hover:bg-white/5 hover:text-white border border-transparent'
                    }`}
                  >
                    <span className="text-[11px] opacity-70">{item.icon}</span>
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}

        <div>
          <Link
            href="/sobre"
            className={`flex items-center gap-3 rounded-lg px-3 py-2.5 font-mono text-[13px] transition-colors ${
              isActive('/sobre')
                ? 'bg-cyan-accent/10 text-cyan-accent border border-cyan-accent/30'
                : 'text-slate-300 hover:bg-white/5 hover:text-white border border-transparent'
            }`}
          >
            <span className="text-[11px] opacity-70">◈</span>
            Sobre
          </Link>
        </div>
      </nav>

      <div className="border-t border-white/5 px-5 py-4">
        <p className="font-mono text-[10px] leading-relaxed text-slate-500">
          Alchemia Solutions
          <br />
          Inteligência de mercado &amp; captação · uso da empresa inteira
        </p>
      </div>
    </aside>
  );
}
