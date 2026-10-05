import { useEffect, useState } from "react";
import { getReadyReplies, imageUrl, sendAllWhatsApp, uploadUrl } from "../api.js";
import { shortDateTime } from "../format.js";
import DraftNote from "./DraftNote.jsx";
import Icon from "./Icon.jsx";

// One screen for every chat waiting on the seller: what the buyer said, the
// reply ready to go, and one button to send them all. Nothing goes out until
// the seller confirms.
export default function ReplyAll({ onClose, onSent, onOpenChat }) {
  const [items, setItems] = useState(null);
  const [texts, setTexts] = useState({});
  const [skipped, setSkipped] = useState({});
  const [results, setResults] = useState({});
  const [confirming, setConfirming] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getReadyReplies()
      .then((data) => {
        setItems(data.items);
        setTexts(Object.fromEntries(data.items.map((i) => [i.enquiry_id, i.text])));
      })
      .catch((e) => setError(e.message));
  }, []);

  if (error && items === null) return <p className="rounded-xl bg-madder-soft p-3 text-sm text-madder-dark">{error}</p>;
  if (items === null) return <p className="text-sm text-muted">Loading replies…</p>;

  const open = (i) => i.hours_left > 0 && !results[i.enquiry_id]?.ok;
  const toSend = items.filter((i) => open(i) && !skipped[i.enquiry_id] && (texts[i.enquiry_id] || "").trim());
  const photoCount = toSend.reduce((n, i) => n + Math.min(i.picked.length, 5), 0);

  async function send(list) {
    setSending(true);
    setError("");
    try {
      const r = await sendAllWhatsApp(
        list.map((i) => ({
          enquiry_id: i.enquiry_id,
          text: texts[i.enquiry_id],
          picked: i.picked.map((d) => d.design_id),
          language: i.language,
        })),
      );
      setResults((old) => ({ ...old, ...Object.fromEntries(r.results.map((x) => [x.enquiry_id, x])) }));
      setConfirming(false);
      onSent();
    } catch (e) {
      setError(e.message);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 pb-44 md:pb-28">
      <div className="flex items-start gap-3">
        <button
          type="button"
          onClick={onClose}
          aria-label="Back to inbox"
          className="mt-1 rounded-full p-1.5 text-muted hover:bg-card hover:text-ink"
        >
          <Icon name="back" className="h-5 w-5" />
        </button>
        <div>
          <h2 className="font-display text-2xl font-semibold tracking-tight">Reply to all</h2>
          <p className="mt-1 text-sm text-muted">
            Every buyer waiting on you, with what they said and the reply ready to go. Edit anything, untick a buyer to
            leave them for later, then send all at once.
          </p>
        </div>
      </div>

      {items.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-line px-5 py-10 text-center">
          <span className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-leaf-soft text-leaf">
            <Icon name="check" strokeWidth={2.2} />
          </span>
          <p className="mt-3 text-sm font-semibold text-ink">All caught up</p>
          <p className="mt-1 text-sm text-muted">No buyer is waiting for a reply.</p>
        </div>
      ) : (
        <ul className="space-y-3">
          {items.map((item) => (
            <ReadyCard
              key={item.enquiry_id}
              item={item}
              text={texts[item.enquiry_id] || ""}
              onText={(t) => setTexts((old) => ({ ...old, [item.enquiry_id]: t }))}
              skipped={!!skipped[item.enquiry_id]}
              onSkip={() => setSkipped((old) => ({ ...old, [item.enquiry_id]: !old[item.enquiry_id] }))}
              result={results[item.enquiry_id]}
              sending={sending}
              onSendOne={() => send([item])}
              onOpenChat={() => onOpenChat(item.enquiry_id)}
            />
          ))}
        </ul>
      )}

      {toSend.length > 0 && (
        <div className="fixed inset-x-0 bottom-[calc(4rem+max(0.5rem,env(safe-area-inset-bottom)))] z-20 border-t border-line bg-paper/95 px-4 py-3 backdrop-blur md:bottom-0">
          <div className="mx-auto max-w-3xl">
            {confirming ? (
              <div className="flex flex-wrap items-center gap-2">
                <p className="min-w-0 flex-1 text-sm text-ink">
                  Send <span className="font-semibold">{toSend.length}</span> {toSend.length === 1 ? "reply" : "replies"}
                  {photoCount > 0 && ` and ${photoCount} design ${photoCount === 1 ? "photo" : "photos"}`} to{" "}
                  {toSend.map((i) => i.buyer_name || "buyer").join(", ")}?
                </p>
                <button
                  type="button"
                  onClick={() => send(toSend)}
                  disabled={sending}
                  className="flex items-center gap-2 rounded-xl bg-leaf px-4 py-2.5 text-sm font-semibold text-white hover:bg-leaf/90 disabled:opacity-50"
                >
                  <Icon name="send" className="h-4 w-4" />
                  {sending ? "Sending…" : "Yes, send"}
                </button>
                <button
                  type="button"
                  onClick={() => setConfirming(false)}
                  disabled={sending}
                  className="rounded-xl border border-line bg-card px-4 py-2.5 text-sm font-medium text-muted"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setConfirming(true)}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-leaf py-3 text-sm font-semibold text-white shadow-sm hover:bg-leaf/90"
              >
                <Icon name="send" className="h-4 w-4" />
                Send all {toSend.length} {toSend.length === 1 ? "reply" : "replies"}
              </button>
            )}
            {error && <p className="mt-1.5 text-sm text-madder">{error}</p>}
          </div>
        </div>
      )}
    </div>
  );
}

function ReadyCard({ item, text, onText, skipped, onSkip, result, sending, onSendOne, onOpenChat }) {
  const closed = item.hours_left <= 0;
  const done = result?.ok;
  const src = (ref) => {
    const [kind, name] = ref.split(":");
    return kind === "upload" ? uploadUrl(name) : imageUrl(name);
  };

  return (
    <li
      className={`rounded-2xl border bg-card p-3 transition-opacity sm:p-4 ${
        done ? "border-leaf/40" : "border-line"
      } ${skipped || closed ? "opacity-60" : ""}`}
    >
      <div className="flex items-center gap-2">
        {!done && !closed && (
          <input
            type="checkbox"
            checked={!skipped}
            onChange={onSkip}
            aria-label={`Include ${item.buyer_name || "this buyer"} in Send all`}
            className="h-4 w-4 accent-[var(--color-leaf)]"
          />
        )}
        <button type="button" onClick={onOpenChat} className="min-w-0 flex-1 text-left">
          <span className="block truncate text-sm font-semibold text-ink hover:underline">
            {item.buyer_name || item.buyer_phone_masked}
          </span>
          <span className="block text-[11px] text-faint">
            {item.buyer_phone_masked} · {shortDateTime(item.last_at)} · {item.first_reply ? "First reply" : "Follow-up"}
          </span>
        </button>
        {done && (
          <span className="flex items-center gap-1 rounded-full bg-leaf-soft px-2 py-0.5 text-[11px] font-semibold text-leaf">
            <Icon name="check" className="h-3.5 w-3.5" strokeWidth={2.2} />
            {result.dry_run ? "Sent (test)" : "Sent"}
          </span>
        )}
      </div>

      <div className="mt-2.5 grid gap-3 sm:grid-cols-2">
        <div className="min-w-0">
          <p className="mb-1 text-[11px] font-semibold tracking-wide text-faint uppercase">Buyer said</p>
          <div className="space-y-1 rounded-xl bg-[#efe7dc]/70 p-2">
            {item.said.map((m, n) => (
              <div key={n} className="w-fit max-w-full rounded-lg rounded-tl-sm bg-card px-2 py-1 text-sm text-ink shadow-sm">
                {m.image_ref && <img src={src(m.image_ref)} alt="Buyer's photo" className="max-h-28 rounded-md object-cover" />}
                {m.text && <p className="px-0.5 break-words whitespace-pre-line">{m.text}</p>}
              </div>
            ))}
          </div>
          {item.summary && <p className="mt-1.5 text-xs text-muted">{item.summary}</p>}
          {item.memory?.length > 0 && <p className="mt-0.5 text-xs text-indigo">Remembers: {item.memory.join(" · ")}</p>}
        </div>

        <div className="min-w-0">
          <p className="mb-1 text-[11px] font-semibold tracking-wide text-faint uppercase">Your reply</p>
          <textarea
            value={text}
            onChange={(e) => onText(e.target.value)}
            disabled={done || closed}
            rows={4}
            aria-label={`Reply to ${item.buyer_name || "buyer"}`}
            className="field-sizing-content max-h-80 min-h-20 w-full rounded-xl border border-line bg-paper px-2.5 py-2 text-sm text-ink focus:border-indigo focus:outline-none disabled:opacity-70"
          />
          {!done && text === item.text && <DraftNote source={item.source} needsStaff={item.needs_staff} />}
          {item.picked.length > 0 && (
            <div className="mt-1.5 flex items-center gap-1.5">
              {item.picked.slice(0, 5).map((d) => (
                <img
                  key={d.design_id}
                  src={imageUrl(d.image_file)}
                  alt={d.name}
                  title={`${d.name} (${d.design_id})`}
                  className="h-9 w-9 rounded-md object-cover ring-1 ring-line"
                />
              ))}
              <span className="text-[11px] text-faint">
                + {Math.min(item.picked.length, 5)} {item.picked.length === 1 ? "photo" : "photos"}
              </span>
            </div>
          )}
        </div>
      </div>

      {closed && !done && (
        <p className="mt-2 text-xs text-madder-dark">
          WhatsApp's 24-hour window has closed. Copy the reply and send it from your phone.
        </p>
      )}
      {result && !result.ok && <p className="mt-2 text-xs text-madder">Not sent: {result.error}</p>}
      {!done && !closed && (
        <div className="mt-2 flex justify-end">
          <button
            type="button"
            onClick={onSendOne}
            disabled={sending || !text.trim()}
            className="flex items-center gap-1.5 rounded-lg border border-leaf/40 px-3 py-1.5 text-xs font-semibold text-leaf hover:bg-leaf-soft disabled:opacity-50"
          >
            <Icon name="send" className="h-3.5 w-3.5" />
            Send just this one
          </button>
        </div>
      )}
    </li>
  );
}
