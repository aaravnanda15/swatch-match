import { useCallback, useEffect, useRef, useState } from "react";
import QRCode from "qrcode";
import {
  dismissInboxItem,
  getDemoScenarios,
  getInboxChat,
  imageUrl,
  getInbox,
  getInboxItem,
  getReadyReplies,
  samplePhotoUrl,
  simulateBuyer,
  uploadUrl,
} from "../api.js";
import { shortDateTime } from "../format.js";
import DraftNote from "../components/DraftNote.jsx";
import Icon from "../components/Icon.jsx";
import ImageViewer from "../components/ImageViewer.jsx";
import ReplyAll from "../components/ReplyAll.jsx";
import Shortlist from "../components/Shortlist.jsx";
import WhatsAppSend from "../components/WhatsAppSend.jsx";
import { copyText } from "../clipboard.js";

const POLL_MS = 10000; // check for new WhatsApp enquiries every 10 seconds
const FAST_POLL_MS = 1500; // right after a simulated message, check often

const STATUS = {
  new: { text: "New", style: "bg-madder text-white" },
  sent: { text: "Replied", style: "bg-leaf-soft text-leaf" },
  dismissed: { text: "Dismissed", style: "bg-line/70 text-muted" },
};

export default function InboxPage({ active, onNewCount, demoMode }) {
  const [items, setItems] = useState(null);
  const [filtered, setFiltered] = useState(0);
  const [showMuted, setShowMuted] = useState(false);
  const [readyCount, setReadyCount] = useState(0);
  const [replyAll, setReplyAll] = useState(false);
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState(null);
  // simulated buyers we're waiting for, so we can open them on arrival
  const [pending, setPending] = useState([]);
  const pendingRef = useRef([]);
  pendingRef.current = pending;
  const [fastUntil, setFastUntil] = useState(0); // keep polling fast until this time

  const load = useCallback(() => {
    getInbox()
      .then((data) => {
        setItems(data.items);
        setFiltered(data.filtered || 0);
        getReadyReplies()
          .then((ready) => setReadyCount(ready.items.length))
          .catch(() => {});
        onNewCount(data.new);
        setError("");
        const still = [];
        for (const w of pendingRef.current) {
          const arrived = data.items.find((i) => i.id > w.afterId && (i.buyer_name || "").startsWith(w.buyer));
          if (arrived) {
            setOpenId(arrived.id);
            setFastUntil(Date.now() + 8000); // a follow-up text may still merge in
          } else if (Date.now() - w.at < 45000) {
            still.push(w);
          }
        }
        if (still.length !== pendingRef.current.length) setPending(still);
      })
      .catch((e) => setError(e.message));
  }, [onNewCount]);

  // poll faster while waiting (a follow-up text may still merge in)
  const fast = pending.length > 0 || fastUntil > Date.now();
  useEffect(() => {
    if (!fast) return;
    const timer = setInterval(() => {
      load();
      if (pendingRef.current.length === 0 && Date.now() > fastUntil) setFastUntil(0);
    }, FAST_POLL_MS);
    return () => clearInterval(timer);
  }, [fast, fastUntil, load]);

  async function simulate(scenario) {
    const afterId = Math.max(0, ...(items || []).map((i) => i.id));
    const entry = { buyer: scenario.buyer, afterId, at: Date.now() };
    setPending((list) => [...list.filter((w) => w.buyer !== scenario.buyer), entry]);
    try {
      await simulateBuyer(scenario.id);
    } catch (e) {
      setError(e.message);
      setPending((list) => list.filter((w) => w !== entry));
    }
  }

  useEffect(() => {
    load();
    const timer = setInterval(load, POLL_MS);
    return () => clearInterval(timer);
  }, [load]);

  useEffect(() => {
    if (active) load();
  }, [active, load]);

  if (error && items === null) return <p className="rounded-xl bg-madder-soft p-3 text-sm text-madder-dark">{error}</p>;
  if (items === null) return <p className="text-sm text-muted">Loading inbox…</p>;
  if (replyAll)
    return (
      <ReplyAll
        onClose={() => {
          setReplyAll(false);
          load();
        }}
        onSent={load}
        onOpenChat={(id) => {
          setReplyAll(false);
          setOpenId(id);
        }}
      />
    );

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:items-start">
      {/* phones: list hidden while an enquiry is open */}
      <div className={`min-w-0 space-y-4 ${openId ? "hidden lg:block" : ""}`}>
        <div>
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-display text-2xl font-semibold tracking-tight">Inbox</h2>
            {readyCount > 0 && (
              <button
                type="button"
                onClick={() => setReplyAll(true)}
                className="flex items-center gap-1.5 rounded-xl bg-leaf px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-leaf/90"
              >
                <Icon name="send" className="h-4 w-4" />
                Reply to all ({readyCount})
              </button>
            )}
          </div>
          <p className="mt-1 text-sm text-muted">
            WhatsApp enquiries, already matched. Open one, check it, then reply.
          </p>
          {filtered > 0 && (
            <p className="mt-1.5 flex items-center gap-1.5 text-xs text-leaf">
              <Icon name="check" className="h-3.5 w-3.5" strokeWidth={2.2} />
              {filtered} time-wasting {filtered === 1 ? "message" : "messages"} filtered out for you (emojis, spam,
              repeats)
            </p>
          )}
        </div>
        {demoMode && <BuyerQR />}
        {demoMode && <DemoPanel onSimulate={simulate} pending={pending} />}
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
          <>
            <ul className="divide-y divide-line/70 overflow-hidden rounded-2xl border border-line bg-card">
              {items
                .filter((item) => !item.flagged)
                .map((item) => (
                  <InboxRow key={item.id} item={item} selected={item.id === openId} onOpen={() => setOpenId(item.id)} />
                ))}
            </ul>
            {items.some((item) => item.flagged) && (
              <div>
                <button
                  type="button"
                  onClick={() => setShowMuted(!showMuted)}
                  className="flex items-center gap-1 text-xs font-medium text-muted hover:text-ink"
                >
                  <Icon name="chevron" className={`h-3.5 w-3.5 transition-transform ${showMuted ? "rotate-90" : ""}`} />
                  Muted chats ({items.filter((item) => item.flagged).length}): only off-topic messages so far
                </button>
                {showMuted && (
                  <ul className="mt-2 divide-y divide-line/70 overflow-hidden rounded-2xl border border-line bg-card opacity-75">
                    {items
                      .filter((item) => item.flagged)
                      .map((item) => (
                        <InboxRow key={item.id} item={item} selected={item.id === openId} onOpen={() => setOpenId(item.id)} />
                      ))}
                  </ul>
                )}
              </div>
            )}
          </>
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
            <span className="shrink-0 text-[11px] text-faint">{shortDateTime(item.last_at || item.created_at)}</span>
          </span>
          <span className="mt-0.5 flex items-center gap-2">
            <span className={`truncate text-[13px] ${unsupported ? "text-faint italic" : "text-muted"}`}>
              {item.text || (item.image_file ? "Photo" : "")}
            </span>
            {item.flagged ? (
              <span className="ml-auto shrink-0 rounded-full bg-line px-2 py-0.5 text-[10px] font-semibold text-muted">
                Muted
              </span>
            ) : item.status !== "new" && item.followup_priority === "low" ? (
              <span className="ml-auto shrink-0 rounded-full bg-line/70 px-2 py-0.5 text-[10px] font-semibold text-muted">
                Can wait
              </span>
            ) : (
              <span className={`ml-auto shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ${status.style}`}>
                {status.text}
              </span>
            )}
          </span>
        </span>
      </button>
    </li>
  );
}

function InboxDetail({ id, signature, onBack, onChanged }) {
  const [item, setItem] = useState(null);
  const [chatTick, setChatTick] = useState(0); // bump to reload the conversation
  const [error, setError] = useState("");
  const [viewing, setViewing] = useState(null);

  const load = useCallback(() => {
    getInboxItem(id)
      .then(setItem)
      .catch((e) => setError(e.message));
  }, [id]);

  // reload when a follow-up text merges in
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

      {item.followup && item.followup.intent !== "new_or_changed_request" && (
        <FollowUp
          key={`${item.followup.buyer_text}|${item.status}`}
          item={item}
          onSent={() => {
            load();
            onChanged();
            setTimeout(() => setChatTick((n) => n + 1), 600);
          }}
        />
      )}

      <Conversation item={item} refreshKey={`${signature}|${chatTick}`} onOpenImage={setViewing} />

      {item.answer ? (
        <Shortlist
          key={`${item.mode}|${item.text}`}
          answer={item.answer}
          onOpenImage={setViewing}
          whatsapp={{
            enquiryId: item.id,
            status: item.status,
            hoursLeft: item.hours_left,
            buyerName: item.buyer_name,
            draft: item.draft,
            onSent: () => {
              load();
              onChanged();
              setTimeout(() => setChatTick((n) => n + 1), 600);
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

function DemoPanel({ onSimulate, pending }) {
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
          const busy = pending.some((w) => w.buyer === s.buyer);
          return (
            <button
              key={s.id}
              type="button"
              onClick={() => onSimulate(s)}
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
                  {busy ? "message arriving…" : s.text || "photo"}
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

// older enquiries have no chat log; show their own message
function Conversation({ item, refreshKey, onOpenImage }) {
  const [chat, setChat] = useState(null);
  useEffect(() => {
    getInboxChat(item.id)
      .then(setChat)
      .catch(() => setChat([]));
  }, [item.id, refreshKey]);

  const messages =
    chat && chat.length > 0
      ? chat.slice(-12)
      : [{ id: "only", direction: "in", text: item.text, image_ref: item.image_file ? `upload:${item.image_file}` : null }];

  const src = (ref) => {
    const [kind, name] = ref.split(":");
    return kind === "upload" ? uploadUrl(name) : imageUrl(name);
  };

  return (
    <div className="space-y-1.5 rounded-2xl bg-[#efe7dc]/70 p-2.5">
      {messages.map((m) => {
        const fromBuyer = m.direction === "in";
        return (
          <div
            key={m.id}
            className={`w-fit max-w-[85%] rounded-xl px-2 py-1.5 text-sm shadow-sm ${
              fromBuyer ? "rounded-tl-sm bg-card" : "ml-auto rounded-tr-sm bg-[#d6f2d0]"
            }`}
          >
            {m.image_ref && (
              <button
                type="button"
                onClick={() =>
                  onOpenImage({
                    image_file: m.image_ref.split(":")[1],
                    name: fromBuyer ? "Buyer's photo" : m.caption,
                    upload: m.image_ref.startsWith("upload:"),
                  })
                }
              >
                <img src={src(m.image_ref)} alt="" className="max-h-44 rounded-lg object-cover" />
              </button>
            )}
            {(m.text || m.caption) && (
              <p className={`px-1 whitespace-pre-line ${item.mode === "unsupported" && fromBuyer ? "text-faint italic" : "text-ink"}`}>
                {m.text || m.caption}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}

function BuyerQR() {
  const link = `${window.location.origin}/#buyer`;
  const [qr, setQr] = useState("");
  useEffect(() => {
    QRCode.toDataURL(link, { margin: 1, width: 240, color: { dark: "#231d18", light: "#fffdf9" } })
      .then(setQr)
      .catch(() => setQr(""));
  }, [link]);

  return (
    <section className="flex items-center gap-4 rounded-2xl border border-line bg-card p-3">
      {qr && <img src={qr} alt="QR code for the buyer chat" className="h-24 w-24 shrink-0 rounded-lg" />}
      <div className="min-w-0">
        <p className="text-sm font-semibold text-ink">Be the buyer</p>
        <p className="mt-0.5 text-xs text-muted">
          Scan with any phone to message this shop like on WhatsApp. Replies you send here appear on that phone.
        </p>
        <a
          href="#buyer"
          target="_blank"
          rel="noreferrer"
          className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-indigo hover:underline"
        >
          Open buyer chat in a new tab
          <Icon name="chevron" className="h-3.5 w-3.5" />
        </a>
      </div>
    </section>
  );
}

const FILTER_TEXT = {
  noise: "Filtered: just an emoji or an \"ok\".",
  spam: "Filtered: looks like spam or a forward.",
  duplicate: "Filtered: the same message again; the earlier reply still stands.",
  muted: "Filtered: this chat is muted after repeated off-topic messages.",
  rude: "Filtered: an off-topic or rude message.",
};

const INTENT_TEXT = {
  answer_to_question: "Answer to your question",
  question_about_shown_designs: "Question about the designs",
  greeting: "Greeting",
  off_topic: "Off topic",
  abusive_or_nonsense: "Off topic / rude",
};

// A later message in an ongoing chat ("67 kg", "how many in stock?") with the
// suggested answer. Staff can edit it; nothing goes out until they send it.
function FollowUp({ item, onSent }) {
  const f = item.followup;
  const [text, setText] = useState(f.reply || "");
  const [copied, setCopied] = useState(false);

  return (
    <section className="rise rounded-2xl border border-indigo/25 bg-card p-3 shadow-[0_1px_2px_rgb(35_29_24/0.05)]">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-display text-lg font-semibold tracking-tight">Buyer replied</h3>
        <span className="rounded-full bg-indigo-soft px-2 py-0.5 text-[11px] font-semibold text-indigo">
          {INTENT_TEXT[f.intent] || f.intent}
        </span>
        {f.priority === "low" && (
          <span className="rounded-full bg-line/70 px-2 py-0.5 text-[11px] font-semibold text-muted">Can wait</span>
        )}
        {f.flagged && (
          <span className="rounded-full bg-line px-2 py-0.5 text-[11px] font-semibold text-muted">Muted</span>
        )}
      </div>
      <p className="mt-1 text-xs text-muted">{f.summary}</p>
      {f.reply ? (
        <>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={4}
            aria-label="Suggested reply"
            className="mt-2 w-full resize-y rounded-xl border border-line bg-paper/40 px-3 py-2.5 text-[14px] leading-relaxed focus:border-indigo focus:bg-card focus:outline-none"
          />
          {text === f.reply && <DraftNote source={f.reply_source} needsStaff={f.needs_staff} />}
          <div className="mt-2 space-y-2">
            <WhatsAppSend
              whatsapp={{ enquiryId: item.id, status: item.status, hoursLeft: item.hours_left, buyerName: item.buyer_name, onSent }}
              picked={[]}
              text={text}
              language={item.answer?.query?.language || "en"}
              disabled={!text.trim()}
            />
            <button
              type="button"
              onClick={async () => setCopied(await copyText(text))}
              className="flex w-full items-center justify-center gap-2 rounded-xl border border-line py-2.5 text-sm font-medium text-muted hover:text-ink"
            >
              <Icon name={copied ? "check" : "copy"} className="h-4 w-4" />
              {copied ? "Copied" : "Copy instead (reply from phone)"}
            </button>
          </div>
        </>
      ) : (
        <p className="mt-2 rounded-xl bg-saffron-soft px-3 py-2 text-sm text-[#6e4a10]">
          {FILTER_TEXT[f.filter] || (f.flagged ? FILTER_TEXT.muted : FILTER_TEXT.noise)} No reply needed.
        </p>
      )}
    </section>
  );
}
