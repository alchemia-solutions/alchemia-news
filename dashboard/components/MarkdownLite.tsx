import type { ReactNode } from 'react';

/**
 * Renderizador de Markdown minimalista, sem dependência nova -- suficiente para o conteúdo que
 * este setor já produz (títulos, listas, negrito/itálico, links, `código`, `---`). Não é um
 * parser CommonMark completo (não lida com blocos aninhados, tabelas, blockquotes) -- suficiente
 * para o texto simples de uma newsletter/radar, sem puxar uma lib nova só para isto. Server-safe
 * (função pura, sem hooks) -- usado diretamente dentro de `app/newsletter/page.tsx`.
 */

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const INLINE_RE = /\[([^\]]+)\]\(([^)]+)\)|\*\*([^*]+)\*\*|`([^`]+)`|\*([^*]+)\*/g;
  const nodes: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let i = 0;

  while ((match = INLINE_RE.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }
    const [, linkText, linkUrl, bold, code, italic] = match;
    const key = `${keyPrefix}-${i++}`;
    if (linkText !== undefined) {
      nodes.push(
        <a
          key={key}
          href={linkUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-cyan-accent underline decoration-cyan-accent/30 underline-offset-2 hover:decoration-cyan-accent"
        >
          {linkText}
        </a>
      );
    } else if (bold !== undefined) {
      nodes.push(
        <strong key={key} className="font-semibold text-slate-100">
          {bold}
        </strong>
      );
    } else if (code !== undefined) {
      nodes.push(
        <code key={key} className="rounded bg-navy-800/80 px-1 py-0.5 font-mono text-[0.9em] text-cyan-accent">
          {code}
        </code>
      );
    } else if (italic !== undefined) {
      nodes.push(
        <em key={key} className="italic text-slate-300">
          {italic}
        </em>
      );
    }
    lastIndex = INLINE_RE.lastIndex;
  }
  if (lastIndex < text.length) nodes.push(text.slice(lastIndex));
  return nodes;
}

export default function MarkdownLite({ content }: { content: string }) {
  const lines = content.replace(/\r\n/g, '\n').split('\n');
  const blocks: ReactNode[] = [];
  let paragraphBuf: string[] = [];
  let listBuf: string[] = [];
  let blockKey = 0;

  function flushParagraph() {
    if (paragraphBuf.length === 0) return;
    const text = paragraphBuf.join(' ');
    blocks.push(
      <p key={`p-${blockKey++}`} className="mb-3 text-[14px] leading-relaxed text-slate-300">
        {renderInline(text, `p-${blockKey}`)}
      </p>
    );
    paragraphBuf = [];
  }

  function flushList() {
    if (listBuf.length === 0) return;
    blocks.push(
      <ul key={`ul-${blockKey++}`} className="mb-3 ml-5 list-disc space-y-1 text-[14px] leading-relaxed text-slate-300">
        {listBuf.map((item, idx) => (
          <li key={idx}>{renderInline(item, `li-${blockKey}-${idx}`)}</li>
        ))}
      </ul>
    );
    listBuf = [];
  }

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    const trimmed = line.trim();

    if (trimmed === '') {
      flushParagraph();
      flushList();
      continue;
    }

    if (/^(---|\*\*\*)$/.test(trimmed)) {
      flushParagraph();
      flushList();
      blocks.push(<hr key={`hr-${blockKey++}`} className="my-5 border-white/10" />);
      continue;
    }

    const headingMatch = /^(#{1,4})\s+(.*)$/.exec(trimmed);
    if (headingMatch) {
      flushParagraph();
      flushList();
      const level = headingMatch[1].length;
      const text = headingMatch[2];
      const sizeClass =
        level === 1
          ? 'text-2xl font-semibold text-white mt-2'
          : level === 2
            ? 'text-lg font-semibold text-slate-100 mt-6'
            : level === 3
              ? 'text-base font-semibold text-slate-200 mt-4'
              : 'text-sm font-semibold uppercase tracking-wide text-slate-400 mt-3';
      blocks.push(
        <p key={`h-${blockKey++}`} className={`mb-2 ${sizeClass}`}>
          {renderInline(text, `h-${blockKey}`)}
        </p>
      );
      continue;
    }

    const listMatch = /^[-*]\s+(.*)$/.exec(trimmed);
    if (listMatch) {
      flushParagraph();
      listBuf.push(listMatch[1]);
      continue;
    }

    flushList();
    paragraphBuf.push(trimmed);
  }
  flushParagraph();
  flushList();

  return <div>{blocks}</div>;
}
