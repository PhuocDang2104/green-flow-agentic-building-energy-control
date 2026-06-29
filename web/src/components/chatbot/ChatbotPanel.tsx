"use client";

import { useEffect, useState } from "react";
import { History, Plus, X } from "lucide-react";
import { api } from "@/lib/api";
import { useAppStore } from "@/stores/appStore";
import type { ChatSessionSummary } from "@/lib/types";
import ChatThread from "./ChatThread";

const SESSION_STORAGE_KEY = "greenflow_chat_session_id";
const BOT_STATES = [
  { src: "/assets/landing/chatbot/bot_building.png", speech: "Need a quick building insight?" },
  { src: "/assets/landing/chatbot/bot_hi.png", speech: "Hi, I am GreenFlow!" },
  { src: "/assets/landing/chatbot/bot_love.png", speech: "Ready to optimize energy?" },
];

export default function ChatbotPanel() {
  const open = useAppStore((s) => s.chatbotOpen);
  const setOpen = useAppStore((s) => s.setChatbotOpen);

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [botIndex, setBotIndex] = useState(0);
  const [botHover, setBotHover] = useState(false);

  // cycle the bot pose while the panel is closed
  useEffect(() => {
    if (open) return;
    const timer = window.setInterval(
      () => setBotIndex((value) => (value + 1) % BOT_STATES.length), 3200);
    return () => window.clearInterval(timer);
  }, [open]);

  // resume the last conversation on first open (ChatThread loads it from the id)
  useEffect(() => {
    if (!open || sessionId !== null) return;
    const saved = typeof window !== "undefined"
      ? window.localStorage.getItem(SESSION_STORAGE_KEY) : null;
    if (saved) setSessionId(saved);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const persistSession = (id: string) => {
    setSessionId(id);
    window.localStorage.setItem(SESSION_STORAGE_KEY, id);
  };

  const startNewChat = () => {
    setSessionId(null);
    setShowHistory(false);
    window.localStorage.removeItem(SESSION_STORAGE_KEY);
  };

  const openHistory = () => {
    setShowHistory((v) => !v);
    if (!sessions.length) api.chatSessions().then(setSessions).catch(() => {});
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
          <img
            src="/assets/landing/AI-greenflow_logo.png"
            alt="GreenFlow AI"
            className="h-8 w-8 shrink-0 rounded-full object-contain"
          />
          <div>
            <p className="text-sm font-semibold leading-tight">GreenFlow AI Copilot</p>
            <p className="text-[11px] text-text-muted">Ask, or talk with the mic</p>
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
            <button
              key={s.id}
              onClick={() => { setShowHistory(false); persistSession(s.id); }}
              className={`block w-full truncate rounded-lg px-2 py-1.5 text-left text-[12px] transition hover:bg-white
                ${s.id === sessionId ? "text-teal font-medium" : "text-text-secondary"}`}
            >
              {s.first_message || "(empty)"}
              <span className="ml-1.5 text-text-muted">· {s.n_messages} msgs</span>
            </button>
          ))}
        </div>
      )}

      <ChatThread sessionId={sessionId} onSessionId={persistSession} />
    </div>
  );
}
