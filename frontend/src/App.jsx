import { useEffect, useState } from "react";
import { getHealth } from "./api.js";
import EnquiryPage from "./pages/EnquiryPage.jsx";
import CataloguePage from "./pages/CataloguePage.jsx";
import AuditLogPage from "./pages/AuditLogPage.jsx";

const TABS = [
  { id: "enquiry", label: "Enquiry" },
  { id: "catalogue", label: "Catalogue" },
  { id: "log", label: "Log" },
];

export default function App() {
  const [tab, setTab] = useState("enquiry");
  const [health, setHealth] = useState(null);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth({ status: "down" }));
  }, []);

  return (
    <div className="mx-auto flex min-h-screen max-w-2xl flex-col">
      <header className="sticky top-0 z-10 border-b border-stone-200 bg-white px-4 py-3">
        <h1 className="text-lg font-semibold text-stone-900">Swatch Match</h1>
        <p className="text-xs text-stone-500">
          Server:{" "}
          {health === null ? "checking..." : health.status === "ok" ? "connected" : "not reachable"}
        </p>
      </header>

      {/* pb-20 leaves room for the bottom tab bar */}
      <main className="flex-1 px-4 py-4 pb-20">
        {tab === "enquiry" && <EnquiryPage />}
        {tab === "catalogue" && <CataloguePage />}
        {tab === "log" && <AuditLogPage />}
      </main>

      {/* Bottom tab bar: easy to reach with a thumb on a phone */}
      <nav className="fixed inset-x-0 bottom-0 border-t border-stone-200 bg-white">
        <div className="mx-auto flex max-w-2xl">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex-1 py-3 text-sm font-medium ${
                tab === t.id ? "text-rose-700" : "text-stone-500"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </nav>
    </div>
  );
}
