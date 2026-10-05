import Icon from "./Icon.jsx";

// tool name -> what staff see
const TOOL_NAMES = {
  image_search: "Compared the photo with the catalogue",
  describe_photo: "Described the photo",
  parse_text_to_attributes: "Read the message",
  ask_clarifying_question: "Wrote a question for the buyer",
  attribute_filter: "Matched the details to tags",
  text_search: "Matched the words to photos",
  narrow_to_lookalikes: "Kept the lookalikes",
  check_stock: "Checked stock and rate",
};

const SIGNAL_NAMES = { image: "photo", attributes: "details", text: "words" };

function show(value) {
  if (value && typeof value === "object") {
    return Object.entries(value)
      .map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`)
      .join(", ");
  }
  return String(value);
}

export default function TracePanel({ trace, weights, elapsedMs }) {
  // some steps run in parallel, so prefer the real wall-clock time
  const totalMs = elapsedMs ?? trace.reduce((sum, s) => sum + s.ms, 0);
  const mix = Object.entries(weights)
    .filter(([, w]) => w > 0)
    .map(([k, w]) => `${Math.round(w * 100)}% ${SIGNAL_NAMES[k]}`)
    .join(" + ");

  return (
    <details className="group rounded-2xl border border-line bg-card">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-3 select-none [&::-webkit-details-marker]:hidden">
        <Icon name="sparkle" className="h-4 w-4 text-indigo" />
        <span className="flex-1 text-sm font-semibold text-ink">How this shortlist was made</span>
        <span className="text-xs text-faint tabular-nums">
          {trace.length} steps · {totalMs < 1000 ? `${totalMs} ms` : `${(totalMs / 1000).toFixed(1)} s`}
        </span>
        <Icon name="chevron" className="h-4 w-4 text-faint transition-transform group-open:rotate-90" />
      </summary>

      <div className="border-t border-line/70 px-3 pt-3 pb-4">
        <ol className="relative space-y-4 border-l border-line pl-5">
          {trace.map((s) => (
            <li key={s.step} className="relative">
              <span className="absolute top-0.5 -left-[29px] flex h-[17px] w-[17px] items-center justify-center rounded-full bg-indigo text-[10px] font-semibold text-white ring-4 ring-card">
                {s.step}
              </span>
              <div className="flex flex-wrap items-baseline justify-between gap-x-2">
                <p className="text-sm font-semibold text-ink">{TOOL_NAMES[s.tool] || s.tool}</p>
                <span className="text-[11px] text-faint tabular-nums">{s.ms} ms</span>
              </div>
              <p className="text-xs text-muted">{s.why}</p>
              <dl className="mt-1.5 grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5 rounded-lg bg-paper px-2.5 py-1.5 text-xs">
                <dt className="text-faint">in</dt>
                <dd className="break-words text-ink">{show(s.input)}</dd>
                <dt className="text-faint">out</dt>
                <dd className="break-words text-ink">{show(s.output)}</dd>
              </dl>
              <code className="mt-1 block text-[10px] text-faint">{s.tool}()</code>
            </li>
          ))}
        </ol>
        {mix && (
          <p className="mt-4 rounded-lg bg-indigo-soft/60 px-2.5 py-2 text-xs text-indigo">
            <span className="font-semibold">Score</span> = {mix}. Labels, reasons and stock lines are computed, not
            written by AI.
          </p>
        )}
      </div>
    </details>
  );
}
