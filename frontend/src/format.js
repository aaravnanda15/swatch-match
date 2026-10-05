const INR = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

export function rupees(value) {
  return `₹${INR.format(value)}`;
}

// SQLite gives UTC without a zone
export function shortDateTime(sqliteUtc) {
  const date = new Date(sqliteUtc.replace(" ", "T") + "Z");
  return date.toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}
