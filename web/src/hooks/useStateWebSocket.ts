"use client";

import { useEffect, useRef } from "react";
import { wsUrl } from "@/lib/api";
import { useAppStore } from "@/stores/appStore";

/** Subscribe to the replay/state WebSocket and feed the app store. */
export function useStateWebSocket() {
  const buildingId = useAppStore((s) => s.buildingId);
  const setReplay = useAppStore((s) => s.setReplay);
  const setWsConnected = useAppStore((s) => s.setWsConnected);
  const retryRef = useRef(0);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let closed = false;

    const connect = () => {
      const url = wsUrl(buildingId);
      if (!url) return;
      try {
        ws = new WebSocket(url);
      } catch {
        return;
      }
      ws.onopen = () => {
        retryRef.current = 0;
        setWsConnected(true);
      };
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "state_tick") {
            setReplay(msg.timestamp, msg.zones || {}, msg.building || {}, msg.weather || undefined);
          }
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onclose = () => {
        setWsConnected(false);
        if (!closed && retryRef.current < 3) {
          retryRef.current += 1;
          setTimeout(connect, 2000 * retryRef.current);
        }
      };
    };

    connect();
    return () => {
      closed = true;
      ws?.close();
    };
  }, [buildingId, setReplay, setWsConnected]);
}
