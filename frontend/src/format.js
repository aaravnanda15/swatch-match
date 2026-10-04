// Small helpers for showing numbers and dates the Indian way.

const INR = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

export function rupees(value) {
  return `₹${INR.format(value)}`;
}

// "2026-10-04 08:26:22" (UTC from SQLite) -> "4 Oct, 1:56 pm" in the user's time zone
export function shortDateTime(sqliteUtc) {
  const date = new Date(sqliteUtc.replace(" ", "T") + "Z");
  return date.toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}
