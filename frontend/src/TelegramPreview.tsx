import type { ReactNode } from 'react';

// Render a tiny tag allowlist as React nodes. Never inject server HTML into the page.
function render(node: Node, key: number): ReactNode {
  if (node.nodeType === Node.TEXT_NODE) return node.textContent;
  if (!(node instanceof Element)) return null;
  const children = Array.from(node.childNodes).map(render);
  if (node.tagName === 'B') return <strong key={key}>{children}</strong>;
  if (node.tagName === 'I') return <em key={key}>{children}</em>;
  return <span key={key}>{node.textContent}</span>;
}

export default function TelegramPreview({html, text}: {html?: string; text?: string}) {
  const content = html ? Array.from(new DOMParser().parseFromString(html, 'text/html').body.childNodes).map(render) : text;
  return <div className="telegram-preview"><div className="brief-text" aria-label="Telegram message preview">{content}</div></div>;
}
