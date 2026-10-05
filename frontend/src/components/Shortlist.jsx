import { useState } from "react";
import { rupees } from "../format.js";
import ClarifyCard from "./ClarifyCard.jsx";
import FallbackBanner from "./FallbackBanner.jsx";
import Icon from "./Icon.jsx";
import ReplyBox from "./ReplyBox.jsx";
import ResultCard from "./ResultCard.jsx";
import TracePanel from "./TracePanel.jsx";



const MODE_TEXT = {
  image_only: "Photo",
  text_only: "Text",
  image_and_text: "Photo + text",
  vague: "Not clear yet",
};

// pre-tick up to 3 good in-stock matches, else the closest in-stock one
function defaultPicks(answer) {
  if (answer.clarifying_question) return [];
  const good = answer.results.filter((r) => r.in_stock && ["very_close", "similar"].includes(r.label));
  if (good.length > 0) return good.slice(0, 3).map((r) => r.design_id);
  const closest = answer.results.find((r) => r.in_stock);
  return closest ? [closest.design_id] : [];
}

// whatsapp: { enquiryId, status, hoursLeft, buyerName, onSent }, Inbox only
export default function Shortlist({ answer, onOpenImage, whatsapp }) {
  const [picked, setPicked] = useState(() => defaultPicks(answer));

  function togglePick(designId) {
    setPicked((list) => (list.includes(designId) ? list.filter((d) => d !== designId) : [...list, designId]));
  }
  const pickedInOrder = answer.results.map((r) => r.design_id).filter((d) => picked.includes(d));

  const understood = Object.values(answer.query.attributes);
  if (answer.query.max_rate) understood.push(`up to ${rupees(answer.query.max_rate)}`);
  if (answer.query.min_quantity) understood.push(`${answer.query.min_quantity} pcs`);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 className="font-display text-xl font-semibold tracking-tight">Shortlist</h2>
        <p className="text-xs text-faint">
          Enquiry #{answer.enquiry_id} · {MODE_TEXT[answer.mode]}
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

      {answer.fallback_mode && <FallbackBanner reason={answer.fallback_reason} />}

      {answer.clarifying_question && (
        <ClarifyCard
          question={answer.clarifying_question}
          enquiryId={answer.enquiry_id}
          language={answer.query.language}
          whatsapp={whatsapp}
        />
      )}

      {answer.no_match && !answer.clarifying_question && answer.results.length > 0 && (
        <div className="flex gap-2 rounded-xl border border-line bg-card px-3 py-2.5 text-sm">
          <Icon name="box" className="mt-px h-5 w-5 shrink-0 text-muted" />
          <p>
            <span className="font-semibold">No match in stock.</span>{" "}
            <span className="text-muted">These are the nearest alternatives. Tell the buyer honestly.</span>
          </p>
        </div>
      )}

      {answer.results.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-line p-6 text-center text-sm text-muted">
          Nothing in stock fits
          {answer.query.max_rate ? ` within ${rupees(answer.query.max_rate)}` : ""}.
          {answer.over_budget_removed > 0 && ` ${answer.over_budget_removed} designs were over budget.`}
        </div>
      ) : (
        <div className="space-y-2.5">
          {answer.results.map((r, i) => (
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

      {answer.over_budget_removed > 0 && answer.results.length > 0 && (
        <p className="text-xs text-faint">
          {answer.over_budget_removed} closer designs were hidden because they cost more than{" "}
          {rupees(answer.query.max_rate)}.
        </p>
      )}

      {answer.results.length > 0 && !answer.clarifying_question && (
        <ReplyBox
          enquiryId={answer.enquiry_id}
          picked={pickedInOrder}
          defaultLanguage={answer.query.language}
          whatsapp={whatsapp}
        />
      )}

      <TracePanel trace={answer.trace} weights={answer.weights} />
    </div>
  );
}
