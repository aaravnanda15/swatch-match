// All calls to the backend go through this file.

export async function getHealth() {
  const res = await fetch("/api/health");
  if (!res.ok) throw new Error("Server not reachable");
  return res.json();
}
