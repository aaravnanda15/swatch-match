import { imageUrl } from "../api.js";
import { rupees } from "../format.js";
import Icon from "./Icon.jsx";

const LABEL_STYLE = {
  very_close: "bg-leaf-soft text-leaf",
  similar: "bg-indigo-soft text-indigo",
  alternative: "bg-saffron-soft text-[#8a5a12]",
  none: "bg-[#efe9e0] text-muted",
};

export default function ResultCard({ result, rank, picked, onTogglePick, onOpenImage, style }) {
  const r = result;
  const lowStock = r.in_stock && !r.enough_stock;
  const selectable = typeof onTogglePick === "function";

  return (
    <article
      style={style}
      className={`rise relative overflow-hidden rounded-2xl border bg-card shadow-[0_1px_2px_rgb(35_29_24/0.06)] transition-colors ${
        picked ? "border-madder ring-1 ring-madder" : "border-line"
      }`}
    >
      <div className="flex gap-3 p-3">
        <button
          type="button"
          onClick={() => onOpenImage(r)}
          className="relative h-28 w-24 shrink-0 overflow-hidden rounded-xl bg-line sm:h-32 sm:w-28"
          aria-label={`View photo of ${r.name}`}
        >
          <img src={imageUrl(r.image_file)} alt="" className="h-full w-full object-cover" />
          <span className="absolute top-1.5 left-1.5 flex h-6 w-6 items-center justify-center rounded-full bg-ink/80 text-xs font-semibold text-white">
            {rank}
          </span>
        </button>

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <span
              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${LABEL_STYLE[r.label]}`}
            >
              {r.label_text}
              <span className="font-medium opacity-70">· {Math.floor(r.score * 100)}%</span>
            </span>
            {selectable && (
              <button
                type="button"
                onClick={() => onTogglePick(r.design_id)}
                aria-pressed={picked}
                aria-label={picked ? `Remove ${r.design_id} from reply` : `Add ${r.design_id} to reply`}
                className={`-mt-0.5 -mr-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border transition-colors ${
                  picked ? "border-madder bg-madder text-white" : "border-line bg-card text-faint hover:text-ink"
                }`}
              >
                <Icon name="check" className="h-4 w-4" strokeWidth={2.4} />
              </button>
            )}
          </div>

          <h3 className="mt-1.5 truncate text-[15px] leading-snug font-semibold text-ink">
            {r.name}
            <span className="ml-1.5 text-xs font-medium text-faint">{r.design_id}</span>
          </h3>

          <p className="mt-0.5 line-clamp-2 text-[13px] leading-snug text-muted">{r.reason}</p>

          <p className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[13px]">
            <span className="font-semibold text-ink">
              {rupees(r.rate)}
              <span className="font-normal text-muted"> / {r.unit}</span>
            </span>
            <span className="text-faint">·</span>
            {r.in_stock ? (
              <span className={lowStock ? "font-medium text-[#8a5a12]" : "text-leaf"}>
                {r.quantity_available} in stock{lowStock ? " (less than asked)" : ""}
              </span>
            ) : (
              <span className="font-medium text-madder">Out of stock</span>
            )}
          </p>
        </div>
      </div>

      {r.shade_note && (
        <p className="flex items-center gap-1.5 border-t border-line/70 bg-paper/60 px-3 py-1.5 text-xs text-muted">
          <Icon name="drop" className="h-3.5 w-3.5 text-saffron" />
          Shade may differ in photo. Check the colour before confirming.
        </p>
      )}
    </article>
  );
}
