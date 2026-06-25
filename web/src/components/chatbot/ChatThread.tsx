"use client";

import { useEffect, useRef, useState } from "react";
import { BookOpen, Loader2, Mic, Send, Square, Volume2, VolumeX } from "lucide-react";
import { api } from "@/lib/api";
import { SUGGESTED_PROMPTS } from "@/lib/constants";
import type { ChatMessageRow, ChatQueryResponse } from "@/lib/types";
import InlineRunSteps from "./InlineRunSteps";
import Markdown from "./Markdown";
import ThinkingIndicator from "./ThinkingIndicator";

interface Message {
  role: "user" | "assistant";
  text: string;
  meta?: ChatQueryResponse;
}

function rowsToMessages(rows: ChatMessageRow[]): Message[] {
  return rows
    .filter((r) => r.role === "user" || r.role === "assistant")
    .map((r) => ({
      role: r.role as "user" | "assistant",
      text: r.content,
      meta: r.tool_calls?.length
        ? { session_id: "", answer: r.content, tools_used: r.tool_calls }
        : undefined,
    }));
}

/**
 * The conversation core: message list + composer + send loop, driven by a
 * controlled `sessionId`. Used by the floating ChatbotPanel and the full-page
 * Agents & Actions view. When `sessionId` changes it (re)loads that thread —
 * except for a session it just created via a send (loadedRef guards that, so
 * the optimistic messages aren't wiped).
 */
export default function ChatThread({
  sessionId,
  onSessionId,
  showSuggestions = true,
}: {
  sessionId: string | null;
  onSessionId: (id: string) => void;
  showSuggestions?: boolean;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [speakOn, setSpeakOn] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const loadedRef = useRef<string | null>(null);
  const recRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const speakOnRef = useRef(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  useEffect(() => {
    if (sessionId === loadedRef.current) return; // already in sync (incl. our own new session)
    loadedRef.current = sessionId;
    if (!sessionId) {
      setMessages([]);
      return;
    }
    setLoadingHistory(true);
    api
      .chatSessionMessages(sessionId)
      .then((rows) => setMessages(rowsToMessages(rows)))
      .catch(() => setMessages([]))
      .finally(() => setLoadingHistory(false));
  }, [sessionId]);

  const send = async (text: string) => {
    const message = text.trim();
    if (!message || busy) return;
    setMessages((m) => [...m, { role: "user", text: message }]);
    setInput("");
    setBusy(true);
    try {
      const res = await api.chatQuery(message, sessionId);
      setMessages((m) => [...m, { role: "assistant", text: res.answer, meta: res }]);
      if (speakOnRef.current && res.answer) speakText(res.answer);
      if (res.session_id && res.session_id !== sessionId) {
        loadedRef.current = res.session_id; // keep these messages; don't reload over them
        onSessionId(res.session_id);
      }
    } catch {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: "Sorry — the chat service could not process that request. Check that the API is running.",
        },
      ]);
    } finally {
      setBusy(false);
    }
  };

  // --- voice: TTS (read replies aloud) + STT (push-to-talk) -----------------
  const speakText = async (text: string) => {
    try {
      const blob = await api.speak(text);
      audioRef.current?.pause();
      const url = URL.createObjectURL(blob);
      const a = new Audio(url);
      audioRef.current = a;
      a.onended = () => URL.revokeObjectURL(url);
      await a.play();
    } catch {
      /* TTS unavailable — ignore */
    }
  };

  const toggleSpeak = () => {
    const next = !speakOn;
    setSpeakOn(next);
    speakOnRef.current = next;
    if (!next) audioRef.current?.pause();
  };

  const toggleRecord = async () => {
    if (recording) {
      recRef.current?.stop();
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      chunksRef.current = [];
      rec.ondataavailable = (e) => { if (e.data.size) chunksRef.current.push(e.data); };
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setRecording(false);
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || "audio/webm" });
        if (!blob.size) return;
        setTranscribing(true);
        try {
          const { text } = await api.transcribe(blob);
          if (text.trim()) await send(text);
        } catch {
          /* STT failed — ignore */
        } finally {
          setTranscribing(false);
        }
      };
      recRef.current = rec;
      rec.start();
      setRecording(true);
    } catch {
      /* mic denied / unsupported */
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
        {loadingHistory && (
          <div className="flex items-center gap-2 text-[13px] text-text-muted">
            <Loader2 className="h-3.5 w-3.5 animate-spin text-teal" /> Loading conversation…
          </div>
        )}
        {!loadingHistory && messages.length === 0 && showSuggestions && (
          <div className="space-y-2 pt-2">
            <p className="text-xs text-text-muted">Try asking:</p>
            {SUGGESTED_PROMPTS.map((p) => (
              <button
                key={p}
                onClick={() => send(p)}
                className="block w-full rounded-xl border border-border px-3 py-2 text-left text-[13px] text-text-secondary transition hover:border-teal hover:text-teal"
              >
                {p}
              </button>
            ))}
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
            <div
              className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-[13px] leading-relaxed
              ${m.role === "user" ? "bg-teal text-white" : "bg-surface-muted text-text-primary"}`}
            >
              {m.role === "assistant" ? (
                <Markdown>{m.text}</Markdown>
              ) : (
                <span className="whitespace-pre-wrap">{m.text}</span>
              )}
              {m.meta?.tools_used &&
                m.meta.tools_used.filter((t) => t.name !== "trigger_agent_action").length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {m.meta.tools_used
                      .filter((t) => t.name !== "trigger_agent_action")
                      .map((t, ti) => (
                        <span
                          key={ti}
                          className="rounded-full bg-white px-2 py-0.5 text-[10px] font-medium text-text-muted shadow-sm"
                        >
                          {t.name}
                        </span>
                      ))}
                  </div>
                )}
              {m.meta?.tools_used
                ?.filter((t) => t.name === "trigger_agent_action" && t.result?.run_id)
                .map((t, ti) => (
                  <InlineRunSteps key={ti} runId={t.result.run_id} action={t.result.action} />
                ))}
              {m.role === "assistant" && m.meta?.sources && m.meta.sources.length > 0 && (
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  <BookOpen size={11} className="text-text-muted" />
                  {m.meta.sources.map((s, si) => (
                    <span
                      key={si}
                      className="rounded-full bg-teal-soft px-2 py-0.5 text-[10px] font-medium text-teal"
                    >
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
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="flex items-center gap-2 border-t border-border px-3 py-3"
      >
        <button
          type="button"
          onClick={toggleSpeak}
          title={speakOn ? "Mute spoken replies" : "Read replies aloud"}
          className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl border transition hover:bg-surface-muted
            ${speakOn ? "border-teal text-teal" : "border-border text-text-muted"}`}
        >
          {speakOn ? <Volume2 size={16} /> : <VolumeX size={16} />}
        </button>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about zones, energy, actions…"
          className="flex-1 rounded-xl border border-border bg-surface-muted/50 px-3 py-2 text-[13px] outline-none focus:border-teal"
        />
        <button
          type="button"
          onClick={toggleRecord}
          disabled={transcribing}
          title={recording ? "Stop & transcribe" : "Speak"}
          className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl border transition hover:bg-surface-muted
            ${recording ? "border-danger text-danger animate-pulse" : "border-border text-text-muted"}`}
        >
          {transcribing ? <Loader2 size={16} className="animate-spin" />
            : recording ? <Square size={14} /> : <Mic size={16} />}
        </button>
        <button type="submit" disabled={busy || !input.trim()} className="btn-primary !px-3 !py-2">
          <Send size={15} />
        </button>
      </form>
    </div>
  );
}
