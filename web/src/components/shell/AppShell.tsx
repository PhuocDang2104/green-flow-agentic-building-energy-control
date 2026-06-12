"use client";

import { ReactNode } from "react";
import TopBar from "./TopBar";
import MainTabBar from "./MainTabBar";
import Footer from "./Footer";
import ChatbotPanel from "@/components/chatbot/ChatbotPanel";
import { useStateWebSocket } from "@/hooks/useStateWebSocket";

export default function AppShell({ children }: { children: ReactNode }) {
  useStateWebSocket();
  return (
    <div className="min-h-screen">
      <TopBar />
      <MainTabBar />
      <main className="mx-auto max-w-[1480px] px-5">{children}</main>
      <Footer />
      <ChatbotPanel />
    </div>
  );
}
