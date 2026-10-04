import { useEffect, useState } from "react";
import { getAttributes, getDesigns, imageUrl, saveTags } from "../api.js";
import { rupees } from "../format.js";
import Icon from "../components/Icon.jsx";
import ImageViewer from "../components/ImageViewer.jsx";

// Friendly labels for the attribute names in config.yaml
const LABELS = {
  garment_type: "Type",
  main_colour: "Main colour",
  secondary_colour: "2nd colour",
  pattern: "Pattern",
  border: "Border",
  fabric: "Fabric",
  work_type: "Work",
};

const SOURCE_BADGE = {
  gemini: { text: "Tagged by AI", style: "bg-indigo-soft text-indigo" },
  clip: { text: "Auto-tagged (basic)", style: "bg-saffron-soft text-[#8a5a12]" },
  manual: { text: "Checked by staff", style: "bg-leaf-soft text-leaf" },
};

const FILTERS = [
  { id: "all", label: "All" },
  { id: "unchecked", label: "Needs a check" },
  { id: "out", label: "Out of stock" },
];

export default function CataloguePage() {
  const [designs, setDesigns] = useState(null);
  const [attributes, setAttributes] = useState({});
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [viewing, setViewing] = useState(null);

  useEffect(() => {
    Promise.all([getDesigns(), getAttributes()])
      .then(([d, a]) => {
        setDesigns(d);
        setAttributes(a);
      })
      .catch((e) => setError(e.message));
  }, []);

  function replaceDesign(updated) {
    setDesigns((list) => list.map((d) => (d.design_id === updated.design_id ? updated : d)));
  }

  if (error) return <p className="rounded-xl bg-madder-soft p-3 text-sm text-madder-dark">{error}</p>;
  if (designs === null) return <p className="text-sm text-muted">Loading catalogue…</p>;
  if (designs.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-line p-5 text-sm text-muted">
        The catalogue is empty. Run <code className="rounded bg-line/60 px-1">python -m backend.ingest</code> to
        load <code className="rounded bg-line/60 px-1">catalogue/stock.csv</code>.
      </div>
    );
  }

  const unchecked = designs.filter((d) => d.tag_source !== "manual").length;
  const outOfStock = designs.filter((d) => d.quantity_available === 0).length;

  // Simple search over id, name and tag values, plus the filter chips
  const query = search.trim().toLowerCase();
  const shown = designs.filter((d) => {
    if (filter === "unchecked" && d.tag_source === "manual") return false;
    if (filter === "out" && d.quantity_available > 0) return false;
    if (!query) return true;
    const text = [d.design_id, d.name, ...Object.values(d.tags)].join(" ").toLowerCase();
    return text.includes(query);
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="font-display text-2xl font-semibold tracking-tight">Catalogue</h2>
          <p className="mt-1 text-sm text-muted">Correct tags here so matching works better. Stock and rate come from stock.csv.</p>
        </div>
        <dl className="flex gap-2 text-center">
          <Stat value={designs.length} label="designs" />
          <Stat value={designs.length - unchecked} label="checked" />
          <Stat value={outOfStock} label="out of stock" />
        </dl>
      </div>

      <div className="space-y-2.5">
        <label className="relative block">
          <Icon name="search" className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-faint" />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search: red, bandhani, D012…"
            className="w-full rounded-xl border border-line bg-card py-2.5 pr-3 pl-9 text-sm placeholder:text-faint focus:border-indigo focus:outline-none"
          />
        </label>
        <div className="flex flex-wrap gap-1.5">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              aria-pressed={filter === f.id}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                filter === f.id ? "border-ink bg-ink text-white" : "border-line bg-card text-muted hover:text-ink"
              }`}
            >
              {f.label}
              {f.id === "unchecked" && unchecked > 0 && <span className="ml-1 opacity-70">{unchecked}</span>}
            </button>
          ))}
          <span className="ml-auto self-center text-xs text-faint">
            {shown.length} of {designs.length}
          </span>
        </div>
      </div>

      {shown.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-line p-6 text-center text-sm text-muted">
          No designs match. Try another word or filter.
        </p>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {shown.map((d) => (
            <DesignCard
              key={d.design_id}
              design={d}
              attributes={attributes}
              onSaved={replaceDesign}
              onOpenImage={setViewing}
            />
          ))}
        </div>
      )}

      <ImageViewer design={viewing} onClose={() => setViewing(null)} />
    </div>
  );
}

function Stat({ value, label }) {
  return (
    <div className="min-w-16 rounded-xl border border-line bg-card px-2.5 py-1.5">
      <dt className="sr-only">{label}</dt>
      <dd className="font-display text-lg leading-tight font-semibold">{value}</dd>
      <dd className="text-[11px] text-muted">{label}</dd>
    </div>
  );
}

function DesignCard({ design, attributes, onSaved, onOpenImage }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(design.tags);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function startEditing() {
    setDraft(design.tags);
    setError("");
    setEditing(true);
  }

  async function save() {
    setSaving(true);
    setError("");
    try {
      onSaved(await saveTags(design.design_id, draft));
      setEditing(false);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  const outOfStock = design.quantity_available === 0;
  const badge = SOURCE_BADGE[design.tag_source];

  return (
    <div className="overflow-hidden rounded-2xl border border-line bg-card shadow-[0_1px_2px_rgb(35_29_24/0.05)]">
      <div className="flex gap-3 p-3">
        <button
          type="button"
          onClick={() => onOpenImage(design)}
          className="h-24 w-24 flex-none overflow-hidden rounded-xl bg-line"
          aria-label={`View photo of ${design.name}`}
        >
          <img src={imageUrl(design.image_file)} alt="" loading="lazy" className="h-full w-full object-cover" />
        </button>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium text-faint">{design.design_id}</p>
          <p className="truncate font-semibold text-ink">{design.name}</p>
          <p className="mt-0.5 text-sm">
            <span className="font-semibold">{rupees(design.rate)}</span>
            <span className="text-muted"> / {design.unit} · </span>
            {outOfStock ? (
              <span className="font-medium text-madder">Out of stock</span>
            ) : (
              <span className="text-leaf">{design.quantity_available} in stock</span>
            )}
          </p>
          {badge ? (
            <span className={`mt-1.5 inline-block rounded-full px-2 py-0.5 text-[11px] font-semibold ${badge.style}`}>
              {badge.text}
            </span>
          ) : (
            <span className="mt-1.5 inline-block rounded-full bg-line/60 px-2 py-0.5 text-[11px] text-muted">
              Not tagged yet
            </span>
          )}
        </div>
      </div>

      {!editing && (
        <div className="flex items-end justify-between gap-2 border-t border-line/70 px-3 py-2.5">
          <div className="flex flex-wrap gap-1">
            {/* Each tag value once; skip "none"/"unknown" which add nothing */}
            {[...new Set(Object.keys(LABELS).map((attr) => design.tags[attr]))]
              .filter((value) => value && !["none", "unknown"].includes(value))
              .map((value) => (
                <span key={value} className="rounded-full bg-paper px-2 py-0.5 text-xs text-muted ring-1 ring-line">
                  {value}
                </span>
              ))}
          </div>
          <button
            onClick={startEditing}
            className="flex shrink-0 items-center gap-1 rounded-lg px-2 py-1 text-sm font-semibold text-madder hover:bg-madder-soft"
          >
            <Icon name="edit" className="h-4 w-4" />
            Edit tags
          </button>
        </div>
      )}

      {editing && (
        <div className="space-y-2 border-t border-line/70 bg-paper/60 p-3">
          {Object.keys(LABELS).map((attr) => (
            <label key={attr} className="flex items-center justify-between gap-2 text-sm">
              <span className="text-muted">{LABELS[attr]}</span>
              <select
                value={draft[attr] || ""}
                onChange={(e) => setDraft({ ...draft, [attr]: e.target.value })}
                className="w-44 rounded-lg border border-line bg-card px-2 py-1.5 focus:border-indigo focus:outline-none"
              >
                {!draft[attr] && <option value="">Choose…</option>}
                {(attributes[attr] || []).map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
          ))}
          {error && <p className="text-sm text-madder">{error}</p>}
          <div className="flex gap-2 pt-1">
            <button
              onClick={save}
              disabled={saving}
              className="flex-1 rounded-xl bg-madder py-2.5 text-sm font-semibold text-white hover:bg-madder-dark disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save tags"}
            </button>
            <button
              onClick={() => setEditing(false)}
              disabled={saving}
              className="flex-1 rounded-xl border border-line bg-card py-2.5 text-sm font-medium text-muted"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
