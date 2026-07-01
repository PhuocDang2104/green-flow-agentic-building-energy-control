import LiveClock from "./LiveClock";
import SearchBar from "./SearchBar";
import UserMenu from "./UserMenu";
import TutorialEntryButton from "@/components/tutorial/TutorialEntryButton";

export default function TopBar() {
  return (
    <header className="sticky top-0 z-40 h-16 border-b border-border bg-white/85 backdrop-blur">
      <div className="flex h-full items-center gap-4 px-5">
        {/* left: brand (mobile) */}
        <div className="flex items-center gap-2 lg:hidden">
          <img
            src="/assets/landing/greenflow_favicon.png"
            alt="GreenFlow"
            className="h-8 w-8 rounded-xl object-contain"
          />
          <span className="text-[15px] font-semibold">GreenFlow</span>
        </div>

        {/* center: search */}
        <div className="flex flex-1 justify-center">
          <SearchBar />
        </div>

        {/* right: tutorial + virtual clock + user menu */}
        <TutorialEntryButton />
        <LiveClock />
        <UserMenu />
      </div>
    </header>
  );
}
