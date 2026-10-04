import { imageUrl } from "../api.js";

// Simple shortlist for step 3. Step 4 turns each row into a full result card
// with a label, a one-line reason and the shade note.
export default function ResultList({ results }) {
  if (results.length === 0) {
    return <p className="rounded-lg bg-stone-100 p-3 text-sm text-stone-600">No designs found within the budget.</p>;
  }
  return (
    <ol className="space-y-2">
      {results.map((r) => (
        <li key={r.design_id} className="flex gap-3 rounded-xl border border-stone-200 bg-white p-2">
          <img
            src={imageUrl(r.image_file)}
            alt={r.name}
            className="h-20 w-20 shrink-0 rounded-lg object-cover"
          />
          <div className="min-w-0 flex-1 text-sm">
            <p className="text-xs text-stone-500">{r.design_id}</p>
            <p className="truncate font-medium text-stone-900">{r.name}</p>
            <p className={r.in_stock ? "text-stone-700" : "text-red-700"}>
              {r.in_stock ? `${r.quantity_available} in stock` : "Out of stock"} · ₹{r.rate} / {r.unit}
            </p>
            <p className="text-xs text-stone-500">Match score {Math.round(r.score * 100)}%</p>
          </div>
        </li>
      ))}
    </ol>
  );
}
