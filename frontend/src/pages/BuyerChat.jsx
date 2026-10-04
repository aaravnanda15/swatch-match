import { useEffect, useMemo, useRef, useState } from "react";
import { chatMessages, chatSend, samplePhotoUrl } from "../api.js";
import Icon, { Logo } from "../components/Icon.jsx";

// Plays the buyer's side of WhatsApp (demo mode). Open <app link>/#buyer on
// any phone. Messages reach the shop's Inbox the same way real WhatsApp ones
// do, and replies the shop sends show up here.

const STORAGE_KEY = "swatch-match-buyer";
const POLL_MS = 2000;
const SUGGESTIONS = ["lal bandhani saree chahiye", "blue silk dupatta, 20 piece", "लाल बांधनी साड़ी 2000 तक"];
const SAMPLE_PHOTO = "q_D010_text.jpg";

const CHAT_PREFIX = "9100"; // made-up numbers: no real Indian mobile starts with 0

function loadBuyer() {
  try {
    const buyer = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    return buyer?.phone?.startsWith(CHAT_PREFIX) ? buyer : null; // older demo numbers: start again
  } catch {
    return null;
  }
}

function saveBuyer(buyer) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(buyer));
  } catch {
    // private mode: the chat still works until the page is closed
  }
}

export default function BuyerChat() {
  const [buyer, setBuyer] = useState(loadBuyer);
  if (!buyer) return <Welcome onStart={(b) => (saveBuyer(b), setBuyer(b))} />;
  return <Chat buyer={buyer} />;
}

function Welcome({ onStart }) {
  const [name, setName] = useState("");
  function start(e) {
    e.preventDefault();
    // A made-up number that marks this as a demo chat buyer
    const phone = CHAT_PREFIX + String(Math.floor(Math.random() * 1e8)).padStart(8, "0");
    onStart({ name: name.trim() || "Buyer", phone });
  }
  return (
    <div className="weave flex min-h-screen items-center justify-center p-4">
      <form onSubmit={start} className="w-full max-w-sm rounded-2xl border border-line bg-card p-6 shadow-lg">
        <Logo className="h-10 w-10" />
        <h1 className="mt-3 font-display text-2xl font-semibold tracking-tight">Message the shop</h1>
        <p className="mt-1 text-sm text-muted">
          You're a buyer. Send a photo or ask for a design, the way you would on WhatsApp. The shop replies here.
        </p>
        <input
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={60}
          placeholder="Your shop or name, e.g. Ramesh Textiles"
          aria-label="Your name"
          className="mt-4 w-full rounded-xl border border-line bg-paper/40 px-3 py-3 text-[15px] focus:border-indigo focus:bg-card focus:outline-none"
        />
        <button type="submit" className="mt-3 w-full rounded-xl bg-[#1f7a5a] py-3 text-sm font-semibold text-white">
          Start chat
        </button>
        <p className="mt-3 text-[11px] text-faint">Demo: no real WhatsApp messages are sent.</p>
      </form>
    </div>
  );
}

function Chat({ buyer }) {
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [photo, setPhoto] = useState(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const lastId = useRef(0);
  const bottom = useRef(null);
  const fileInput = useRef(null);

  // Fetch new messages every 2 seconds
  useEffect(() => {
    let stopped = false;
    async function poll() {
      try {
        const fresh = await chatMessages(buyer.phone, lastId.current);
        if (!stopped && fresh.length) {
          lastId.current = fresh[fresh.length - 1].id;
          setMessages((list) => [...list, ...fresh]);
        }
      } catch {
        // offline for a moment: try again on the next tick
      }
    }
    poll();
    const timer = setInterval(poll, POLL_MS);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [buyer.phone]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, sending]);

  async function send(e, overrideText) {
    e?.preventDefault();
    const body = overrideText ?? text;
    if (!body.trim() && !photo) return;
    setSending(true);
    setError("");
    try {
      await chatSend(buyer.phone, buyer.name, body, photo);
      setText("");
      setPhoto(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  }

  async function sendSamplePhoto() {
    const blob = await (await fetch(samplePhotoUrl(SAMPLE_PHOTO))).blob();
    setPhoto(new File([blob], "photo.jpg", { type: "image/jpeg" }));
  }

  const photoUrl = useMemo(() => (photo ? URL.createObjectURL(photo) : ""), [photo]);
  useEffect(() => () => photoUrl && URL.revokeObjectURL(photoUrl), [photoUrl]);

  const waitingForShop = messages.length > 0 && messages[messages.length - 1].direction === "in";

  return (
    <div className="flex h-[100dvh] flex-col bg-[#efe7dc]">
      <header className="flex items-center gap-3 bg-[#1f4e46] px-4 py-3 text-white">
        <span className="flex h-10 w-10 items-center justify-center rounded-full bg-white/95">
          <Logo className="h-7 w-7" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold">Swatch Match Textiles</p>
          <p className="truncate text-xs text-white/70">
            {waitingForShop ? "Checking stock for you…" : "Usually replies within minutes"}
          </p>
        </div>
        <span className="rounded-full bg-white/15 px-2 py-0.5 text-[10px] font-semibold">DEMO</span>
      </header>

      <main
        className="flex-1 space-y-2 overflow-y-auto px-3 py-4"
        style={{
          backgroundImage:
            "radial-gradient(rgb(31 78 70 / 0.07) 1px, transparent 1px), radial-gradient(rgb(179 50 43 / 0.05) 1px, transparent 1px)",
          backgroundSize: "18px 18px, 18px 18px",
          backgroundPosition: "0 0, 9px 9px",
        }}
      >
        <p className="mx-auto w-fit rounded-lg bg-[#fdf3d0] px-3 py-1.5 text-center text-[11px] text-[#6e5a1e] shadow-sm">
          Chatting as <b>{buyer.name}</b>. Send a photo or ask for a design.
        </p>

        {messages.map((m) => (
          <Bubble key={m.id} message={m} />
        ))}
        {sending && (
          <div className="ml-auto w-fit max-w-[80%] rounded-xl rounded-tr-sm bg-[#d6f2d0] px-3 py-2 text-sm text-ink/60 shadow-sm">
            Sending…
          </div>
        )}
        <div ref={bottom} />
      </main>

      {messages.length === 0 && !photo && (
        <div className="flex gap-2 overflow-x-auto px-3 pb-2">
          <button
            type="button"
            onClick={sendSamplePhoto}
            className="flex shrink-0 items-center gap-1 rounded-full bg-white px-3 py-1.5 text-xs font-medium text-[#1f4e46] shadow-sm"
          >
            <Icon name="photo" className="h-3.5 w-3.5" />
            Use a sample photo
          </button>
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => send(null, s)}
              className="shrink-0 rounded-full bg-white px-3 py-1.5 text-xs text-ink shadow-sm"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {photo && (
        <div className="flex items-center gap-2 bg-white/80 px-3 py-2">
          <img src={photoUrl} alt="" className="h-12 w-12 rounded-lg object-cover" />
          <span className="flex-1 text-xs text-muted">Photo ready. Add a message or just send.</span>
          <button type="button" onClick={() => setPhoto(null)} aria-label="Remove photo" className="p-2 text-muted">
            <Icon name="x" className="h-4 w-4" />
          </button>
        </div>
      )}
      {error && <p className="bg-madder-soft px-3 py-1.5 text-xs text-madder-dark">{error}</p>}

      <form onSubmit={send} className="pb-safe flex items-end gap-2 bg-[#efe7dc] px-2 pt-1">
        <div className="flex flex-1 items-end rounded-3xl bg-white px-2 shadow-sm">
          <button
            type="button"
            onClick={() => fileInput.current.click()}
            aria-label="Attach a photo"
            className="p-2.5 text-[#54656f]"
          >
            <Icon name="camera" className="h-5 w-5" />
          </button>
          <textarea
            rows={1}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) send(e);
            }}
            placeholder="Message"
            aria-label="Message"
            className="max-h-28 flex-1 resize-none bg-transparent py-2.5 text-[15px] focus:outline-none"
          />
        </div>
        <button
          type="submit"
          disabled={sending || (!text.trim() && !photo)}
          aria-label="Send"
          className="mb-0.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[#1f7a5a] text-white disabled:opacity-60"
        >
          <Icon name="send" className="h-5 w-5" />
        </button>
        <input
          ref={fileInput}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="hidden"
          onChange={(e) => {
            if (e.target.files[0]) setPhoto(e.target.files[0]);
            e.target.value = "";
          }}
        />
      </form>
    </div>
  );
}

function Bubble({ message: m }) {
  const mine = m.direction === "in"; // "in" = buyer to shop = this person's own message
  const time = new Date(m.created_at.replace(" ", "T") + "Z").toLocaleTimeString("en-IN", {
    hour: "numeric",
    minute: "2-digit",
  });
  return (
    <div
      className={`w-fit max-w-[80%] rounded-xl px-2 pt-1.5 pb-1 text-[15px] leading-snug text-ink shadow-sm ${
        mine ? "ml-auto rounded-tr-sm bg-[#d6f2d0]" : "rounded-tl-sm bg-white"
      }`}
    >
      {m.image_url && <img src={m.image_url} alt="" className="mb-1 max-h-64 rounded-lg object-cover" />}
      {(m.text || m.caption) && <p className="px-1 whitespace-pre-line">{m.text || m.caption}</p>}
      <p className="px-1 text-right text-[10px] text-ink/45">{time}</p>
    </div>
  );
}
