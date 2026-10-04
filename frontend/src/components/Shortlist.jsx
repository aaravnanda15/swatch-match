import { useState } from "react";
import { rupees } from "../format.js";
import ClarifyCard from "./ClarifyCard.jsx";
import FallbackBanner from "./FallbackBanner.jsx";
import Icon from "./Icon.jsx";
import ReplyBox from "./ReplyBox.jsx";
import ResultCard from "./ResultCard.jsx";
import TracePanel from "./TracePanel.jsx";

// The agent's answer for one enquiry: what was understood, notices, the
// result cards (tick to offer), the reply box and the trace. Used by the
// Enquiry tab and the WhatsApp Inbox.


const MODE_TEXT = {
  image_only: "Photo",
  text_only: "Text",
  image_and_text: "Photo + text",
  vague: "Not clear yet",
};

// Ticked at the start: in-stock designs labelled Very close or Similar (up to 3)
function defaultPicks(result) {
  if (result.clarifying_question) return [];
  const good = result.results.filter((r) => r.in_stock && ["very_close", "similar"].includes(r.label));
  return good.slice(0, 3).map((r) => r.design_id);
}

// whatsapp (optional): { enquiryId, status, hoursLeft, buyerName, onSent } for Inbox enquiries
export default function Shortlist({ result, onOpenImage, whatsapp }) {
  const [picked, setPicked] = useState(() => defaultPicks(result));

  function togglePick(designId) {
    setPicked((list) => (list.includes(designId) ? list.filter((d) => d !== designId) : [...list, designId]));
  }
  // Keep the reply in shortlist order, whatever order things were ticked
  const pickedInOrder = result.results.map((r) => r.design_id).filter((d) => picked.includes(d));

  const understood = Object.values(result.query.attributes);
  if (result.query.max_rate) understood.push(`up to ${rupees(result.query.max_rate)}`);
  if (result.query.min_quantity) understood.push(`${result.query.min_quantity} pcs`);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 className="font-display text-xl font-semibold tracking-tight">Shortlist</h2>
        <p className="text-xs text-faint">
          Enquiry #{result.enquiry_id} · {MODE_TEXT[result.mode]}
        </p>
      </div>

      {understood.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <span className="text-muted">Understood:</span>
          {understood.map((u) => (
            <span key={u} className="rounded-full bg-indigo-soft px-2 py-0.5 font-medium text-indigo">
              {u}
            </span>
          ))}
        </div>
      )}

      {result.fallback_mode && <FallbackBanner reason={result.fallback_reason} />}

      {result.clarifying_question && (
        <ClarifyCard
          question={result.clarifying_question}
          enquiryId={result.enquiry_id}
          language={result.query.language}
          whatsapp={whatsapp}
        />
      )}

      {result.no_match && !result.clarifying_question && result.results.length > 0 && (
        <div className="flex gap-2 rounded-xl border border-line bg-card px-3 py-2.5 text-sm">
          <Icon name="box" className="mt-px h-5 w-5 shrink-0 text-muted" />
          <p>
            <span className="font-semibold">No close match in stock.</span>{" "}
            <span className="text-muted">These are the nearest alternatives. Tell the buyer honestly.</span>
          </p>
        </div>
      )}

      {result.results.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-line p-6 text-center text-sm text-muted">
          Nothing in stock fits
          {result.query.max_rate ? ` within ${rupees(result.query.max_rate)}` : ""}.
          {result.over_budget_removed > 0 && ` ${result.over_budget_removed} designs were over budget.`}
        </div>
      ) : (
        <div className="space-y-2.5">
          {result.results.map((r, i) => (
            <ResultCard
              key={r.design_id}
              result={r}
              rank={i + 1}
              onOpenImage={onOpenImage}
              picked={picked.includes(r.design_id)}
              onTogglePick={togglePick}
              style={{ animationDelay: `${i * 50}ms` }}
            />
          ))}
        </div>
      )}

      {result.over_budget_removed > 0 && result.results.length > 0 && (
        <p className="text-xs text-faint">
          {result.over_budget_removed} closer designs were hidden because they cost more than{" "}
          {rupees(result.query.max_rate)}.
        </p>
      )}

      {result.results.length > 0 && !result.clarifying_question && (
        <ReplyBox
          enquiryId={result.enquiry_id}
          picked={pickedInOrder}
          defaultLanguage={result.query.language}
          whatsapp={whatsapp}
        />
      )}

      <TracePanel trace={result.trace} weights={result.weights} />
    </div>
  );
}
