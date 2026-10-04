import { useCallback, useEffect, useRef, useState } from "react";
import {
  dismissInboxItem,
  getDemoScenarios,
  getInbox,
  getInboxItem,
  samplePhotoUrl,
  simulateBuyer,
  uploadUrl,
} from "../api.js";
import { shortDateTime } from "../format.js";
import Icon from "../components/Icon.jsx";
import ImageViewer from "../components/ImageViewer.jsx";
import Shortlist from "../components/Shortlist.jsx";

const POLL_MS = 10000; // check for new WhatsApp enquiries every 10 seconds
const FAST_POLL_MS = 1500; // right after a simulated message, check often

const STATUS = {
  new: { text: "New", style: "bg-madder text-white" },
  sent: { text: "Replied", style: "bg-leaf-soft text-leaf" },
  dismissed: { text: "Dismissed", style: "bg-line/70 text-muted" },
};

// WhatsApp enquiries, already run through the agent. Staff open one, check the
// shortlist and reply. Polls in the background so the tab badge stays current.
export default function InboxPage({ active, onNewCount, demoMode }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState(null);
  const [waiting, setWaiting] = useState(null); // simulated buyer we are waiting for
  const waitingRef = useRef(null);
  waitingRef.current = waiting;

  const load = useCallback(() => {
    getInbox()
      .then((data) => {
        setItems(data.items);
        onNewCount(data.new);
        setError("");
        // A simulated buyer's message has arrived: open it
        const w = waitingRef.current;
        if (w) {
          const arrived = data.items.find((i) => i.id > w.afterId && (i.buyer_name || "").startsWith(w.buyer));
          if (arrived && !w.openedId) {
            setOpenId(arrived.id);
            setWaiting({ ...w, openedId: arrived.id });
          }
        }
      })
      .catch((e) => setError(e.message));
  }, [onNewCount]);

  // Poll fast for a short while after simulating (catches photo + text merging too)
  useEffect(() => {
    if (!waiting) return;
    const timer = setInterval(load, FAST_POLL_MS);
    const stop = setTimeout(() => setWaiting(null), 30000);
    return () => {
      clearInterval(timer);
      clearTimeout(stop);
    };
  }, [waiting?.buyer, waiting?.afterId, load]); // eslint-disable-line react-hooks/exhaustive-deps

  async function simulate(scenario) {
    const afterId = Math.max(0, ...(items || []).map((i) => i.id));
    setWaiting({ buyer: scenario.buyer, afterId, openedId: null });
    try {
      await simulateBuyer(scenario.id);
    } catch (e) {
      setError(e.message);
      setWaiting(null);
    }
  }

  useEffect(() => {
    load();
    const timer = setInterval(load, POLL_MS);
    return () => clearInterval(timer);
  }, [load]);

  // Refresh straight away when the tab is opened
  useEffect(() => {
    if (active) load();
  }, [active, load]);

  if (error && items === null) return <p className="rounded-xl bg-madder-soft p-3 text-sm text-madder-dark">{error}</p>;
  if (items === null) return <p className="text-sm text-muted">Loading inbox…</p>;

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:items-start">
      {/* List: always on desktop, hidden on phones while an enquiry is open */}
      <div className={`min-w-0 space-y-4 ${openId ? "hidden lg:block" : ""}`}>
        <div>
          <h2 className="font-display text-2xl font-semibold tracking-tight">Inbox</h2>
          <p className="mt-1 text-sm text-muted">
            WhatsApp enquiries, already matched. Open one, check it, then reply.
          </p>
        </div>
        {demoMode && <DemoPanel onSimulate={simulate} waiting={waiting} />}
        {items.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-line px-5 py-10 text-center">
            <span className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-card text-indigo ring-1 ring-line">
              <Icon name="inbox" />
            </span>
            <p className="mt-3 text-sm font-semibold text-ink">No WhatsApp enquiries yet</p>
            <p className="mt-1 text-sm text-muted">
              {demoMode
                ? "Tap a buyer above to simulate their WhatsApp message."
                : "When a buyer messages your WhatsApp number, it appears here."}
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-line/70 overflow-hidden rounded-2xl border border-line bg-card">
            {items.map((item) => (
              <InboxRow key={item.id} item={item} selected={item.id === openId} onOpen={() => setOpenId(item.id)} />
            ))}
          </ul>
        )}
      </div>

      <div className={`min-w-0 ${openId ? "" : "hidden lg:block"}`}>
        {openId ? (
          <InboxDetail
            key={openId}
            id={openId}
            signature={(() => {
              const it = items.find((i) => i.id === openId);
              return it ? `${it.mode}|${it.text}|${it.status}` : "";
            })()}
            onBack={() => setOpenId(null)}
            onChanged={load}
          />
        ) : (
          <div className="hidden rounded-2xl border border-dashed border-line px-5 py-16 text-center text-sm text-muted lg:block">
            Choose an enquiry on the left.
          </div>
        )}
      </div>
    </div>
  );
}

function InboxRow({ item, selected, onOpen }) {
  const status = STATUS[item.status] || STATUS.new;
  const unsupported = item.mode === "unsupported";
  const name = item.buyer_name || item.buyer_phone_masked;
  return (
    <li>
      <button
        type="button"
        onClick={onOpen}
        className={`flex w-full items-center gap-3 px-3 py-3 text-left transition-colors hover:bg-paper ${
          selected ? "bg-indigo-soft/50" : ""
        }`}
      >
        {item.image_file ? (
          <img src={uploadUrl(item.image_file)} alt="" className="h-12 w-12 shrink-0 rounded-xl object-cover" />
        ) : (
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-indigo-soft font-display text-lg font-semibold text-indigo">
            {name.trim()[0]?.toUpperCase() || "?"}
          </span>
        )}
        <span className="min-w-0 flex-1">
          <span className="flex items-baseline justify-between gap-2">
            <span className={`truncate text-sm ${item.status === "new" ? "font-semibold text-ink" : "text-ink"}`}>
              {name}
            </span>
            <span className="shrink-0 text-[11px] text-faint">{shortDateTime(item.created_at)}</span>
          </span>
          <span className="mt-0.5 flex items-center gap-2">
            <span className={`truncate text-[13px] ${unsupported ? "text-faint italic" : "text-muted"}`}>
              {item.text || (item.image_file ? "Photo" : "")}
            </span>
            <span className={`ml-auto shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ${status.style}`}>
              {status.text}
            </span>
          </span>
        </span>
      </button>
    </li>
  );
}

function InboxDetail({ id, signature, onBack, onChanged }) {
  const [item, setItem] = useState(null);
  const [error, setError] = useState("");
  const [viewing, setViewing] = useState(null);

  const load = useCallback(() => {
    getInboxItem(id)
      .then(setItem)
      .catch((e) => setError(e.message));
  }, [id]);

  // Reload when the list shows this enquiry changed (e.g. a follow-up text merged in)
  useEffect(load, [load, signature]);

  async function dismiss() {
    try {
      await dismissInboxItem(id);
      load();
      onChanged();
    } catch (e) {
      setError(e.message);
    }
  }

  if (error) return <p className="rounded-xl bg-madder-soft p-3 text-sm text-madder-dark">{error}</p>;
  if (!item) return <p className="text-sm text-muted">Loading…</p>;

  const status = STATUS[item.status] || STATUS.new;
  const windowOpen = item.hours_left > 0;

  return (
    <div className="space-y-4">
      <button
        type="button"
        onClick={onBack}
        className="flex items-center gap-1 text-sm font-medium text-muted hover:text-ink lg:hidden"
      >
        <Icon name="back" className="h-4 w-4" />
        Inbox
      </button>

      {/* Who and when */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate font-display text-xl font-semibold tracking-tight">
            {item.buyer_name || "WhatsApp buyer"}
          </h2>
          <p className="text-sm text-muted">
            +{item.buyer_phone} · {shortDateTime(item.created_at)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${status.style}`}>{status.text}</span>
          {item.status === "new" && (
            <button
              type="button"
              onClick={dismiss}
              className="rounded-lg border border-line bg-card px-3 py-1 text-xs font-medium text-muted hover:text-ink"
            >
              Dismiss
            </button>
          )}
        </div>
      </div>

      {item.status === "new" && (
        <p
          className={`flex items-center gap-1.5 text-xs ${windowOpen ? "text-muted" : "font-medium text-madder"}`}
        >
          <Icon name="info" className="h-3.5 w-3.5" />
          {windowOpen
            ? `Reply within ${Math.floor(item.hours_left)} h ${Math.round((item.hours_left % 1) * 60)} min (WhatsApp's 24-hour window).`
            : "WhatsApp's 24-hour reply window has closed. Reply from your phone instead."}
        </p>
      )}

      {/* What the buyer sent, as a chat bubble */}
      <div className="max-w-[88%] rounded-2xl rounded-tl-md border border-line bg-card p-2 shadow-sm">
        {item.image_file && (
          <button type="button" onClick={() => setViewing({ image_file: item.image_file, name: "Buyer's photo", upload: true })}>
            <img src={uploadUrl(item.image_file)} alt="Buyer's photo" className="max-h-56 rounded-xl object-cover" />
          </button>
        )}
        {item.text && (
          <p className={`px-1.5 py-1 text-[15px] ${item.mode === "unsupported" ? "text-faint italic" : "text-ink"}`}>
            {item.text}
          </p>
        )}
      </div>

      {item.answer ? (
        <Shortlist
          key={`${item.mode}|${item.text}`}
          result={item.answer}
          onOpenImage={setViewing}
          whatsapp={{
            enquiryId: item.id,
            status: item.status,
            hoursLeft: item.hours_left,
            buyerName: item.buyer_name,
            onSent: () => {
              load();
              onChanged();
            },
          }}
        />
      ) : (
        <p className="rounded-xl border border-dashed border-line px-3 py-5 text-center text-sm text-muted">
          Nothing to match. Reply from your phone, or Dismiss.
        </p>
      )}

      <ImageViewer design={viewing} onClose={() => setViewing(null)} />
    </div>
  );
}

// Demo mode: pretend buyers message the shop, to show the WhatsApp flow live
function DemoPanel({ onSimulate, waiting }) {
  const [scenarios, setScenarios] = useState([]);
  useEffect(() => {
    getDemoScenarios().then(setScenarios).catch(() => {});
  }, []);
  if (scenarios.length === 0) return null;

  return (
    <section className="min-w-0 rounded-2xl border border-indigo/25 bg-indigo-soft/50 p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-sm font-semibold text-indigo">
          <Icon name="sparkle" className="h-4 w-4" />
          Simulate a WhatsApp buyer
        </p>
        <span className="rounded-full bg-card px-2 py-0.5 text-[10px] font-semibold text-indigo ring-1 ring-indigo/20">
          Demo · nothing is really sent
        </span>
      </div>
      <div className="mt-2.5 grid grid-cols-1 gap-2 sm:grid-cols-2">
        {scenarios.map((s) => {
          const busy = waiting && !waiting.openedId && waiting.buyer === s.buyer;
          return (
            <button
              key={s.id}
              type="button"
              onClick={() => onSimulate(s)}
              disabled={Boolean(waiting && !waiting.openedId)}
              className="flex w-full min-w-0 items-center gap-2.5 rounded-xl bg-card p-2 text-left ring-1 ring-line transition hover:ring-indigo/50 disabled:opacity-60"
            >
              {s.photo ? (
                <img src={samplePhotoUrl(s.photo)} alt="" className="h-10 w-10 shrink-0 rounded-lg object-cover" />
              ) : (
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-indigo-soft font-display font-semibold text-indigo">
                  {s.buyer[0]}
                </span>
              )}
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px] font-semibold text-ink">{s.buyer}</span>
                <span className="block truncate text-xs text-muted">
                  <span className="font-medium text-indigo">{s.language}</span> ·{" "}
                  {busy ? "sending on WhatsApp…" : s.text || "photo"}
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
