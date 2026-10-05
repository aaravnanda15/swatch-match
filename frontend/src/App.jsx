import { useCallback, useEffect, useState } from "react";
import { getHealth } from "./api.js";
import Icon, { Logo } from "./components/Icon.jsx";
import AboutSheet from "./components/AboutSheet.jsx";
import EnquiryPage from "./pages/EnquiryPage.jsx";
import CataloguePage from "./pages/CataloguePage.jsx";
import AuditLogPage from "./pages/AuditLogPage.jsx";
import InboxPage from "./pages/InboxPage.jsx";
import InsightsPage from "./pages/InsightsPage.jsx";
import BuyerChat from "./pages/BuyerChat.jsx";

const ALL_TABS = [
  { id: "inbox", label: "Inbox", icon: "inbox", whatsappOnly: true },
  { id: "enquiry", label: "Enquiry", icon: "enquiry" },
  { id: "catalogue", label: "Catalogue", icon: "catalogue" },
  { id: "insights", label: "Insights", icon: "chart" },
  { id: "log", label: "Log", icon: "log" },
];

export default function App() {
  const [tab, setTab] = useState("enquiry");
  const [health, setHealth] = useState(null);
  const [newCount, setNewCount] = useState(0); // WhatsApp enquiries waiting
  const [aboutOpen, setAboutOpen] = useState(false);
  const [hash, setHash] = useState(window.location.hash); // "#buyer" = buyer chat page

  useEffect(() => {
    const onHash = () => setHash(window.location.hash);
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  const onNewCount = useCallback((n) => setNewCount(n), []);

  useEffect(() => {
    document.title = newCount > 0 ? `(${newCount}) Swatch Match` : "Swatch Match";
  }, [newCount]);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth({ status: "down" }));
  }, []);

  if (hash === "#buyer") return <BuyerChat />; // buyers never see the staff screens

  const whatsapp = Boolean(health?.whatsapp_configured);
  const TABS = ALL_TABS.filter((t) => whatsapp || !t.whatsappOnly);

  return (
    <div className="min-h-screen">
      <header className="weave sticky top-0 z-20 border-b border-line/80 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-3">
          <Logo className="h-8 w-8 shrink-0" />
          <div className="min-w-0 flex-1">
            <h1 className="font-display text-xl leading-tight font-semibold tracking-tight text-ink">Swatch Match</h1>
            <p className="truncate text-xs text-muted">Buyer enquiry → shortlist from your own stock</p>
          </div>
          <button
            type="button"
            onClick={() => setAboutOpen(true)}
            className="flex shrink-0 items-center gap-1 rounded-full border border-line bg-card px-2.5 py-1 text-xs font-medium text-muted hover:text-ink"
          >
            <Icon name="info" className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">How it works</span>
          </button>
          <StatusPill health={health} />
        </div>

        <nav className="mx-auto hidden max-w-5xl gap-1 px-4 md:flex" aria-label="Sections">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              aria-current={tab === t.id ? "page" : undefined}
              className={`flex items-center gap-2 border-b-2 px-3 pt-1 pb-2.5 text-sm font-medium transition-colors ${
                tab === t.id ? "border-madder text-madder" : "border-transparent text-muted hover:text-ink"
              }`}
            >
              <Icon name={t.icon} className="h-4 w-4" />
              {t.label}
              {t.id === "inbox" && newCount > 0 && <Badge n={newCount} />}
            </button>
          ))}
        </nav>
      </header>

      {/* keep pages mounted so a half-done enquiry survives a tab switch */}
      <main className="mx-auto max-w-5xl px-4 pt-5 pb-28 md:pb-12">
        {whatsapp && (
          <div hidden={tab !== "inbox"}>
            <InboxPage active={tab === "inbox"} onNewCount={onNewCount} demoMode={Boolean(health?.demo_mode)} />
          </div>
        )}
        <div hidden={tab !== "enquiry"}>
          <EnquiryPage />
        </div>
        <div hidden={tab !== "catalogue"}>
          <CataloguePage />
        </div>
        <div hidden={tab !== "insights"}>
          <InsightsPage active={tab === "insights"} demoMode={Boolean(health?.demo_mode)} />
        </div>
        <div hidden={tab !== "log"}>
          <AuditLogPage active={tab === "log"} />
        </div>
      </main>

      <AboutSheet open={aboutOpen} onClose={() => setAboutOpen(false)} />

      <nav
        className="pb-safe fixed inset-x-0 bottom-0 z-20 border-t border-line bg-card/95 backdrop-blur md:hidden"
        aria-label="Sections"
      >
        <div className="mx-auto flex max-w-md">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              aria-current={tab === t.id ? "page" : undefined}
              className={`flex flex-1 flex-col items-center gap-0.5 pt-2 pb-1 text-[11px] font-medium ${
                tab === t.id ? "text-madder" : "text-muted"
              }`}
            >
              <span
                className={`relative flex h-7 w-12 items-center justify-center rounded-full transition-colors ${
                  tab === t.id ? "bg-madder-soft" : ""
                }`}
              >
                <Icon name={t.icon} className="h-5 w-5" />
                {t.id === "inbox" && newCount > 0 && (
                  <span className="absolute -top-1 right-1">
                    <Badge n={newCount} />
                  </span>
                )}
              </span>
              {t.label}
            </button>
          ))}
        </div>
      </nav>
    </div>
  );
}

function Badge({ n }) {
  return (
    <span className="ml-0.5 inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-madder px-1 text-[10px] leading-none font-bold text-white">
      {n > 99 ? "99+" : n}
    </span>
  );
}

function StatusPill({ health }) {
  let dot = "bg-faint";
  let text = "Checking…";
  let title = "";
  if (health?.status === "down") {
    dot = "bg-madder";
    text = "Offline";
    title = "Cannot reach the server";
  } else if (health?.status === "ok") {
    dot = health.llm_configured ? "bg-leaf" : "bg-saffron";
    text = health.llm_configured ? "AI on" : "Basic mode";
    title = health.llm_configured
      ? `${health.designs} designs · Gemini is used for reading messages`
      : `${health.designs} designs · No AI key: keyword list and photo matching only`;
  }
  return (
    <span
      title={title}
      className="flex shrink-0 items-center gap-1.5 rounded-full border border-line bg-card px-2.5 py-1 text-xs font-medium text-muted"
    >
      <span className={`h-2 w-2 rounded-full ${dot}`} />
      {text}
    </span>
  );
}
