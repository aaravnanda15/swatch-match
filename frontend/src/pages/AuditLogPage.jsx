import { useEffect, useState } from "react";
import { getAudit, getDesigns, imageUrl, uploadUrl } from "../api.js";
import { copyText } from "../clipboard.js";
import { shortDateTime } from "../format.js";
import Icon from "../components/Icon.jsx";

const LANGUAGE_NAMES = { en: "English", hi: "हिंदी", hinglish: "Hinglish", gu: "ગુજરાતી" };

// Every reply staff approved, newest first. Reloads each time the tab opens.
export default function AuditLogPage({ active }) {
  const [entries, setEntries] = useState(null);
  const [designs, setDesigns] = useState({});
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!active) return;
    Promise.all([getAudit(), getDesigns()])
      .then(([log, list]) => {
        setEntries(log);
        setDesigns(Object.fromEntries(list.map((d) => [d.design_id, d])));
        setError("");
      })
      .catch((e) => setError(e.message));
  }, [active]);

  if (error) return <p className="rounded-xl bg-madder-soft p-3 text-sm text-madder-dark">{error}</p>;
  if (entries === null) return <p className="text-sm text-muted">Loading log…</p>;

  const query = search.trim().toLowerCase();
  const shown = entries.filter((e) => {
    if (!query) return true;
    return [e.enquiry_text, e.reply_text, ...e.picked].join(" ").toLowerCase().includes(query);
  });

  return (
    <div className="space-y-4">
      <div>
        <h2 className="font-display text-2xl font-semibold tracking-tight">Log</h2>
        <p className="mt-1 text-sm text-muted">
          Every reply staff approved, newest first. Swatch Match never sends anything itself.
        </p>
      </div>

      {entries.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-line px-5 py-10 text-center">
          <span className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-card text-indigo ring-1 ring-line">
            <Icon name="log" />
          </span>
          <p className="mt-3 text-sm font-semibold text-ink">No approved replies yet</p>
          <p className="mt-1 text-sm text-muted">Approve a reply on the Enquiry tab and it shows up here.</p>
        </div>
      ) : (
        <>
          <label className="relative block">
            <Icon name="search" className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-faint" />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search messages, replies or design IDs"
              className="w-full rounded-xl border border-line bg-card py-2.5 pr-3 pl-9 text-sm placeholder:text-faint focus:border-indigo focus:outline-none"
            />
          </label>
          <p className="text-xs text-faint">
            {shown.length} of {entries.length} approved replies
          </p>

          {/* Phones: cards */}
          <div className="space-y-3 md:hidden">
            {shown.map((e) => (
              <EntryCard key={e.id} entry={e} designs={designs} />
            ))}
          </div>

          {/* Wider screens: a table */}
          <div className="hidden overflow-hidden rounded-2xl border border-line bg-card md:block">
            <table className="w-full text-left text-sm">
              <thead className="bg-paper text-xs text-muted">
                <tr>
                  <th className="px-3 py-2.5 font-medium">When</th>
                  <th className="px-3 py-2.5 font-medium">Buyer asked</th>
                  <th className="px-3 py-2.5 font-medium">Offered</th>
                  <th className="px-3 py-2.5 font-medium">Approved reply</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/70 align-top">
                {shown.map((e) => (
                  <tr key={e.id}>
                    <td className="px-3 py-3 whitespace-nowrap">
                      <p className="font-medium text-ink">{shortDateTime(e.created_at)}</p>
                      <p className="mt-1 text-xs text-faint">
                        #{e.id} · {LANGUAGE_NAMES[e.language] || e.language}
                      </p>
                    </td>
                    <td className="max-w-56 px-3 py-3">
                      <Enquiry entry={e} />
                    </td>
                    <td className="px-3 py-3">
                      <Picked entry={e} designs={designs} />
                    </td>
                    <td className="w-[38%] px-3 py-3">
                      <Reply text={e.reply_text} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function EntryCard({ entry, designs }) {
  return (
    <article className="space-y-3 rounded-2xl border border-line bg-card p-3">
      <div className="flex items-center justify-between text-xs">
        <span className="font-semibold text-ink">{shortDateTime(entry.created_at)}</span>
        <span className="text-faint">
          #{entry.id} · {LANGUAGE_NAMES[entry.language] || entry.language}
        </span>
      </div>
      <Enquiry entry={entry} />
      <Picked entry={entry} designs={designs} />
      <Reply text={entry.reply_text} />
    </article>
  );
}

function Enquiry({ entry }) {
  return (
    <div className="flex items-start gap-2">
      {entry.enquiry_image && (
        <img
          src={uploadUrl(entry.enquiry_image)}
          alt="Buyer's photo"
          className="h-12 w-12 shrink-0 rounded-lg object-cover ring-1 ring-line"
        />
      )}
      <p className="min-w-0 text-sm break-words text-ink">
        {entry.enquiry_text ? `“${entry.enquiry_text}”` : <span className="text-muted">Photo only</span>}
      </p>
    </div>
  );
}

function Picked({ entry, designs }) {
  if (entry.picked.length === 0) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-indigo-soft px-2 py-0.5 text-xs font-medium text-indigo">
        <Icon name="question" className="h-3.5 w-3.5" />
        Asked a question
      </span>
    );
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {entry.picked.map((id) => {
        const d = designs[id];
        return (
          <span
            key={id}
            title={d?.name}
            className="flex items-center gap-1.5 rounded-full bg-paper py-0.5 pr-2 pl-0.5 text-xs font-medium text-ink ring-1 ring-line"
          >
            {d ? (
              <img src={imageUrl(d.image_file)} alt="" className="h-5 w-5 rounded-full object-cover" />
            ) : (
              <span className="h-5 w-5 rounded-full bg-line" />
            )}
            {id}
          </span>
        );
      })}
    </div>
  );
}

function Reply({ text }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  async function copy() {
    if (await copyText(text)) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  return (
    <div>
      <p className={`text-[13px] leading-relaxed whitespace-pre-line text-muted ${open ? "" : "line-clamp-3"}`}>
        {text}
      </p>
      <div className="mt-1.5 flex gap-3 text-xs font-semibold">
        <button type="button" onClick={() => setOpen(!open)} className="text-indigo">
          {open ? "Show less" : "Show all"}
        </button>
        <button type="button" onClick={copy} className="flex items-center gap-1 text-madder">
          <Icon name={copied ? "check" : "copy"} className="h-3.5 w-3.5" />
          {copied ? "Copied" : "Copy again"}
        </button>
      </div>
    </div>
  );
}
