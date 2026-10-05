async function request(url, options) {
  let res;
  try {
    res = await fetch(url, options);
  } catch {
    throw new Error("Cannot reach the server. Is it running?");
  }
  if (!res.ok) {
    let message = "Something went wrong. Please try again.";
    try {
      const body = await res.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      // not JSON
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


export function getInbox() {
  return request("/api/inbox");
}

export function getInboxItem(id) {
  return request(`/api/inbox/${id}`);
}

export function dismissInboxItem(id) {
  return request(`/api/inbox/${id}/dismiss`, { method: "POST" });
}

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

// tz offset so "today" matches the shop's day, not UTC
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

export function saveStock(designId, quantity, rate) {
  return request(`/api/designs/${encodeURIComponent(designId)}/stock`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ quantity_available: quantity, rate }),
  });
}

// buyer chat (demo mode)
export function chatSend(phone, name, text, photo) {
  const form = new FormData();
  form.append("phone", phone);
  form.append("name", name);
  form.append("text", text);
  if (photo) form.append("image", photo);
  return request("/api/demo/chat/send", { method: "POST", body: form });
}

export function chatMessages(phone, after = 0) {
  return request(`/api/demo/chat/${encodeURIComponent(phone)}?after=${after}`);
}

export function getInboxChat(id) {
  return request(`/api/inbox/${id}/chat`);
}
