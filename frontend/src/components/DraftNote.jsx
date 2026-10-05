import Icon from "./Icon.jsx";

// Who wrote the draft: the AI (numbers checked against stock.csv) or the plain template.
export default function DraftNote({ source, needsStaff }) {
  return (
    <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px]">
      {source === "composed" && (
        <span className="flex items-center gap-1 rounded-full bg-indigo-soft px-2 py-0.5 font-semibold text-indigo">
          <Icon name="sparkle" className="h-3 w-3" />
          Written by AI · numbers checked against stock.csv
        </span>
      )}
      {source === "template" && (
        <span className="flex items-center gap-1 rounded-full bg-saffron-soft px-2 py-0.5 font-semibold text-[#6e4a10]">
          <Icon name="edit" className="h-3 w-3" />
          Plain reply, add a personal line?
        </span>
      )}
      {needsStaff && (
        <span className="flex items-center gap-1 rounded-full bg-madder-soft px-2 py-0.5 font-semibold text-madder-dark">
          <Icon name="question" className="h-3 w-3" />
          Staff to confirm: the buyer asked something we don't have on file
        </span>
      )}
    </div>
  );
}
