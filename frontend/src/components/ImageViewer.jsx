import { useEffect } from "react";
import { imageUrl } from "../api.js";
import Icon from "./Icon.jsx";

// Full-screen photo. Closes on tap outside, the X button or Escape.
export default function ImageViewer({ design, onClose }) {
  useEffect(() => {
    if (!design) return;
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [design, onClose]);

  if (!design) return null;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={design.name}
      onClick={onClose}
      className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-ink/85 p-4"
    >
      <button
        type="button"
        onClick={onClose}
        className="absolute top-4 right-4 flex h-10 w-10 items-center justify-center rounded-full bg-white/15 text-white"
        aria-label="Close"
      >
        <Icon name="x" />
      </button>
      <img
        src={imageUrl(design.image_file)}
        alt={design.name}
        onClick={(e) => e.stopPropagation()}
        className="max-h-[78vh] max-w-full rounded-xl object-contain shadow-2xl"
      />
      <p className="mt-3 text-center text-sm text-white/90">
        <span className="font-semibold">{design.design_id}</span> · {design.name}
      </p>
    </div>
  );
}
