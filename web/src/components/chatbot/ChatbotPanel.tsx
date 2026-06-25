"use client";

import { useEffect, useRef, useState } from "react";
import { BookOpen, History, Loader2, Plus, Send, Sparkles, X } from "lucide-react";
import { api } from "@/lib/api";
import { SUGGESTED_PROMPTS } from "@/lib/constants";
import { useAppStore } from "@/stores/appStore";
import type { ChatQueryResponse, ChatSessionSummary } from "@/lib/types";
import InlineRunSteps from "./InlineRunSteps";
import Markdown from "./Markdown";
import ThinkingIndicator from "./ThinkingIndicator";

const SESSION_STORAGE_KEY = "greenflow_chat_session_id";
const BOT_STATES = [
  {
    src: "/assets/landing/chatbot/bot_building.png",
    speech: "Can xem toa nha nao?",
  },
  {
    src: "/assets/landing/chatbot/bot_hi.png",
    speech: "Hi, minh la GreenFlow!",
  },
  {
    src: "/assets/landing/chatbot/bot_love.png",
    speech: "Toi uu nang luong nao!",
  },
];

interface Message {
  role: "user" | "assistant";
  text: string;
  meta?: ChatQueryResponse;
}

function rowsToMessages(rows: { role: string; content: string; tool_calls?: ChatQueryResponse["tools_used"] }[]): Message[] {
  return rows
    .filter((r) => r.role === "user" || r.role === "assistant")
    .map((r) => ({
      role: r.role as "user" | "assistant",
      text: r.content,
      meta: r.tool_calls?.length ? { session_id: "", answer: r.content, tools_used: r.tool_calls } : undefined,
    }));
}

export default function ChatbotPanel() {
  const open = useAppStore((s) => s.chatbotOpen);
  const setOpen = useAppStore((s) => s.setChatbotOpen);

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [botIndex, setBotIndex] = useState(0);
  const [botHover, setBotHover] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  useEffect(() => {
    if (open) return;
    const timer = window.setInterval(() => {
      setBotIndex((value) => (value + 1) % BOT_STATES.length);
    }, 3200);
    return () => window.clearInterval(timer);
  }, [open]);

  // On first open, resume the last conversation from localStorage so a page
  // reload / revisit doesn't lose history.
  useEffect(() => {
    if (!open || sessionId !== null) return;
    const saved = typeof window !== "undefined"
      ? window.localStorage.getItem(SESSION_STORAGE_KEY) : null;
    if (!saved) return;
    setLoadingHistory(true);
    api.chatSessionMessages(saved)
      .then((rows) => {
        const loaded = rowsToMessages(rows);
        if (loaded.length) {
          setMessages(loaded);
          setSessionId(saved);
        } else {
          window.localStorage.removeItem(SESSION_STORAGE_KEY);
        }
      })
      .catch(() => window.localStorage.removeItem(SESSION_STORAGE_KEY))
      .finally(() => setLoadingHistory(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const persistSession = (id: string) => {
    setSessionId(id);
    window.localStorage.setItem(SESSION_STORAGE_KEY, id);
  };

  const send = async (text: string) => {
    const message = text.trim();
    if (!message || busy) return;
    setMessages((m) => [...m, { role: "user", text: message }]);
    setInput("");
    setBusy(true);
    try {
      const res = await api.chatQuery(message, sessionId);
      setMessages((m) => [...m, { role: "assistant", text: res.answer, meta: res }]);
      if (res.session_id && res.session_id !== sessionId) persistSession(res.session_id);
    } catch {
      setMessages((m) => [...m, {
        role: "assistant",
        text: "Sorry — the chat service could not process that request. Check that the API is running.",
      }]);
    } finally {
      setBusy(false);
    }
  };

  const startNewChat = () => {
    setMessages([]);
    setSessionId(null);
    setShowHistory(false);
    window.localStorage.removeItem(SESSION_STORAGE_KEY);
  };

  const openHistory = () => {
    setShowHistory((v) => !v);
    if (!sessions.length) api.chatSessions().then(setSessions).catch(() => {});
  };

  const loadSession = async (id: string) => {
    setShowHistory(false);
    setLoadingHistory(true);
    try {
      const rows = await api.chatSessionMessages(id);
      setMessages(rowsToMessages(rows));
      persistSession(id);
    } finally {
      setLoadingHistory(false);
    }
  };

  if (!open) {
    const bot = BOT_STATES[botIndex];
    return (
      <button
        onClick={() => setOpen(true)}
        onMouseEnter={() => setBotHover(true)}
        onMouseLeave={() => setBotHover(false)}
        className="fixed bottom-4 right-4 z-50 h-24 w-24 bg-transparent p-0 transition hover:-translate-y-1 focus:outline-none"
        aria-label="Open GreenFlow chat"
      >
        {botHover && (
          <span className="absolute bottom-[76px] right-16 w-max max-w-[190px] rounded-2xl bg-white px-3 py-2 text-xs font-medium text-text-primary shadow-floating">
            {bot.speech}
            <span className="absolute -bottom-1 right-4 h-3 w-3 rotate-45 bg-white" />
          </span>
        )}
        <img
          src={bot.src}
          alt=""
          className="h-full w-full object-contain drop-shadow-[0_18px_30px_rgba(15,23,42,0.22)]"
          draggable={false}
        />
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
            <p className="text-[11px] text-text-muted">Ask about energy, cost, alerts, zones</p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={startNewChat} title="New conversation"
                  className="grid h-7 w-7 place-items-center rounded-full text-text-muted hover:bg-white">
            <Plus size={15} />
          </button>
          <button onClick={openHistory} title="Past conversations"
                  className={`grid h-7 w-7 place-items-center rounded-full hover:bg-white
                    ${showHistory ? "bg-white text-teal" : "text-text-muted"}`}>
            <History size={15} />
          </button>
          <button onClick={() => setOpen(false)}
                  className="grid h-7 w-7 place-items-center rounded-full text-text-muted hover:bg-white">
            <X size={15} />
          </button>
        </div>
      </div>

      {showHistory && (
        <div className="max-h-48 overflow-y-auto border-b border-border bg-surface-muted/40 px-3 py-2">
          {sessions.length === 0 && (
            <p className="px-2 py-1 text-[12px] text-text-muted">No past conversations yet.</p>
          )}
          {sessions.map((s) => (
            <button key={s.id} onClick={() => loadSession(s.id)}
                    className={`block w-full truncate rounded-lg px-2 py-1.5 text-left text-[12px] transition hover:bg-white
                      ${s.id === sessionId ? "text-teal font-medium" : "text-text-secondary"}`}>
              {s.first_message || "(empty)"}
              <span className="ml-1.5 text-text-muted">· {s.n_messages} msgs</span>
            </button>
          ))}
        </div>
      )}

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
        {loadingHistory && (
          <div className="flex items-center gap-2 text-[13px] text-text-muted">
            <Loader2 className="h-3.5 w-3.5 animate-spin text-teal" /> Loading conversation…
          </div>
        )}
        {!loadingHistory && messages.length === 0 && (
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
              {m.role === "assistant"
                ? <Markdown>{m.text}</Markdown>
                : <span className="whitespace-pre-wrap">{m.text}</span>}
              {m.meta?.tools_used && m.meta.tools_used.filter((t) => t.name !== "trigger_agent_action").length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {m.meta.tools_used.filter((t) => t.name !== "trigger_agent_action").map((t, ti) => (
                    <span key={ti}
                          className="rounded-full bg-white px-2 py-0.5 text-[10px] font-medium text-text-muted shadow-sm">
                      {t.name}
                    </span>
                  ))}
                </div>
              )}
              {m.meta?.tools_used?.filter((t) => t.name === "trigger_agent_action" && t.result?.run_id)
                .map((t, ti) => (
                  <InlineRunSteps key={ti} runId={t.result.run_id} action={t.result.action} />
                ))}
              {m.role === "assistant" && m.meta?.sources && m.meta.sources.length > 0 && (
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  <BookOpen size={11} className="text-text-muted" />
                  {m.meta.sources.map((s, si) => (
                    <span key={si}
                          className="rounded-full bg-teal-soft px-2 py-0.5 text-[10px] font-medium text-teal">
                      {s}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {busy && (
          <div className="flex justify-start">
            <div className="w-[85%] max-w-[85%]">
              <ThinkingIndicator />
            </div>
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
