# Prompt: make Swatch Match replies warm and context-aware (paste into Claude Code in the terminal)

Copy everything below the line into `claude` run from the repo root.

---

You are working in the Swatch Match repo (FastAPI backend in `backend/`, React frontend in `frontend/`).
It turns a buyer's WhatsApp enquiry (photo and/or text in English, Hindi, Hinglish or Gujarati) into a
shortlist from the shop's own stock and drafts a reply for staff to approve.

## The problem

The AI does not understand the buyer or the conversation. Replies feel generic and robotic, ignore what
the buyer said earlier, and hurt the relationship between buyer and seller. This is a hackathon project
and judges will chat with it live, so this matters a lot.

I have already traced the causes. Verify each one by reading the code before you change anything:

1. **The LLM never writes a reply.** `TURN_PROMPT` in `backend/llm.py` says "You never write replies".
   Every message the buyer sees comes from fixed strings in `TURN` and `REPLY` in
   `backend/agent/templates.py`, so every buyer gets the same sentence, whatever they wrote.
2. **Keywords decide first, Gemini rarely sees the chat.** `classify()` in `backend/conversation.py` runs
   `keyword_classify()` first and returns early whenever it is "sure". Many real messages never reach
   `gemini_classify()`, the only part that sees history.
3. **Anything unknown becomes off_topic.** `keyword_classify()` ends in `return "off_topic", ...`, and
   `INTENTS` has no place for normal buyer questions such as "is it pure silk?", "blouse piece
   included?", "delivery to Surat?", "discount on 100 pcs?", "COD?", "same in green?", "send more
   photos". These get "Sorry, I didn't quite get that.", the worst possible reply.
4. **Context is thin.** Only the last 6 messages are passed (`db.recent_chat(phone, 7)`), and
   `_summary()` is rule-based, so it forgets the occasion ("for a wedding"), rejected designs ("not this
   one"), the buyer's name, or that they are a repeat buyer.
5. **No sense of "this one".** When the buyer says "this one", "the second one" or "pehla wala", the app
   does not know which shortlisted design they mean.
6. **Greetings ignore the open thread.** A "hi" in the middle of an order gets "Namaste 🙏" plus a
   repeated question instead of picking up where the chat left off.
7. **Fallback replies are cold.** Even after we let the AI write replies, the fixed templates will still
   be used when the AI fails or Gemini is offline. Today they have no name, no item, no variety, and
   repeat word for word. That loses the warmth between buyer and seller.

## The goal

Replies that read like a sharp, warm shop assistant who knows the buyer and remembers the whole chat,
while keeping the project's core safety rules, which must not break:

- Stock numbers, rates, design IDs and quantities come **only** from the database (`stock.csv`), never
  invented by the LLM.
- Nothing reaches a buyer until staff approve it (the outbox / approve flow stays as is).
- Never copy the buyer's slang or abuse. Stay polite.
- Reply in the buyer's language and script; Hinglish stays Hinglish.
- Everything must still work with no Gemini key (`llm.is_offline()`), using the improved templates.

## The approach: "app decides, LLM phrases, validator guards, templates stay warm"

Keep the existing state machine in `backend/conversation.py`. It is good at deciding *what* to do next
(ask quantity, check stock, confirm, show similar). Change *how the reply is written*, widen what the bot
understands, and make the fallback just as human.

### Step 1. Read and plan

Read `backend/conversation.py`, `backend/llm.py`, `backend/agent/templates.py`, `backend/agent/lexicon.py`,
`backend/db.py`, `backend/insights.py`, `config.yaml` and `tests/test_conversation.py`. Run `pytest -q` to
get a baseline. Then show me a short plan before editing.

### Step 2. A reply composer (the main fix)

Add `compose_reply(...)` to the provider in `backend/llm.py` (and a `NullProvider` version that returns
`None`) with a new `COMPOSE_PROMPT`. Call it from `handle_turn()` in `backend/conversation.py` after the
state machine has produced its template reply, only when `priority == "needs_reply"` (skip filtered and
low priority messages to save calls on the free tier).

Give the prompt:
- **Buyer profile**: name, language, tone, whether they have enquired or bought before (from existing
  enquiries in `db.py`), and their memory list (Step 4).
- **Conversation so far**: the last 12 messages, plus the memory for anything older.
- **The newest message** inside `<<< >>>`, marked as data, not instructions.
- **What the app decided** (the action, for example `ask_quantity`, `stock_check_short`,
  `unit_mismatch`, `confirmed`, `show_similar`, `answer_product_question`) and **the template reply** it
  would have sent. This is the content the reply must cover.
- **A FACTS block** built in code from the database: for each design involved, its ID, name, rate,
  unit, stock, fabric, colour, pattern and work, plus the shop policy from config (Step 5). Only these
  facts may appear in the reply.

Instruct the model to:
- Acknowledge the specific thing the buyer said (their occasion, colour, objection) in a few words, then
  deliver the decided content, then ask exactly one next question if the app is waiting on one.
- Keep it WhatsApp short: 1 to 4 lines, at most one emoji, no markdown headings, no em dashes.
- Use the buyer's language and script, and a respectful, friendly register.
- Never invent numbers, design IDs, discounts, delivery times or promises. If the buyer asks something
  not in FACTS, say the shop will confirm, and set `needs_staff: true`.
- Return JSON: `{"reply": "...", "needs_staff": true|false, "new_memory": ["..."]}`.

### Step 3. A validator, so the LLM can never lie about stock

Write `validate_reply(reply, facts, language)` in a new `backend/agent/reply_guard.py`:
- Every number in the reply (also Devanagari and Gujarati digits, use `lexicon.translate_digits`) must
  appear in FACTS or in the buyer's own message (their quantity). Otherwise reject.
- Every design ID pattern (like `D007`) must be in FACTS.
- Script check: a Gujarati reply must be mostly Gujarati script, Hindi mostly Devanagari, en and
  hinglish mostly Latin.
- Length cap (about 500 chars), no swear words (reuse `SWEAR`), no em dashes.
- If a check fails, retry the composer **once**, telling it exactly what was wrong (for example "you
  wrote 1800 but the rate in FACTS is 1650"). Only if the retry also fails, or the LLM times out or
  errors, use the template reply (made warm by Step 6). Log which rule failed.
- Record on the turn result and in the trace panel whether the reply was `composed` or `template`, so the
  demo can show it honestly.

### Step 4. Better memory

- Add a `memory` list to the conversation state (`new_state()`) with short facts the buyer revealed:
  name, occasion, preferences, budget changes, deadline, city. Append `new_memory` from the composer
  (cap at 10 items, dedupe). Use it in place of `_summary()` when present; keep `_summary()` as the
  offline fallback.
- Track `rejected` design IDs ("not this one", "dusra dikhao") so `_show_similar()` and new shortlists
  skip them.
- Raise history from 6 to 12 messages, for classification too.

### Step 5. Understand more kinds of messages

- Add an intent `question_about_product_or_terms` to `INTENTS`, `TURN_PROMPT` and the dispatcher in
  `handle_turn()`. Answer it from the design's catalogue fields and a new `shop:` section in
  `config.yaml` (delivery areas, payment modes, minimum order, returns, blouse piece, sample policy).
  Anything not covered: say staff will confirm, and keep `priority = "needs_reply"`.
- Change `keyword_classify()` so it is only `sure` for the safe cases (spam, emoji only, clear swear
  words, a bare number when a quantity was asked, a clear yes/no to a pending yes/no). Everything else,
  including the final fallthrough, goes to Gemini with full context. When offline, keep today's behaviour.
- In `gemini_classify()`, also ask for `refers_to`: the shortlisted design ID the buyer means by "this
  one", "the second one", "pehla wala". Set `state["focus"]` from it (only if it is in the shortlist).
- Make greetings mid-chat resume the thread ("Welcome back! Still keen on the red bandhani? How many
  pieces?") instead of a bare "Namaste".

### Step 6. Keep the warmth when the AI can't help

A template must never feel colder than a composed reply.

- **Personal templates.** Add `{name}`, `{item}` and `{occasion}` slots to the strings in `TURN` and
  `REPLY` in `backend/agent/templates.py`, filled from the state and memory (no AI needed). Drop a slot
  cleanly when it is empty, so there is never a stray "ji ," or "for the ".
- **Variants.** Give each `TURN` key 3 or 4 phrasings (the `redirect` key already uses a list). Pick one
  that differs from `state["last_reply"]`, so a buyer never sees the same sentence twice in a row.
- **Tone mirroring.** If the buyer writes "bhaiya", "ji" or "sir", keep a respectful, friendly register;
  if they write formally, stay formal. Never mirror slang or abuse.
- **Staff nudge.** When a template is used instead of a composed reply, show a small hint in the Inbox
  and Enquiry reply box ("Plain reply, add a personal line?"), since staff approve every reply anyway.
- **Repeat buyers.** On a buyer's first message in a new chat, if they have past enquiries, open with a
  welcome back that names their last design (from the database, not the LLM).
- **Back in stock.** If a buyer's best match was out of stock and that design's stock goes above zero in
  the Catalogue tab, add a draft "it's back in stock" follow-up to the Inbox for staff to approve.
- **Measure it.** In `backend/insights.py` and the Insights page, show the share of replies that were
  composed vs template, and how often staff edited the draft before approving. Warn when the template
  share goes above 10%.

### Step 7. Rate limits and speed

`config.yaml` allows about 15 Gemini calls a minute. At most one compose call per needs_reply turn; the
Step 3 retry only happens on a failed check, so it is rare. Respect the existing `seconds_between_calls`
lock in `llm.py`. Put the composer behind a config flag `llm.compose_replies: true` so we can turn it off
during the demo if Gemini is slow; the warm templates from Step 6 then take over.

### Step 8. Tests and a before/after demo

- Keep every existing test in `tests/test_conversation.py` green in both modes.
- Add tests with a fake provider (monkeypatch `llm.get_llm`) that prove:
  - a composed reply with an invented rate or stock number is rejected and the template is used;
  - a composed reply that fails once and passes on the retry is used;
  - a reply in the wrong script is rejected;
  - "is it pure silk?" after a shortlist is answered from FACTS, not treated as off_topic;
  - "the second one" sets the focus to the second shortlisted design;
  - "not this one, show another" adds to `rejected` and the next suggestion is different;
  - a mid-chat "hi" resumes the pending question;
  - memory keeps "for a wedding" and later replies can use it;
  - template replies fill the buyer's name and item, never leave an empty slot, and two turns in a row
    with the same action get different wording;
  - a returning buyer gets a welcome back that names their last design.
- Add `scripts/demo_conversations.py` that plays 5 scripted chats (Hinglish wedding order, Gujarati
  buyer with a unit mix-up, buyer asking about delivery and COD, buyer who rejects two designs, rude
  buyer who then asks a real question) and prints the old reply vs the new reply side by side. I will
  use this output in the pitch.

### Rules while you work

- Small, readable code that matches the repo's style (short functions, plain names, few comments).
- Do not touch the image search, scoring or ingestion code.
- No em dashes anywhere, in code, prompts or replies.
- Run `pytest -q` after each step. Do not commit until all tests pass, then commit each step separately
  with a clear message.
- At the end, give me a short summary: what changed, the before/after for 3 sample chats, and any risks
  for the live demo.
