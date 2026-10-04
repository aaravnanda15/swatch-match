// All calls to the backend go through this file.

async function request(url, options) {
  let res;
  try {
    res = await fetch(url, options);
  } catch {
    throw new Error("Cannot reach the server. Is it running?");
  }
  if (!res.ok) {
    // FastAPI puts error messages in "detail"
    let message = "Something went wrong. Please try again.";
    try {
      const body = await res.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      // response was not JSON; keep the generic message
    }
    throw new Error(message);
  }
  return res.json();
}

export function getHealth() {
  return request("/api/health");
}

export function getAttributes() {
  return request("/api/attributes");
}

export function getDesigns() {
  return request("/api/designs");
}

export function saveTags(designId, tags) {
  return request(`/api/designs/${encodeURIComponent(designId)}/tags`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(tags),
  });
}

export function imageUrl(imageFile) {
  return `/api/images/${encodeURIComponent(imageFile)}`;
}
