import { useEffect, useState } from "react";
import { getAttributes, getDesigns, imageUrl, saveTags } from "../api.js";

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
  gemini: { text: "Tagged by AI", style: "bg-sky-100 text-sky-800" },
  clip: { text: "Auto-tagged (basic)", style: "bg-amber-100 text-amber-800" },
  manual: { text: "Checked by staff", style: "bg-emerald-100 text-emerald-800" },
};

export default function CataloguePage() {
  const [designs, setDesigns] = useState(null);
  const [attributes, setAttributes] = useState({});
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");

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

  if (error) return <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>;
  if (designs === null) return <p className="text-sm text-stone-500">Loading catalogue...</p>;
  if (designs.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-stone-300 p-4 text-sm text-stone-600">
        The catalogue is empty. Run <code className="rounded bg-stone-100 px-1">python -m backend.ingest</code> to
        load <code className="rounded bg-stone-100 px-1">catalogue/stock.csv</code>.
      </div>
    );
  }

  // Simple search over id, name and tag values
  const query = search.trim().toLowerCase();
  const shown = designs.filter((d) => {
    if (!query) return true;
    const text = [d.design_id, d.name, ...Object.values(d.tags)].join(" ").toLowerCase();
    return text.includes(query);
  });
  const unchecked = designs.filter((d) => d.tag_source !== "manual").length;

  return (
    <div className="space-y-3">
      <input
        type="search"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search: red, bandhani, D012..."
        className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm"
      />
      <p className="text-xs text-stone-500">
        {shown.length} of {designs.length} designs · {unchecked} not yet checked by staff. Fix any wrong tag so
        matching works better.
      </p>
      {shown.map((d) => (
        <DesignCard key={d.design_id} design={d} attributes={attributes} onSaved={replaceDesign} />
      ))}
    </div>
  );
}

function DesignCard({ design, attributes, onSaved }) {
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
    <div className="overflow-hidden rounded-xl border border-stone-200 bg-white">
      <div className="flex gap-3 p-3">
        <img
          src={imageUrl(design.image_file)}
          alt={design.name}
          loading="lazy"
          className="h-24 w-24 flex-none rounded-lg bg-stone-100 object-cover"
        />
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium text-stone-500">{design.design_id}</p>
          <p className="truncate font-medium text-stone-900">{design.name}</p>
          <p className={`text-sm ${outOfStock ? "text-red-700" : "text-stone-700"}`}>
            {outOfStock ? "Out of stock" : `${design.quantity_available} in stock`} · ₹{design.rate} / {design.unit}
          </p>
          {badge ? (
            <span className={`mt-1 inline-block rounded-full px-2 py-0.5 text-xs ${badge.style}`}>{badge.text}</span>
          ) : (
            <span className="mt-1 inline-block rounded-full bg-stone-100 px-2 py-0.5 text-xs text-stone-600">
              Not tagged yet
            </span>
          )}
        </div>
      </div>

      {!editing && (
        <div className="border-t border-stone-100 px-3 py-2">
          <div className="flex flex-wrap gap-1">
            {/* Each tag value once; skip "none"/"unknown" which add nothing */}
            {[...new Set(Object.keys(LABELS).map((attr) => design.tags[attr]))]
              .filter((value) => value && !["none", "unknown"].includes(value))
              .map((value) => (
                <span key={value} className="rounded-full bg-stone-100 px-2 py-0.5 text-xs text-stone-700">
                  {value}
                </span>
              ))}
          </div>
          <button onClick={startEditing} className="mt-2 py-1 text-sm font-medium text-rose-700">
            Edit tags
          </button>
        </div>
      )}

      {editing && (
        <div className="space-y-2 border-t border-stone-100 bg-stone-50 p-3">
          {Object.keys(LABELS).map((attr) => (
            <label key={attr} className="flex items-center justify-between gap-2 text-sm">
              <span className="text-stone-600">{LABELS[attr]}</span>
              <select
                value={draft[attr] || ""}
                onChange={(e) => setDraft({ ...draft, [attr]: e.target.value })}
                className="w-44 rounded-md border border-stone-300 bg-white px-2 py-1.5"
              >
                {!draft[attr] && <option value="">Choose...</option>}
                {(attributes[attr] || []).map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
          ))}
          {error && <p className="text-sm text-red-700">{error}</p>}
          <div className="flex gap-2 pt-1">
            <button
              onClick={save}
              disabled={saving}
              className="flex-1 rounded-lg bg-rose-700 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save"}
            </button>
            <button
              onClick={() => setEditing(false)}
              disabled={saving}
              className="flex-1 rounded-lg border border-stone-300 bg-white py-2 text-sm font-medium text-stone-700"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
