// Small notice shown when the AI was not used, so staff know results come
// from the simpler keyword/photo matching.
export default function FallbackBanner({ reason }) {
  return (
    <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
      <span className="font-semibold">Basic mode.</span> {reason} Results still work, but unusual words may be
      missed.
    </p>
  );
}
