import { useEffect } from "react";
import Icon, { Logo } from "./Icon.jsx";

const FLOW = [
  ["enquiry", "Buyer messages on WhatsApp", "A photo, a message in English, हिंदी, ગુજરાતી or Hinglish, or both."],
  ["sparkle", "The agent shortlists", "Photo matching (CLIP), message reading (Gemini, keyword list as backup), tag match, stock check. Every step is shown in the trace."],
  ["check", "Staff check and tap Send", "Top 5 designs with label, reason, stock and rate, plus a ready reply. Nothing reaches the buyer until staff approve."],
  ["chart", "The shop learns", "Insights show reply speed and missed demand: what buyers ask for that the shop does not stock."],
];

const TRUST = [
  ["Numbers never come from AI", "Stock and rate are read from stock.csv; reply lines with numbers are templates."],
  ["Reasons are computed", "Labels and one-line reasons come from scores, tags and a brightness check, so they cannot be made up."],
  ["Works without AI", "If Gemini is off or fails, the keyword list and CLIP take over and the screen says so."],
  ["A person approves every reply", "The agent shortlists; it never decides and never sends on its own."],
];

// "How it works" for judges and new staff. Opened from the header.
export default function AboutSheet({ open, onClose }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="How Swatch Match works"
      className="fixed inset-0 z-40 flex justify-center overflow-y-auto bg-ink/40 p-3 backdrop-blur-sm sm:p-6"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="weave relative my-auto w-full max-w-3xl rounded-3xl border border-line p-5 shadow-2xl sm:p-8"
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="absolute top-4 right-4 flex h-9 w-9 items-center justify-center rounded-full bg-card text-muted ring-1 ring-line hover:text-ink"
        >
          <Icon name="x" className="h-4 w-4" />
        </button>

        <Logo className="h-11 w-11" />
        <h2 className="mt-3 font-display text-3xl leading-tight font-semibold tracking-tight sm:text-4xl">
          From a buyer's WhatsApp photo to a ready shortlist, in seconds.
        </h2>
        <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-muted">
          Small fabric and saree wholesalers get enquiries as photos and messages in many languages. Today staff search
          the shelves from memory, which is slow and depends on who is on duty. Swatch Match matches each enquiry
          against the shop's own catalogue, with real stock and rate, and drafts the reply.
        </p>

        <ol className="mt-6 grid gap-3 sm:grid-cols-2">
          {FLOW.map(([icon, title, body], i) => (
            <li key={title} className="rounded-2xl border border-line bg-card p-4">
              <div className="flex items-center gap-2">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo text-white">
                  <Icon name={icon} className="h-4 w-4" />
                </span>
                <span className="text-xs font-semibold text-faint">STEP {i + 1}</span>
              </div>
              <p className="mt-2 font-semibold text-ink">{title}</p>
              <p className="mt-1 text-sm leading-relaxed text-muted">{body}</p>
            </li>
          ))}
        </ol>

        <h3 className="mt-7 font-display text-xl font-semibold tracking-tight">Built to be trusted</h3>
        <ul className="mt-3 grid gap-x-6 gap-y-3 sm:grid-cols-2">
          {TRUST.map(([title, body]) => (
            <li key={title} className="flex gap-2.5">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-leaf-soft text-leaf">
                <Icon name="check" className="h-3.5 w-3.5" strokeWidth={2.4} />
              </span>
              <span>
                <span className="block text-sm font-semibold text-ink">{title}</span>
                <span className="block text-sm text-muted">{body}</span>
              </span>
            </li>
          ))}
        </ul>

        <div className="mt-7 grid gap-3 sm:grid-cols-3">
          <Fact value="94%" label="right design first" note="30 of 32 test enquiries, no AI key" />
          <Fact value="100%" label="right design in top 5" note="32 of 32 test enquiries" />
          <Fact value="4" label="languages" note="English, Hindi, Gujarati, Hinglish" />
        </div>
        <p className="mt-2 text-xs text-faint">
          Measured with evaluate.py on 4 Oct 2026 on the sample catalogue, using edited copies of catalogue photos
          and hand-written messages. The messages, the staff tags and the keyword list were written by the same
          team, so treat this as an upper bound; real phone photos and real buyers are harder.
        </p>

        <p className="mt-6 text-xs text-muted">
          <span className="font-semibold text-ink">Under the hood:</span> FastAPI · SQLite · CLIP ViT-B/32 ·
          Gemini 3.5 Flash-Lite · WhatsApp Business Cloud API · React + Tailwind. One fixed, explainable agent route per
          enquiry type, no open-ended AI loop.
        </p>
      </div>
    </div>
  );
}

function Fact({ value, label, note }) {
  return (
    <div className="rounded-2xl border border-line bg-card px-4 py-3">
      <p className="font-display text-3xl leading-none font-semibold tracking-tight text-madder">{value}</p>
      <p className="mt-1.5 text-sm font-semibold text-ink">{label}</p>
      <p className="text-[11px] text-faint">{note}</p>
    </div>
  );
}
