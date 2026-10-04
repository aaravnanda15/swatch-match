import { useCallback, useEffect, useState } from "react";
import { addSampleHistory, clearSampleHistory, getInsights, imageUrl } from "../api.js";
import { rupees } from "../format.js";
import Icon from "../components/Icon.jsx";

// Real-world colour of each fabric colour name, for the small swatches
const SWATCH = {
  red: "#c62828", maroon: "#7b1f2a", pink: "#e75a9b", orange: "#ef7d22", yellow: "#f2c230",
  gold: "#c9a227", green: "#2e8b57", blue: "#2f5fc4", navy: "#1f2b5c", purple: "#6b3fa0",
  white: "#ffffff", cream: "#f3e7c9", black: "#1d1d1d", grey: "#8a8a8a", brown: "#7a4b2a",
  silver: "#c0c0c0", multicolour: "conic-gradient(#c62828, #f2c230, #2e8b57, #2f5fc4, #6b3fa0, #c62828)",
};
const LANGUAGE_NAMES = { en: "English", hi: "हिंदी", hinglish: "Hinglish", gu: "ગુજરાતી" };

const pct = (x) => (x == null ? "–" : `${Math.round(x * 100)}%`);

// What the shop's enquiries say: how fast staff reply, what buyers want,
// and what they want that the shop does not have (missed demand).
export default function InsightsPage({ active, demoMode }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    getInsights()
      .then((d) => {
        setData(d);
        setError("");
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (active) load();
  }, [active, load]);

  async function run(action) {
    setBusy(true);
    try {
      await action();
      load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (error && !data) return <p className="rounded-xl bg-madder-soft p-3 text-sm text-madder-dark">{error}</p>;
  if (!data) return <p className="text-sm text-muted">Working out insights…</p>;

  const empty = data.total === 0;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="font-display text-2xl font-semibold tracking-tight">Insights</h2>
          <p className="mt-1 text-sm text-muted">Last {data.days} days of enquiries: how fast you reply and what buyers want.</p>
        </div>
      </div>

      {data.sample_count > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-saffron/40 bg-saffron-soft px-3 py-2 text-xs text-[#6e4a10]">
          <p className="flex items-center gap-1.5">
            <Icon name="info" className="h-4 w-4 shrink-0" />
            Includes {data.sample_count} sample enquiries made up for the demo (real matching, made-up buyers and dates).
          </p>
          <button
            type="button"
            disabled={busy}
            onClick={() => run(clearSampleHistory)}
            className="font-semibold underline disabled:opacity-50"
          >
            Clear sample data
          </button>
        </div>
      )}

      {empty ? (
        <div className="rounded-2xl border border-dashed border-line px-5 py-10 text-center">
          <span className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-card text-indigo ring-1 ring-line">
            <Icon name="chart" />
          </span>
          <p className="mt-3 text-sm font-semibold text-ink">No enquiries in the last {data.days} days</p>
          <p className="mt-1 text-sm text-muted">Insights appear as enquiries come in.</p>
          {demoMode && (
            <button
              type="button"
              disabled={busy}
              onClick={() => run(addSampleHistory)}
              className="mt-4 rounded-xl bg-indigo px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              {busy ? "Adding…" : "Load a sample week"}
            </button>
          )}
        </div>
      ) : (
        <>
          {/* Headline numbers */}
          <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label="Enquiries" value={data.total} note={`${data.on_whatsapp} on WhatsApp`} />
            <Stat label="Replied" value={pct(data.reply_rate)} note={`${data.replied} of ${data.total} approved`} />
            <Stat
              label="Typical reply time"
              value={data.median_reply_minutes == null ? "–" : `${Math.round(data.median_reply_minutes)} min`}
              note="median, message to approved reply"
            />
            <Stat
              label="Good match"
              value={pct(data.good_match_rate)}
              note="top result Very close or Similar"
            />
          </dl>

          <div className="grid gap-4 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
            <MissedDemand data={data} />
            <PerDay perDay={data.per_day} />
          </div>

          <section className="rounded-2xl border border-line bg-card p-4">
            <h3 className="font-display text-lg font-semibold tracking-tight">What buyers ask for</h3>
            <div className="mt-3 grid gap-5 md:grid-cols-3">
              <TopList title="Colours" items={data.asked.main_colour} swatch />
              <TopList title="Patterns" items={data.asked.pattern} />
              <TopList title="Types" items={data.asked.garment_type} />
            </div>
            {data.languages.length > 0 && (
              <div className="mt-5 flex flex-wrap items-center gap-1.5 border-t border-line/70 pt-3 text-xs">
                <span className="text-muted">Buyers wrote in:</span>
                {data.languages.map(([lang, n]) => (
                  <span key={lang} className="rounded-full bg-indigo-soft px-2 py-0.5 font-medium text-indigo">
                    {LANGUAGE_NAMES[lang] || lang} · {n}
                  </span>
                ))}
              </div>
            )}
          </section>

          {data.most_offered.length > 0 && (
            <section className="rounded-2xl border border-line bg-card p-4">
              <h3 className="font-display text-lg font-semibold tracking-tight">Designs you offered most</h3>
              <div className="mt-3 flex gap-3 overflow-x-auto pb-1">
                {data.most_offered.map((d) => (
                  <div key={d.design_id} className="w-28 shrink-0">
                    <img src={imageUrl(d.image_file)} alt="" className="h-28 w-28 rounded-xl object-cover" />
                    <p className="mt-1.5 truncate text-xs font-semibold text-ink" title={d.name}>
                      {d.name}
                    </p>
                    <p className="text-[11px] text-muted">
                      offered {d.count}× · {d.quantity_available} left
                    </p>
                  </div>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

function Stat({ label, value, note }) {
  return (
    <div className="rounded-2xl border border-line bg-card px-4 py-3">
      <dt className="text-xs font-medium text-muted">{label}</dt>
      <dd className="mt-1 font-display text-3xl leading-none font-semibold tracking-tight text-ink">{value}</dd>
      <dd className="mt-1.5 text-[11px] text-faint">{note}</dd>
    </div>
  );
}

function MissedDemand({ data }) {
  const max = Math.max(1, ...data.missed_requests.map((m) => m.count));
  const nothing = data.missed_requests.length === 0 && data.out_of_stock_wanted.length === 0;
  return (
    <section className="rounded-2xl border border-madder/25 bg-card p-4">
      <h3 className="flex items-center gap-2 font-display text-lg font-semibold tracking-tight">
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-madder-soft text-madder">
          <Icon name="trend" className="h-4 w-4" />
        </span>
        Missed demand: what to restock
      </h3>
      <p className="mt-1 text-xs text-muted">Buyers asked for these, and nothing in stock fully matched.</p>

      {nothing && <p className="mt-4 text-sm text-muted">Nothing missed. Every request had a full match in stock.</p>}

      {data.missed_requests.length > 0 && (
        <ul className="mt-3 space-y-2.5">
          {data.missed_requests.map((m) => (
            <li key={m.request}>
              <div className="flex items-baseline justify-between gap-2 text-sm">
                <span className="truncate font-medium text-ink first-letter:uppercase">{m.request}</span>
                <span className="shrink-0 text-xs text-muted tabular-nums">
                  asked {m.count}×{m.budget ? ` · under ${rupees(m.budget)}` : ""}
                </span>
              </div>
              <div className="mt-1 h-1.5 rounded-full bg-line/60">
                <div className="h-1.5 rounded-full bg-madder" style={{ width: `${(m.count / max) * 100}%` }} />
              </div>
            </li>
          ))}
        </ul>
      )}

      {data.out_of_stock_wanted.length > 0 && (
        <div className="mt-4 border-t border-line/70 pt-3">
          <p className="text-xs font-semibold text-ink">Wanted, but out of stock</p>
          <ul className="mt-2 space-y-2">
            {data.out_of_stock_wanted.map((d) => (
              <li key={d.design_id} className="flex items-center gap-2.5">
                <img src={imageUrl(d.image_file)} alt="" className="h-9 w-9 shrink-0 rounded-lg object-cover" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-ink">{d.name}</span>
                  <span className="text-[11px] text-muted">
                    {d.design_id} · good match {d.count}× · {d.quantity_available} in stock
                  </span>
                </span>
                {d.quantity_available === 0 && (
                  <span className="shrink-0 rounded-full bg-madder-soft px-2 py-0.5 text-[10px] font-semibold text-madder-dark">
                    Restock
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

// Enquiries per day: one series, so no legend; hover or focus a bar for its value
function PerDay({ perDay }) {
  const max = Math.max(1, ...perDay.map((d) => d.count));
  const label = (iso, short) =>
    new Date(`${iso}T12:00:00`).toLocaleDateString("en-IN", short ? { weekday: "short" } : { weekday: "long", day: "numeric", month: "short" });
  return (
    <section className="rounded-2xl border border-line bg-card p-4">
      <h3 className="font-display text-lg font-semibold tracking-tight">Enquiries per day</h3>
      <div className="mt-4 flex h-40 items-end gap-2" role="list">
        {perDay.map((d, i) => (
          <div
            key={d.date}
            role="listitem"
            tabIndex={0}
            aria-label={`${label(d.date)}: ${d.count} enquiries`}
            className="group relative flex h-full flex-1 flex-col items-center justify-end focus:outline-none"
          >
            {/* Tooltip */}
            <span
              className={`pointer-events-none absolute -top-1 z-10 -translate-y-full rounded-md bg-ink px-2 py-1 text-[11px] whitespace-nowrap text-white opacity-0 shadow transition-opacity group-hover:opacity-100 group-focus:opacity-100 ${
                i < 2 ? "left-0" : i > perDay.length - 3 ? "right-0" : ""
              }`}
            >
              {label(d.date)}: <b>{d.count}</b>
            </span>
            <div
              className="w-full max-w-9 rounded-t-[4px] bg-indigo transition-colors group-hover:bg-madder group-focus:bg-madder"
              style={{ height: `${Math.max(2, (d.count / max) * 100)}%` }}
            />
          </div>
        ))}
      </div>
      <div className="mt-1.5 flex gap-2 border-t border-line pt-1.5">
        {perDay.map((d) => (
          <span key={d.date} className="flex-1 text-center text-[10px] text-muted">
            {label(d.date, true)}
          </span>
        ))}
      </div>
    </section>
  );
}

function TopList({ title, items, swatch }) {
  const max = Math.max(1, ...items.map(([, n]) => n));
  return (
    <div>
      <p className="text-xs font-semibold text-muted">{title}</p>
      {items.length === 0 ? (
        <p className="mt-2 text-xs text-faint">Not enough data yet.</p>
      ) : (
        <ul className="mt-2 space-y-1.5">
          {items.map(([value, n]) => (
            <li key={value} className="flex items-center gap-2 text-sm">
              {swatch && (
                <span
                  className="h-3.5 w-3.5 shrink-0 rounded-full ring-1 ring-line"
                  style={{ background: SWATCH[value] || "#ccc" }}
                />
              )}
              <span className="w-20 shrink-0 truncate text-ink first-letter:uppercase">{value}</span>
              <span className="h-1.5 flex-1 rounded-full bg-line/60">
                <span className="block h-1.5 rounded-full bg-indigo" style={{ width: `${(n / max) * 100}%` }} />
              </span>
              <span className="w-6 shrink-0 text-right text-xs text-muted tabular-nums">{n}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
