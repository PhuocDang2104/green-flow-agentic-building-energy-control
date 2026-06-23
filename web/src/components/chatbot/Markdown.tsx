"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

// Compact, chat-sized styling for LLM markdown (GFM: lists, tables, code, etc.)
const components: Components = {
  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="mb-2 list-disc space-y-0.5 pl-4 last:mb-0">{children}</ul>,
  ol: ({ children }) => <ol className="mb-2 list-decimal space-y-0.5 pl-4 last:mb-0">{children}</ol>,
  li: ({ children }) => <li className="leading-snug">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noreferrer"
       className="text-teal underline underline-offset-2">{children}</a>
  ),
  h1: ({ children }) => <h3 className="mb-1 mt-2 text-[13px] font-semibold first:mt-0">{children}</h3>,
  h2: ({ children }) => <h3 className="mb-1 mt-2 text-[13px] font-semibold first:mt-0">{children}</h3>,
  h3: ({ children }) => <h3 className="mb-1 mt-2 text-[13px] font-semibold first:mt-0">{children}</h3>,
  blockquote: ({ children }) => (
    <blockquote className="my-2 border-l-2 border-border pl-2 text-text-secondary">{children}</blockquote>
  ),
  code: ({ className, children }) =>
    className?.startsWith("language-")
      ? <code className="font-mono">{children}</code>
      : <code className="rounded bg-black/10 px-1 py-0.5 font-mono text-[12px]">{children}</code>,
  pre: ({ children }) => (
    <pre className="my-2 overflow-x-auto rounded-lg bg-slate-900 p-2.5 text-[12px] leading-relaxed text-slate-100">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="my-2 overflow-x-auto">
      <table className="w-full border-collapse text-[12px]">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border border-border bg-surface-muted px-2 py-1 text-left font-semibold">{children}</th>
  ),
  td: ({ children }) => <td className="border border-border px-2 py-1 align-top">{children}</td>,
  hr: () => <hr className="my-2 border-border" />,
};

/** Render assistant markdown answers nicely inside the chat bubble. */
export default function Markdown({ children }: { children: string }) {
  return (
    <div className="text-[13px] leading-relaxed [word-break:break-word]">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  );
}
