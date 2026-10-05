import { useEffect, useRef, useState } from "react";
import { approveReply, draftReply } from "../api.js";
import { copyText } from "../clipboard.js";
import Icon from "./Icon.jsx";
import WhatsAppSend from "./WhatsAppSend.jsx";

const LANGUAGES = [
  { id: "en", label: "English" },
  { id: "hi", label: "हिंदी" },
  { id: "hinglish", label: "Hinglish" },
  { id: "gu", label: "ગુજરાતી" },
];

export default function ReplyBox({ enquiryId, picked, defaultLanguage, whatsapp }) {
  const [language, setLanguage] = useState(
    LANGUAGES.some((l) => l.id === defaultLanguage) ? defaultLanguage : "en"
  );
  const [text, setText] = useState("");
  const [edited, setEdited] = useState(false); // staff changed the text by hand
  const [stale, setStale] = useState(false); // picks changed after editing
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [approved, setApproved] = useState(null); // "copied" | "saved"
  const pickedKey = picked.join(",");
  const lastBuilt = useRef("");

  async function build() {
    if (picked.length === 0) {
      setText("");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const draft = await draftReply(enquiryId, picked, language);
      setText(draft.text);
      setEdited(false);
      setStale(false);
      setApproved(null);
      lastBuilt.current = `${pickedKey}|${language}`;
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  // rebuild on pick/language change, but don't overwrite staff edits
  useEffect(() => {
    if (lastBuilt.current === `${pickedKey}|${language}`) {
      setStale(false); // back to what the draft was built for
      return;
    }
    if (edited) {
      setStale(true);
      return;
    }
    build();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pickedKey, language]);

  async function approve() {
    setError("");
    try {
      await approveReply(enquiryId, picked, text, language);
      const copied = await copyText(text);
      setApproved(copied ? "copied" : "saved");
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <section className="rise rounded-2xl border border-line bg-card p-3 shadow-[0_1px_2px_rgb(35_29_24/0.05)]">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-display text-lg font-semibold tracking-tight">Reply to buyer</h3>
        <div role="radiogroup" aria-label="Reply language" className="flex rounded-xl bg-paper p-0.5 ring-1 ring-line">
          {LANGUAGES.map((l) => (
            <button
              key={l.id}
              type="button"
              role="radio"
              aria-checked={language === l.id}
              onClick={() => setLanguage(l.id)}
              className={`rounded-[10px] px-2.5 py-1 text-xs font-semibold transition-colors ${
                language === l.id ? "bg-card text-ink shadow-sm ring-1 ring-line" : "text-muted hover:text-ink"
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>
      </div>

      {picked.length === 0 ? (
        <p className="mt-3 rounded-xl border border-dashed border-line px-3 py-5 text-center text-sm text-muted">
          Tick <Icon name="check" className="inline h-4 w-4 align-[-3px]" strokeWidth={2.4} /> the designs to offer, and
          a reply appears here.
        </p>
      ) : (
        <>
          <p className="mt-1 text-xs text-muted">
            {picked.length} design{picked.length > 1 ? "s" : ""}: {picked.join(", ")} · Stock and rate filled in from
            stock.csv. Edit freely.
          </p>
          <textarea
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setEdited(true);
              setApproved(null);
            }}
            rows={9}
            aria-label="Reply text"
            className={`mt-2 w-full resize-y rounded-xl border border-line bg-paper/40 px-3 py-2.5 text-[14px] leading-relaxed focus:border-indigo focus:bg-card focus:outline-none ${
              loading ? "opacity-50" : ""
            }`}
          />
          {stale && (
            <div className="mt-1.5 flex items-center justify-between gap-2 rounded-lg bg-saffron-soft px-2.5 py-1.5 text-xs text-[#6e4a10]">
              Your edits are kept. The picked designs changed.
              <button type="button" onClick={build} className="flex items-center gap-1 font-semibold underline">
                <Icon name="refresh" className="h-3.5 w-3.5" />
                Rebuild draft
              </button>
            </div>
          )}
        </>
      )}

      {error && <p className="mt-2 text-sm text-madder">{error}</p>}

      {picked.length > 0 && whatsapp && (
        <div className="mt-3">
          <WhatsAppSend
            whatsapp={whatsapp}
            picked={picked}
            text={text}
            language={language}
            disabled={loading || !text.trim() || stale}
          />
        </div>
      )}

      {picked.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={approve}
            disabled={loading || !text.trim()}
            className={
              whatsapp
                ? "flex flex-1 items-center justify-center gap-2 rounded-xl border border-line py-2.5 text-sm font-medium text-muted hover:text-ink disabled:opacity-50"
                : "flex flex-1 items-center justify-center gap-2 rounded-xl bg-leaf py-3 text-sm font-semibold text-white shadow-sm hover:bg-leaf/90 disabled:opacity-50"
            }
          >
            <Icon name={approved ? "check" : "copy"} className="h-4 w-4" strokeWidth={2.2} />
            {approved ? "Approved" : whatsapp ? "Copy instead (reply from phone)" : "Approve & copy"}
          </button>
          {edited && !stale && (
            <button
              type="button"
              onClick={build}
              className="rounded-xl border border-line px-3 py-3 text-sm font-medium text-muted hover:text-ink"
            >
              Reset
            </button>
          )}
        </div>
      )}

      {approved && (
        <p className="mt-2 flex items-center gap-1.5 text-xs text-leaf">
          <Icon name="check" className="h-4 w-4" strokeWidth={2.2} />
          {approved === "copied"
            ? "Copied and saved to the log. Paste it in WhatsApp and attach the photos."
            : "Saved to the log. Select the text above and copy it."}
        </p>
      )}
      <p className="mt-2 text-[11px] text-faint">
        {whatsapp
          ? "Nothing goes to the buyer until you tap Send. You stay in control."
          : "Swatch Match never sends messages. You stay in control."}
      </p>
    </section>
  );
}
