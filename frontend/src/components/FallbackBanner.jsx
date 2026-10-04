import Icon from "./Icon.jsx";

// Small notice shown when the AI was not used, so staff know results come
// from the simpler keyword/photo matching.
export default function FallbackBanner({ reason }) {
  return (
    <div className="flex gap-2 rounded-xl border border-saffron/40 bg-saffron-soft px-3 py-2 text-xs leading-relaxed text-[#6e4a10]">
      <Icon name="info" className="mt-px h-4 w-4 shrink-0" />
      <p>
        <span className="font-semibold">Basic mode.</span> {reason} Results still work, but unusual words may be
        missed.
      </p>
    </div>
  );
}
