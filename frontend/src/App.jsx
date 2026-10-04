import { useEffect, useState } from "react";
import { getHealth } from "./api.js";
import Icon, { Logo } from "./components/Icon.jsx";
import EnquiryPage from "./pages/EnquiryPage.jsx";
import CataloguePage from "./pages/CataloguePage.jsx";
import AuditLogPage from "./pages/AuditLogPage.jsx";

const TABS = [
  { id: "enquiry", label: "Enquiry", icon: "enquiry" },
  { id: "catalogue", label: "Catalogue", icon: "catalogue" },
  { id: "log", label: "Log", icon: "log" },
];

export default function App() {
  const [tab, setTab] = useState("enquiry");
  const [health, setHealth] = useState(null);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth({ status: "down" }));
  }, []);

  return (
    <div className="min-h-screen">
      <header className="weave sticky top-0 z-20 border-b border-line/80 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-3">
          <Logo className="h-8 w-8 shrink-0" />
          <div className="min-w-0 flex-1">
            <h1 className="font-display text-xl leading-tight font-semibold tracking-tight text-ink">Swatch Match</h1>
            <p className="truncate text-xs text-muted">Buyer enquiry → shortlist from your own stock</p>
          </div>
          <StatusPill health={health} />
        </div>

        {/* Tabs at the top on wider screens */}
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
            </button>
          ))}
        </nav>
      </header>

      {/* Pages stay mounted so an enquiry in progress survives a tab switch */}
      <main className="mx-auto max-w-5xl px-4 pt-5 pb-28 md:pb-12">
        <div hidden={tab !== "enquiry"}>
          <EnquiryPage />
        </div>
        <div hidden={tab !== "catalogue"}>
          <CataloguePage />
        </div>
        <div hidden={tab !== "log"}>
          <AuditLogPage active={tab === "log"} />
        </div>
      </main>

      {/* Bottom tab bar on phones: easy to reach with a thumb */}
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
                className={`flex h-7 w-12 items-center justify-center rounded-full transition-colors ${
                  tab === t.id ? "bg-madder-soft" : ""
                }`}
              >
                <Icon name={t.icon} className="h-5 w-5" />
              </span>
              {t.label}
            </button>
          ))}
        </div>
      </nav>
    </div>
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
