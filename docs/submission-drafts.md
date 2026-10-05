# Project submission drafts

Two drafts of the hackathon form. Fill every `[ ... ]` yourself. Only claim what that person really did:
the form says roles are cross-checked against the contribution text.

---

## Draft 1: Backend, Product / Research, Presentation / Demo

**Full Name:** [exact name for the certificate]

**Email Address:** [email registered on Unstop]

**Team Name:** [FULL TEAM NAME IN CAPITALS, exactly as on Unstop]

**Team Leader or Team Member:** [pick one]

**Your role(s):** Backend, Product / Research, Presentation / Demo

**What did YOU personally build?**

Built the FastAPI backend of Swatch Match: the agent router that turns a buyer's WhatsApp photo or text into a
5-design shortlist (image search, attribute filter, stock check), the CLIP vector index and weighted scoring,
and the SQLite data layer with stock.csv as the single source of truth for stock and rates. Built the WhatsApp
Business Cloud API integration (signed webhook, duplicate skipping, photo + text merging, 24-hour reply window)
and the per-buyer chat state machine that reads quantities, unit mix-ups and off-topic messages. Built the
Insights API for reply speed and missed demand, the multi-turn pytest suite and evaluate.py (94% top-1, 100%
top-5). Researched how fabric and saree wholesalers handle WhatsApp enquiries in Hindi, Gujarati and Hinglish,
and built demo mode (simulated buyers, QR buyer-chat page, sample week) for the live demo and pitch.

---

## Draft 2: Frontend, AI / ML, Design / UI-UX

**Full Name:** [exact name for the certificate]

**Email Address:** [email registered on Unstop]

**Team Name:** [FULL TEAM NAME IN CAPITALS, exactly as on Unstop]

**Team Leader or Team Member:** [pick one]

**Your role(s):** Frontend, AI / ML, Design / UI-UX

**What did YOU personally build?**

Built the React + Vite + Tailwind frontend of Swatch Match: the Inbox, Enquiry, Catalogue (stock and price
editing), Insights and Log tabs, photo paste and drag-drop straight from WhatsApp Web, shortlist cards with
Very close / Similar / Alternative labels, the editable 4-language reply box with Approve & copy, the "How this
shortlist was made" trace panel, and the WhatsApp-style buyer chat page. On AI / ML, built the CLIP ViT-B/32
image and text matching, the Gemini prompts for photo tagging, enquiry parsing, clarifying questions and
message classification (strict JSON limited to the shop's own vocabulary), the CLIP zero-shot tagging fallback,
and the English / Hindi / Gujarati / Hinglish keyword parser for Basic mode. Designed the mobile-first,
staff-approves-everything UI so a shop worker can reply to a buyer in seconds.

---

## About the Project (same answers in both drafts)

**Theme:** [pick from the official track list, for example the AI for small business / commerce / Bharat track
if one exists. Do not invent a track.]

**Project Name:** Swatch Match

**What problem are you solving?**

Small fabric and saree wholesalers lose time and sales matching buyers' WhatsApp photo and text enquiries to
their own stock by memory.

**Explain the problem in detail**

Small textile and saree wholesalers in India get dozens of enquiries a day on WhatsApp. Buyers send a photo,
a short message, or both, often in Hindi, Gujarati or Hinglish: "isme blue chahiye", "लाल बांधनी साड़ी 2000
तक". Staff then search the shelves from memory, check stock and rate by hand, and type a reply. This is slow,
depends on whoever is on duty, and breaks down at busy times. Buyers who wait go to the next shop, and the
owner never learns what buyers asked for that was not in stock, so restocking is guesswork.

**What is your solution?**

Swatch Match is a web app for shop staff. They paste a buyer's enquiry (photo, text or both), or it arrives
by itself from WhatsApp in the Inbox. In seconds the app shortlists the 5 closest designs from the shop's own
catalogue, each with a label (Very close / Similar / Alternative), a one-line reason and the real stock and
rate from the shop's stock file. Vague messages get one clarifying question in the buyer's language. Staff
tick the designs to offer, edit the drafted reply in English, Hindi, Hinglish or Gujarati, and approve it;
with WhatsApp connected, the reply and design photos go to the buyer. The app keeps chat context (quantities,
unit mix-ups, follow-up questions), filters spam and time-wasters, and its Insights tab shows reply speed and
missed demand, a restocking list written by the buyers.

**Who are your target users?**

Staff and owners of small and medium fabric, saree and dupatta wholesalers and retailers in India who sell
over WhatsApp, and by extension any small shop with a photo-heavy catalogue and WhatsApp buyers.

**What makes it distinctive or original?**

- It matches against the shop's own stock, not the internet, and the stock and price always come from the
  shop's file, never from the AI.
- It understands photo + text together ("this design but in blue": the photo picks lookalikes, the words
  re-rank them).
- It works in Hindi, Gujarati and Hinglish, and replies in the buyer's language.
- Nothing reaches a buyer until staff approve it; every step is shown in a trace panel.
- It still works with no AI key (Basic mode with CLIP and a keyword list).
- It turns enquiries into business data: missed demand and out-of-stock best matches.

**Tech stack, models and APIs used**

Backend: Python 3.11, FastAPI, Uvicorn, SQLite, NumPy, Pillow. Frontend: React 19, Vite, Tailwind CSS.
Models: OpenAI CLIP ViT-B/32 via sentence-transformers (image and text embeddings, zero-shot tagging),
Google Gemini (gemini-3.5-flash-lite) through the google-genai SDK. APIs: Meta WhatsApp Business Cloud API
(webhooks and sending). Testing: pytest and a custom top-1 / top-5 evaluation script. Hosting for the demo:
GitHub Codespaces and a Cloudflare quick tunnel; Docker for deployment.

**Prompt architecture and AI workflow**

A fixed router, not a free-running agent. For a photo, CLIP turns it into a 512-number vector and compares it
with every catalogue photo in one matrix multiply; Gemini describes the photo as tags chosen only from the
shop's allowed vocabulary. For text, Gemini extracts attributes, budget, quantity and language as strict JSON
(values copied from an allowed list, buyer text wrapped as data so instructions inside it are ignored); a
4-language keyword parser is the fallback. The score is a weighted mix of photo similarity, tag match and CLIP
text similarity, with weights set in config. Over-budget designs are dropped and stock is checked against
stock.csv. For chats, each buyer has a saved state (request, designs shown, quantity, pending question,
stage); every new message goes to Gemini with that state, the pending question and recent history, and comes
back as a labelled intent. The app then decides the next step, and replies are built from templates with
numbers filled from the database, so the AI cannot invent a price or stock figure.

**Agents, chains or evaluation methods**

Agent: a tool-calling router (image_search, describe_photo, parse_text_to_attributes, attribute_filter,
text_search, check_stock, ask_clarifying_question, draft_reply) that runs in a fixed, explainable order and
logs every call to a trace panel. Evaluation: evaluate.py measures top-1 and top-5 accuracy on 32 test
enquiries (photo, text in 4 languages, photo + text): 94% top-1 and 100% top-5 in Basic mode, and refuses to
run if a test photo is identical to a catalogue photo. A pytest suite runs multi-turn chats (unit mix-ups,
swearing, spam, 40 turns of nonsense, changed requests) with and without Gemini and checks that every number
in a reply exists in the stock file.

---

## Project Links

**GitHub repository link:** https://github.com/aaravnanda15/swatch-match [make sure the repo is set to
Public before submitting]

**Live deployed project link:** [Codespaces public link `https://<name>-7860.app.github.dev` or a Cloudflare
tunnel link. Both stop when the codespace or laptop stops, so keep it running during judging.]

**Demo video link:** [unlisted YouTube or Drive link, sharing set to "Anyone with the link"]
