// All calls to the backend go through this file.

async function request(url, options) {
  let res;
  try {
    res = await fetch(url, options);
  } catch {
    throw new Error("Cannot reach the server. Is it running?");
  }
  if (res.status === 401 && !url.startsWith("/api/login")) {
    // Staff passcode needed: App.jsx listens for this and shows the passcode screen
    window.dispatchEvent(new Event("auth-required"));
    throw new Error("Please enter the staff passcode.");
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

export function login(passcode) {
  return request("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ passcode }),
  });
}

export function logout() {
  return request("/api/logout", { method: "POST" });
}

export function getInbox() {
  return request("/api/inbox");
}

export function getInboxItem(id) {
  return request(`/api/inbox/${id}`);
}

export function dismissInboxItem(id) {
  return request(`/api/inbox/${id}/dismiss`, { method: "POST" });
}

// Sends the approved reply and the picked design photos to the buyer on WhatsApp
export function sendWhatsApp(enquiryId, picked, text, language) {
  return request("/api/whatsapp/send", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enquiry_id: enquiryId, picked, text, language }),
  });
}

export function getSamplePhotos() {
  return request("/api/demo/photos");
}

export function samplePhotoUrl(name) {
  return `/api/demo/photos/${encodeURIComponent(name)}`;
}

export function getDemoScenarios() {
  return request("/api/demo/scenarios");
}

export function simulateBuyer(scenarioId) {
  return request("/api/demo/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario_id: scenarioId }),
  });
}

// Shop's offset from UTC in minutes (India = 330), so days match the shop's calendar
export function getInsights(days = 7) {
  const tz = -new Date().getTimezoneOffset();
  return request(`/api/insights?days=${days}&tz_offset=${tz}`);
}

export function addSampleHistory() {
  return request("/api/demo/history", { method: "POST" });
}

export function clearSampleHistory() {
  return request("/api/demo/history", { method: "DELETE" });
}

// Staff edit stock and rate (saved to stock.csv and the database)
export function saveStock(designId, quantity, rate) {
  return request(`/api/designs/${encodeURIComponent(designId)}/stock`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ quantity_available: quantity, rate }),
  });
}
