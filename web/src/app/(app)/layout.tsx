import AppShell from "@/components/shell/AppShell";

// Layout for the authenticated/app area. The landing page (root "/") lives
// outside this group and renders without the AppShell chrome.
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
