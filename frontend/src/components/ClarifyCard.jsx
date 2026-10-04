import { useState } from "react";
import { approveReply } from "../api.js";
import { copyText } from "../clipboard.js";
import Icon from "./Icon.jsx";

// Shown when the enquiry is too vague: one question to send back to the buyer.
export default function ClarifyCard({ question, enquiryId, language }) {
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  // Logged like any approved reply, then copied for pasting into WhatsApp
  async function approve() {
    setError("");
    try {
      await approveReply(enquiryId, [], question, language);
      await copyText(question);
      setDone(true);
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div className="rise rounded-2xl border border-indigo/25 bg-indigo-soft/60 p-3">
      <p className="flex items-center gap-1.5 text-sm font-semibold text-indigo">
        <Icon name="question" className="h-4 w-4" />
        Not clear yet. Ask the buyer one question
      </p>
      {/* Looks like an outgoing chat message */}
      <div className="mt-2.5 ml-auto max-w-[92%] rounded-2xl rounded-tr-md bg-[#dcf3d8] px-3 py-2 text-[15px] leading-snug text-ink shadow-sm">
        {question}
      </div>
      <div className="mt-2.5 flex items-center justify-between gap-2">
        <p className="text-xs text-muted">The designs below are only a best guess.</p>
        <button
          type="button"
          onClick={approve}
          className="flex shrink-0 items-center gap-1.5 rounded-lg bg-indigo px-3 py-1.5 text-sm font-semibold text-white hover:bg-indigo/90"
        >
          <Icon name={done ? "check" : "copy"} className="h-4 w-4" />
          {done ? "Copied & logged" : "Approve & copy"}
        </button>
      </div>
      {error && <p className="mt-2 text-sm text-madder">{error}</p>}
    </div>
  );
}
