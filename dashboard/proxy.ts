import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// Gate de acesso da diretoria — só entra em vigor quando NODE_ENV=production (setado pelo próprio
// Next.js em qualquer `next build`/`next start`, em qualquer plataforma -- não depende de detectar
// Vercel/Cloudflare/etc especificamente). `npm run dev` local continua sem gate, sem atrapalhar o
// uso interno já existente. Falha fechada por design: se SITE_AUTH_USER/SITE_AUTH_PASSWORD não
// estiverem configuradas no ambiente de produção, o site fica bloqueado para todo mundo (inclusive
// o fundador) até serem definidas — nunca abre por engano por falta de configuração. Ver AGENTS.md
// deste setor, addendum 2026-08-19.

function isAuthorized(request: NextRequest): boolean {
  const expectedUser = process.env.SITE_AUTH_USER;
  const expectedPassword = process.env.SITE_AUTH_PASSWORD;
  if (!expectedUser || !expectedPassword) return false;

  const header = request.headers.get('authorization');
  if (!header || !header.startsWith('Basic ')) return false;

  let decoded: string;
  try {
    decoded = atob(header.slice('Basic '.length));
  } catch {
    return false;
  }
  const separatorIndex = decoded.indexOf(':');
  if (separatorIndex === -1) return false;

  const user = decoded.slice(0, separatorIndex);
  const password = decoded.slice(separatorIndex + 1);
  return user === expectedUser && password === expectedPassword;
}

export function proxy(request: NextRequest) {
  if (process.env.NODE_ENV !== 'production') {
    return NextResponse.next();
  }

  if (isAuthorized(request)) {
    return NextResponse.next();
  }

  return new Response('Acesso restrito - Alchemia Solutions.', {
    status: 401,
    headers: {
      // Valor de header HTTP precisa ser ByteString (Latin1) -- nunca use travessao/emoji/acento
      // fora do ASCII aqui (achado real: travessao (U+2014) quebrava com 500, nao 401).
      'WWW-Authenticate': 'Basic realm="Alchemia News - acesso da diretoria"',
    },
  });
}

export const config = {
  matcher: [
    // Todas as rotas, exceto assets estáticos/otimização de imagem/favicon — mesmo padrão
    // recomendado pela doc oficial do Next.js 16 para não bloquear CSS/JS/imagem.
    '/((?!_next/static|_next/image|favicon.ico).*)',
  ],
};
