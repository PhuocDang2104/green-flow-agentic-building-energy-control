"use client";

import { ReactNode } from "react";
import TopBar from "./TopBar";
import MainTabBar from "./MainTabBar";
import SideBar from "./SideBar";
import Footer from "./Footer";
import ChatbotPanel from "@/components/chatbot/ChatbotPanel";
import { useStateWebSocket } from "@/hooks/useStateWebSocket";

export default function AppShell({ children }: { children: ReactNode }) {
  useStateWebSocket();
  return (
    <div className="flex min-h-screen">
      {/* desktop sidebar */}
      <SideBar />

      {/* content column */}
      <div className="flex min-w-0 flex-1 flex-col lg:pl-[248px]">
        <TopBar />
        <main className="mx-auto w-full max-w-[1400px] flex-1 px-5 pb-24 lg:pb-8">
          {children}
        </main>
        <Footer />
      </div>

      {/* mobile floating nav + global chatbot */}
      <MainTabBar />
      <ChatbotPanel />
    </div>
  );
}
