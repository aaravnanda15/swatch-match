import { useEffect, useRef, useState } from "react";
import { getSettings, sendEnquiry } from "../api.js";

// Used until /api/settings answers (same values as config.yaml)
const DEFAULT_SETTINGS = {
  max_mb: 10,
  allowed_types: ["image/jpeg", "image/png", "image/webp"],
  max_text_chars: 1000,
};

// Tap one to fill the text box: shows staff the kinds of messages that work
const EXAMPLES = ["red bandhani saree under 2000", "lal bandhani chahiye", "same design in blue"];

const MODE_TEXT = {
  image_only: "Photo only",
  text_only: "Text only",
  image_and_text: "Photo + text",
};

export default function EnquiryPage() {
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [photo, setPhoto] = useState(null); // the File the user picked
  const [preview, setPreview] = useState(""); // temporary URL to show it
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);
  const fileInput = useRef(null);

  useEffect(() => {
    getSettings().then(setSettings).catch(() => {}); // defaults are fine if this fails
  }, []);

  // Free the preview URL when the photo changes or the page closes
  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview);
    };
  }, [preview]);

  function pickPhoto(e) {
    const file = e.target.files[0];
    e.target.value = ""; // so picking the same file again still triggers a change
    if (!file) return;
    setResult(null);

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
  }

  function removePhoto() {
    setPhoto(null);
    setPreview("");
    setResult(null);
  }

  async function submit(e) {
    e.preventDefault();
    if (!photo && !text.trim()) {
      setError("Add a photo or type what the buyer asked for.");
      return;
    }
    setError("");
    setResult(null);
    setSending(true);
    try {
      setResult(await sendEnquiry(photo, text));
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  }

  const tooLong = text.length > settings.max_text_chars;

  return (
    <form onSubmit={submit} className="space-y-4">
      <p className="text-sm text-stone-600">
        Paste the buyer's photo, their message, or both. You get a shortlist from your catalogue.
      </p>

      {/* Photo */}
      <section className="rounded-xl border border-stone-200 bg-white p-3">
        <h2 className="mb-2 text-sm font-medium text-stone-800">Photo</h2>
        {preview ? (
          <div className="flex items-start gap-3">
            <img src={preview} alt="Buyer's photo" className="h-28 w-28 rounded-lg object-cover" />
            <div className="min-w-0 flex-1 space-y-2 text-sm">
              <p className="truncate text-stone-600">{photo.name}</p>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => fileInput.current.click()}
                  className="rounded-lg border border-stone-300 px-3 py-1.5 text-stone-700"
                >
                  Change
                </button>
                <button
                  type="button"
                  onClick={removePhoto}
                  className="rounded-lg border border-stone-300 px-3 py-1.5 text-stone-700"
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
            className="w-full rounded-lg border-2 border-dashed border-stone-300 py-6 text-sm text-stone-600"
          >
            Choose or take a photo
            <span className="mt-1 block text-xs text-stone-400">
              JPG, PNG or WEBP, up to {settings.max_mb} MB
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
      </section>

      {/* Text */}
      <section className="rounded-xl border border-stone-200 bg-white p-3">
        <label htmlFor="enquiry-text" className="mb-2 block text-sm font-medium text-stone-800">
          Message
        </label>
        <textarea
          id="enquiry-text"
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setResult(null);
          }}
          rows={3}
          placeholder="e.g. red bandhani under 2000, ya Hindi / Gujarati mein"
          className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
        />
        <div className="mt-1 flex items-center justify-between gap-2">
          <div className="flex flex-wrap gap-1">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => setText(ex)}
                className="rounded-full bg-stone-100 px-2 py-0.5 text-xs text-stone-600"
              >
                {ex}
              </button>
            ))}
          </div>
          <span className={`shrink-0 text-xs ${tooLong ? "text-red-600" : "text-stone-400"}`}>
            {text.length}/{settings.max_text_chars}
          </span>
        </div>
      </section>

      {error && (
        <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={sending || tooLong}
        className="w-full rounded-lg bg-rose-700 py-3 text-sm font-semibold text-white disabled:opacity-50"
      >
        {sending ? "Finding matches..." : "Find matches"}
      </button>

      {result && (
        <div className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">
          Enquiry #{result.enquiry_id} received ({MODE_TEXT[result.mode]}). Matching is added in the next step.
        </div>
      )}
    </form>
  );
}
