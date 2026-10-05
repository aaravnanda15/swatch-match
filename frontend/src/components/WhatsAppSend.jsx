import { useState } from "react";
import { sendWhatsApp } from "../api.js";
import Icon from "./Icon.jsx";

// whatsapp = { enquiryId, status, hoursLeft, buyerName, onSent }
// draft = { draft_source, edited }: who wrote the reply, for Insights
export default function WhatsAppSend({ whatsapp, picked, text, language, disabled, draft }) {
  const [confirming, setConfirming] = useState(false);
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  if (whatsapp.status === "sent" && !result) {
    return (
      <p className="flex items-center gap-1.5 rounded-xl bg-leaf-soft px-3 py-2.5 text-sm font-medium text-leaf">
        <Icon name="check" className="h-4 w-4" strokeWidth={2.2} />
        Already replied to this enquiry.
      </p>
    );
  }
  if (whatsapp.hoursLeft <= 0 && !result) {
    return (
      <p className="rounded-xl bg-madder-soft px-3 py-2.5 text-sm text-madder-dark">
        WhatsApp's 24-hour window has closed, so the app cannot reply. Copy the text and reply from your phone.
      </p>
    );
  }

  async function send() {
    setSending(true);
    setError("");
    try {
      const r = await sendWhatsApp(whatsapp.enquiryId, picked, text, language, draft);
      setResult(r);
      setConfirming(false);
      whatsapp.onSent();
    } catch (e) {
      setError(e.message);
    } finally {
      setSending(false);
    }
  }

  if (result) {
    return (
      <div className="space-y-1.5 rounded-xl bg-leaf-soft px-3 py-2.5 text-sm text-leaf">
        <p className="flex items-center gap-1.5 font-semibold">
          <Icon name="check" className="h-4 w-4" strokeWidth={2.2} />
          {result.dry_run ? "Test mode: nothing really sent" : "Sent on WhatsApp"} · {result.messages_sent} message
          {result.messages_sent > 1 ? "s" : ""}
        </p>
        {result.dry_run && <p className="text-xs">WHATSAPP_DRY_RUN is on, so the messages are in the server log.</p>}
        {result.failed_photos.length > 0 && (
          <p className="text-xs text-madder-dark">
            Photo not sent for {result.failed_photos.map((f) => f.design_id).join(", ")}. Send it from your phone.
          </p>
        )}
      </div>
    );
  }

  const photos = picked.slice(0, 5);
  return (
    <div className="space-y-2">
      {confirming ? (
        <div className="rounded-xl border border-leaf/40 bg-leaf-soft/60 p-3 text-sm">
          <p className="text-ink">
            Send to <span className="font-semibold">{whatsapp.buyerName || "the buyer"}</span>: this reply
            {photos.length > 0 && (
              <>
                {" "}
                and {photos.length} photo{photos.length > 1 ? "s" : ""} ({photos.join(", ")})
              </>
            )}
            ?
          </p>
          <div className="mt-2.5 flex gap-2">
            <button
              type="button"
              onClick={send}
              disabled={sending}
              className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-leaf py-2.5 text-sm font-semibold text-white hover:bg-leaf/90 disabled:opacity-50"
            >
              <Icon name="send" className="h-4 w-4" />
              {sending ? "Sending…" : "Send now"}
            </button>
            <button
              type="button"
              onClick={() => setConfirming(false)}
              disabled={sending}
              className="rounded-xl border border-line bg-card px-4 text-sm font-medium text-muted"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setConfirming(true)}
          disabled={disabled}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-leaf py-3 text-sm font-semibold text-white shadow-sm hover:bg-leaf/90 disabled:opacity-50"
        >
          <Icon name="send" className="h-4 w-4" />
          Send on WhatsApp
        </button>
      )}
      {error && <p className="text-sm text-madder">{error}</p>}
    </div>
  );
}
