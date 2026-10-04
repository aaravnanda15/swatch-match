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

export function getSettings() {
  return request("/api/settings");
}

// photo is a File (or null), text is a string. Sent as a form, like a normal upload.
export function sendEnquiry(photo, text) {
  const form = new FormData();
  if (photo) form.append("image", photo);
  form.append("text", text);
  return request("/api/enquiry", { method: "POST", body: form });
}

export function draftReply(enquiryId, picked, language) {
  return request("/api/reply", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enquiry_id: enquiryId, picked, language }),
  });
}

// Records the approved reply in the audit log. Nothing is sent to the buyer.
export function approveReply(enquiryId, picked, text, language) {
  return request("/api/approve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enquiry_id: enquiryId, picked, text, language }),
  });
}

export function getAudit() {
  return request("/api/audit");
}

export function uploadUrl(imageFile) {
  return `/api/uploads/${encodeURIComponent(imageFile)}`;
}
