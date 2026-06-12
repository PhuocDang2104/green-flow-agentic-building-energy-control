"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, MessageCircle, Send, Sparkles, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { SUGGESTED_PROMPTS } from "@/lib/constants";
import { useAppStore } from "@/stores/appStore";
import type { ChatResponse } from "@/lib/types";

interface Message {
  role: "user" | "assistant";
  text: string;
  meta?: ChatResponse;
}

export default function ChatbotPanel() {
  const open = useAppStore((s) => s.chatbotOpen);
  const setOpen = useAppStore((s) => s.setChatbotOpen);
  const setViewerUpdates = useAppStore((s) => s.setViewerUpdates);
  const selectEntity = useAppStore((s) => s.selectEntity);
  const router = useRouter();

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  const send = async (text: string) => {
    const message = text.trim();
    if (!message || busy) return;
    setMessages((m) => [...m, { role: "user", text: message }]);
    setInput("");
    setBusy(true);
    try {
      const res = await api.chat(message);
      setMessages((m) => [...m, { role: "assistant", text: res.answer, meta: res }]);
      if (res.viewer_updates?.length) setViewerUpdates(res.viewer_updates);
    } catch {
      setMessages((m) => [...m, {
        role: "assistant",
        text: "Sorry — the orchestrator could not process that request. Check that the API is running.",
      }]);
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-5 right-5 z-50 flex items-center gap-2 rounded-full bg-teal px-4 py-3 text-sm font-medium text-white shadow-floating transition hover:bg-teal/90"
      >
        <MessageCircle size={17} /> Ask GreenFlow
      </button>
    );
  }

  return (
    <div className="fixed bottom-5 right-5 z-50 flex h-[600px] w-[400px] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-card border border-border bg-white shadow-floating">
      <div className="flex items-center justify-between border-b border-border bg-teal-soft px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="grid h-7 w-7 place-items-center rounded-full bg-teal text-white">
            <Sparkles size={13} />
          </span>
          <div>
            <p className="text-sm font-semibold leading-tight">Building Copilot</p>
            <p className="text-[11px] text-text-muted">Orchestrator-backed Q&A</p>
          </div>
        </div>
        <button onClick={() => setOpen(false)}
                className="grid h-7 w-7 place-items-center rounded-full text-text-muted hover:bg-white">
          <X size={15} />
        </button>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
        {messages.length === 0 && (
          <div className="space-y-2 pt-2">
            <p className="text-xs text-text-muted">Try asking:</p>
            {SUGGESTED_PROMPTS.map((p) => (
              <button key={p} onClick={() => send(p)}
                      className="block w-full rounded-xl border border-border px-3 py-2 text-left text-[13px] text-text-secondary transition hover:border-teal hover:text-teal">
                {p}
              </button>
            ))}
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
            <div className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-[13px] leading-relaxed
              ${m.role === "user" ? "bg-teal text-white" : "bg-surface-muted text-text-primary"}`}>
              {m.text}
              {m.meta?.related_entities && m.meta.related_entities.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {m.meta.related_entities.map((e) => (
                    <button
                      key={e.entity_key}
                      onClick={() => {
                        selectEntity(e.entity_key);
                        router.push("/dashboard");
                      }}
                      className="rounded-full bg-white px-2.5 py-1 text-[11px] font-medium text-teal shadow-sm transition hover:bg-teal hover:text-white"
                    >
                      {e.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {busy && (
          <div className="flex items-center gap-2 text-[13px] text-text-muted">
            <Loader2 className="h-3.5 w-3.5 animate-spin text-teal" />
            Orchestrator is planning and executing…
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); send(input); }}
        className="flex items-center gap-2 border-t border-border px-3 py-3"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about zones, energy, actions…"
          className="flex-1 rounded-xl border border-border bg-surface-muted/50 px-3 py-2 text-[13px] outline-none focus:border-teal"
        />
        <button type="submit" disabled={busy || !input.trim()}
                className="btn-primary !px-3 !py-2">
          <Send size={15} />
        </button>
      </form>
    </div>
  );
}
