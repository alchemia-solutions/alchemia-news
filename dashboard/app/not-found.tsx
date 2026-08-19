import Link from 'next/link';

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center text-center">
      <p className="font-mono text-6xl text-cyan-accent">404</p>
      <p className="mt-2 text-slate-400">Página não encontrada.</p>
      <Link href="/" className="mt-4 font-mono text-[12px] text-cyan-accent hover:underline">
        ← voltar ao painel
      </Link>
    </div>
  );
}
