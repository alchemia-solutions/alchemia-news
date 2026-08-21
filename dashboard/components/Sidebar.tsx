'use client';

import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';

// Reorganizado em 3 grupos (2026-08-19, Fase 2) -- o app deixou de ser só o radar de nicho do
// setor que o mantém e passou a cobrir também captação de recursos e comunicação, para uso da
// empresa inteira. "Sobre" fica fora dos grupos, como já estava (rodapé da sidebar). Ver
// docs/specs/2026-08-19-funding-opportunities-and-app-restructure.md.
//
// 2026-08-21 -- vira GAVETA abaixo do breakpoint `md` (768px). Antes disto o `<aside>` era
// `fixed w-60` sem nenhuma variante responsiva e o `<main>` era `ml-60` fixo: num viewport de
// 375px sobravam **71px** de coluna de conteúdo (240 de sidebar + 64 de padding), com a sidebar
// cobrindo 64% da tela e sem nenhuma forma de fechá-la. Medido, não estimado. As grades internas
// das páginas já eram responsivas (`sm:`/`md:`/`lg:`) -- só a casca nunca tinha sido adaptada.
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

// `slate-400` (#94a3b8) e não `slate-500`/`slate-600`: sobre o navy-950 (#060c1e) do app, o
// slate-600 dos títulos de grupo media **2,57:1** e o slate-500 **4,09:1** -- ambos abaixo do
// mínimo de 4,5:1 para texto pequeno. Medido no app renderizado em 2026-08-21. slate-400 passa.
const LINK_BASE =
  'flex items-center gap-3 rounded-lg px-3 py-2.5 font-mono text-[13px] transition-colors ' +
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-accent focus-visible:ring-offset-2 ' +
  'focus-visible:ring-offset-navy-900';
const LINK_ACTIVE = 'border border-cyan-accent/30 bg-cyan-accent/10 text-cyan-accent';
const LINK_IDLE = 'border border-transparent text-slate-300 hover:bg-white/5 hover:text-white';

export default function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const toggleRef = useRef<HTMLButtonElement | null>(null);

  function isActive(href: string) {
    return pathname === href || (href !== '/' && pathname?.startsWith(href));
  }

  // Fecha a gaveta ao navegar. Sem isto, tocar num link no celular carrega a página nova com a
  // gaveta ainda aberta por cima dela.
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  // Esc fecha e devolve o foco ao botão que abriu -- comportamento esperado de diálogo modal.
  // Trava o scroll do body enquanto aberta, senão a página de trás rola sob a gaveta.
  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setOpen(false);
        toggleRef.current?.focus();
      }
    }
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  function renderLink(item: { href: string; label: string; icon: string }) {
    const active = isActive(item.href);
    return (
      <Link
        key={item.href}
        href={item.href}
        aria-current={active ? 'page' : undefined}
        className={`${LINK_BASE} ${active ? LINK_ACTIVE : LINK_IDLE}`}
      >
        <span aria-hidden="true" className="text-[11px] opacity-70">
          {item.icon}
        </span>
        {item.label}
      </Link>
    );
  }

  return (
    <>
      {/* Barra de topo -- só abaixo de `md`, onde a sidebar não está visível. `sticky` para o
          botão de menu continuar alcançável depois de rolar uma lista longa. */}
      <div className="sticky top-0 z-30 flex items-center gap-3 border-b border-cyan-accent/10 bg-navy-900/85 px-4 py-3 backdrop-blur-xl md:hidden">
        <button
          ref={toggleRef}
          type="button"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          aria-controls="sidebar-nav"
          aria-label={open ? 'Fechar menu de navegação' : 'Abrir menu de navegação'}
          className="flex h-9 w-9 flex-none items-center justify-center rounded-lg border border-cyan-accent/25 text-cyan-accent transition-colors hover:bg-cyan-accent/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-accent focus-visible:ring-offset-2 focus-visible:ring-offset-navy-900"
        >
          <span aria-hidden="true" className="text-base leading-none">
            {open ? '✕' : '☰'}
          </span>
        </button>
        <Image src="/alchemia-logo.png" alt="" width={26} height={26} aria-hidden="true" />
        <p className="font-mono text-[12px] font-semibold tracking-wide text-white">
          ALCHEMIA <span className="text-cyan-accent">NEWS</span>
        </p>
      </div>

      {/* Fundo escuro atrás da gaveta. `md:hidden` porque acima do breakpoint a sidebar é fixa e
          não modal. Não é focável -- o Esc e o botão ✕ são os caminhos de teclado. */}
      {open ? (
        <div
          className="fixed inset-0 z-40 bg-black/65 backdrop-blur-sm md:hidden"
          onClick={() => setOpen(false)}
          aria-hidden="true"
        />
      ) : null}

      <aside
        id="sidebar-nav"
        aria-label="Navegação principal"
        className={`fixed left-0 top-0 z-50 flex h-screen w-60 flex-col border-r border-cyan-accent/10 bg-navy-900/95 backdrop-blur-xl transition-transform duration-200 md:z-40 md:translate-x-0 md:bg-navy-900/60 motion-reduce:transition-none ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-center gap-3 px-5 py-6">
          <Image
            src="/alchemia-logo.png"
            alt=""
            width={36}
            height={36}
            aria-hidden="true"
            className="drop-shadow-[0_0_12px_rgba(41,211,245,0.35)]"
          />
          <div>
            <p className="font-mono text-[13px] font-semibold tracking-wide text-white">ALCHEMIA</p>
            <p className="font-mono text-[10px] tracking-[0.2em] text-cyan-accent">NEWS INTEL</p>
          </div>
        </div>

        <nav className="flex-1 space-y-5 overflow-y-auto px-3 pb-4">
          <div>{renderLink(TOP_ITEM)}</div>

          {/* `role="group"` + `aria-labelledby` em vez de <h3>: são rótulos de agrupamento de
              navegação, não seções do documento -- entrar no outline de headings competiria com o
              <h1> de cada página sem nunca ter um <h2> entre eles. */}
          {NAV_GROUPS.map((group) => {
            const labelId = `nav-group-${group.label.replace(/\s+/g, '-').toLowerCase()}`;
            return (
              <div key={group.label} role="group" aria-labelledby={labelId}>
                <p
                  id={labelId}
                  className="mb-1.5 px-3 font-mono text-[10px] uppercase tracking-[0.15em] text-slate-400"
                >
                  {group.label}
                </p>
                <div className="space-y-1">{group.items.map(renderLink)}</div>
              </div>
            );
          })}

          <div>{renderLink({ href: '/sobre', label: 'Sobre', icon: '◈' })}</div>
        </nav>

        <div className="border-t border-white/5 px-5 py-4">
          <p className="font-mono text-[10px] leading-relaxed text-slate-400">
            Alchemia Solutions
            <br />
            Inteligência de mercado &amp; captação · uso da empresa inteira
          </p>
        </div>
      </aside>
    </>
  );
}
