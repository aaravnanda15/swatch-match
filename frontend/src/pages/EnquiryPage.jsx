import { useCallback, useEffect, useRef, useState } from "react";
import { getSettings, sendEnquiry } from "../api.js";
import Icon from "../components/Icon.jsx";
import ImageViewer from "../components/ImageViewer.jsx";
import Shortlist from "../components/Shortlist.jsx";

// Used until /api/settings answers (same values as config.yaml)
const DEFAULT_SETTINGS = {
  max_mb: 10,
  allowed_types: ["image/jpeg", "image/png", "image/webp"],
  max_text_chars: 1000,
};

// Tap one to fill the text box: shows staff the kinds of messages that work
const EXAMPLES = ["red bandhani saree under 2000", "lal bandhani chahiye", "लाल बांधनी साड़ी", "same design in blue"];

export default function EnquiryPage() {
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [photo, setPhoto] = useState(null); // the File the user picked
  const [preview, setPreview] = useState(""); // temporary URL to show it
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [viewing, setViewing] = useState(null); // design shown full screen
  const fileInput = useRef(null);
  const formRef = useRef(null);
  const resultsRef = useRef(null);

  useEffect(() => {
    getSettings().then(setSettings).catch(() => {}); // defaults are fine if this fails
  }, []);

  // Free the preview URL when the photo changes or the page closes
  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview);
    };
  }, [preview]);

  const acceptPhoto = useCallback(
    (file) => {
      // Check here first so the user gets an answer instantly. The server checks again.
      if (!settings.allowed_types.includes(file.type)) {
        setError("Please choose a JPG, PNG or WEBP photo. Other files (PDF, video, HEIC) cannot be matched.");
        return;
      }
      if (file.size > settings.max_mb * 1024 * 1024) {
        const mb = (file.size / 1024 / 1024).toFixed(1);
        setError(`This photo is ${mb} MB. Please send one under ${settings.max_mb} MB.`);
        return;
      }
      setError("");
      setPhoto(file);
      setPreview(URL.createObjectURL(file));
    },
    [settings]
  );

  // Paste a photo straight from WhatsApp Web (Ctrl/Cmd + V) while this page is open
  useEffect(() => {
    function onPaste(e) {
      if (!formRef.current || formRef.current.offsetParent === null) return; // page hidden
      const file = [...(e.clipboardData?.files || [])].find((f) => f.type.startsWith("image/"));
      if (file) {
        e.preventDefault();
        acceptPhoto(file);
      }
    }
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [acceptPhoto]);

  function pickPhoto(e) {
    const file = e.target.files[0];
    e.target.value = ""; // so picking the same file again still triggers a change
    if (file) acceptPhoto(file);
  }

  function dropPhoto(e) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) acceptPhoto(file);
  }

  function removePhoto() {
    setPhoto(null);
    setPreview("");
  }

  function startOver() {
    removePhoto();
    setText("");
    setResult(null);
    setError("");
  }

  async function submit(e) {
    e.preventDefault();
    if (!photo && !text.trim()) {
      setError("Add a photo or type what the buyer asked for.");
      return;
    }
    setError("");
    setSending(true);
    try {
      setResult(await sendEnquiry(photo, text));
      // On phones the shortlist is below the form: bring it into view
      if (window.innerWidth < 1024) {
        setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  }

  const tooLong = text.length > settings.max_text_chars;

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:items-start">
      {/* ---------- The enquiry ---------- */}
      <form ref={formRef} onSubmit={submit} className="space-y-4 lg:sticky lg:top-32">
        <div>
          <h2 className="font-display text-2xl font-semibold tracking-tight">New enquiry</h2>
          <p className="mt-1 text-sm text-muted">
            Paste the buyer's photo, their message, or both. Get a shortlist from your own stock.
          </p>
        </div>

        <section className="rounded-2xl border border-line bg-card p-3 shadow-[0_1px_2px_rgb(35_29_24/0.05)]">
          {preview ? (
            <div className="flex items-center gap-3">
              <img src={preview} alt="Buyer's photo" className="h-24 w-24 rounded-xl object-cover" />
              <div className="min-w-0 flex-1 space-y-2">
                <p className="truncate text-sm font-medium text-ink">{photo.name || "Pasted photo"}</p>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => fileInput.current.click()}
                    className="rounded-lg border border-line px-3 py-1.5 text-sm font-medium text-ink hover:bg-paper"
                  >
                    Change
                  </button>
                  <button
                    type="button"
                    onClick={removePhoto}
                    className="rounded-lg border border-line px-3 py-1.5 text-sm font-medium text-muted hover:bg-paper"
                  >
                    Remove
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => fileInput.current.click()}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={dropPhoto}
              className={`flex w-full flex-col items-center gap-1.5 rounded-xl border-2 border-dashed px-4 py-7 text-center transition-colors ${
                dragging ? "border-indigo bg-indigo-soft" : "border-line hover:border-faint hover:bg-paper/60"
              }`}
            >
              <span className="flex h-11 w-11 items-center justify-center rounded-full bg-indigo-soft text-indigo">
                <Icon name="camera" className="h-6 w-6" />
              </span>
              <span className="text-sm font-semibold text-ink">Add the buyer's photo</span>
              <span className="text-xs text-muted">
                Tap to choose, drop it here, or paste · JPG, PNG, WEBP up to {settings.max_mb} MB
              </span>
            </button>
          )}
          <input
            ref={fileInput}
            type="file"
            accept={settings.allowed_types.join(",")}
            onChange={pickPhoto}
            className="hidden"
          />

          <label htmlFor="enquiry-text" className="mt-4 mb-1.5 block text-sm font-semibold text-ink">
            Buyer's message
          </label>
          <textarea
            id="enquiry-text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={3}
            placeholder="e.g. red bandhani under 2000 · English, हिंदी, ગુજરાતી or Hinglish"
            className="w-full resize-y rounded-xl border border-line bg-paper/40 px-3 py-2.5 text-[15px] placeholder:text-faint focus:border-indigo focus:bg-card focus:outline-none"
          />
          <div className="mt-2 flex items-start justify-between gap-2">
            <div className="flex flex-wrap gap-1.5">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  type="button"
                  onClick={() => setText(ex)}
                  className="rounded-full border border-line bg-paper px-2.5 py-1 text-xs text-muted hover:border-faint hover:text-ink"
                >
                  {ex}
                </button>
              ))}
            </div>
            <span className={`shrink-0 pt-1 text-xs tabular-nums ${tooLong ? "text-madder" : "text-faint"}`}>
              {text.length}/{settings.max_text_chars}
            </span>
          </div>
        </section>

        {error && (
          <p role="alert" className="flex gap-2 rounded-xl border border-madder/30 bg-madder-soft px-3 py-2.5 text-sm text-madder-dark">
            <Icon name="alert" className="mt-px h-4 w-4 shrink-0" />
            {error}
          </p>
        )}

        <div className="flex gap-2">
          <button
            type="submit"
            disabled={sending || tooLong}
            className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-madder py-3.5 text-[15px] font-semibold text-white shadow-sm transition-colors hover:bg-madder-dark disabled:opacity-50"
          >
            <Icon name="search" className="h-5 w-5" />
            {sending ? "Finding matches…" : "Find matches"}
          </button>
          {(result || photo || text) && (
            <button
              type="button"
              onClick={startOver}
              className="rounded-xl border border-line bg-card px-4 text-sm font-medium text-muted hover:text-ink"
            >
              Clear
            </button>
          )}
        </div>
      </form>

      {/* ---------- The shortlist ---------- */}
      <section ref={resultsRef} aria-live="polite" className="min-w-0 scroll-mt-20">
        {sending ? (
          <LoadingCards />
        ) : result ? (
          <Shortlist key={result.enquiry_id} result={result} onOpenImage={setViewing} />
        ) : (
          <EmptyState />
        )}
      </section>

      <ImageViewer design={viewing} onClose={() => setViewing(null)} />
    </div>
  );
}

function EmptyState() {
  const steps = [
    ["photo", "Add what the buyer sent", "A photo, a message, or both."],
    ["search", "Get a shortlist", "Top 5 from your catalogue with stock and rate."],
    ["check", "Pick, edit, approve", "Copy a ready reply. Nothing is sent by itself."],
  ];
  return (
    <div className="rounded-2xl border border-dashed border-line px-5 py-8">
      <ol className="space-y-5">
        {steps.map(([icon, title, body], i) => (
          <li key={title} className="flex gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-card text-indigo ring-1 ring-line">
              <Icon name={icon} className="h-[18px] w-[18px]" />
            </span>
            <div>
              <p className="text-sm font-semibold text-ink">
                {i + 1}. {title}
              </p>
              <p className="text-sm text-muted">{body}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

function LoadingCards() {
  return (
    <div className="space-y-2.5" aria-label="Finding matches">
      <div className="h-7 w-32 animate-pulse rounded-lg bg-line/70" />
      {[0, 1, 2].map((i) => (
        <div key={i} className="flex gap-3 rounded-2xl border border-line bg-card p-3">
          <div className="h-28 w-24 animate-pulse rounded-xl bg-line/70" />
          <div className="flex-1 space-y-2 pt-1">
            <div className="h-4 w-24 animate-pulse rounded bg-line/70" />
            <div className="h-4 w-3/4 animate-pulse rounded bg-line/70" />
            <div className="h-3 w-full animate-pulse rounded bg-line/50" />
            <div className="h-3 w-1/2 animate-pulse rounded bg-line/50" />
          </div>
        </div>
      ))}
    </div>
  );
}
