'use client';

import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const NAV_ITEMS = [
  { href: '/', label: 'Painel', icon: '◆' },
  { href: '/noticias', label: 'Notícias', icon: '▤' },
  { href: '/artigos', label: 'Artigos & Papers', icon: '▧' },
  { href: '/empresas', label: 'Empresas', icon: '▣' },
  { href: '/bancos-ferramentas', label: 'Bancos & Ferramentas', icon: '▥' },
  { href: '/sobre', label: 'Sobre', icon: '◈' },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-60 flex-col border-r border-cyan-accent/10 bg-navy-900/60 backdrop-blur-xl">
      <div className="flex items-center gap-3 px-5 py-6">
        <Image src="/alchemia-logo.png" alt="Alchemia" width={36} height={36} className="drop-shadow-[0_0_12px_rgba(41,211,245,0.35)]" />
        <div>
          <p className="font-mono text-[13px] font-semibold tracking-wide text-white">ALCHEMIA</p>
          <p className="font-mono text-[10px] tracking-[0.2em] text-cyan-accent">NEWS INTEL</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href || (item.href !== '/' && pathname?.startsWith(item.href));
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
      </nav>

      <div className="border-t border-white/5 px-5 py-4">
        <p className="font-mono text-[10px] leading-relaxed text-slate-500">
          Alchemia Solutions
          <br />
          Inteligência de mercado · CADD &amp; AI Drug Discovery
        </p>
      </div>
    </aside>
  );
}
