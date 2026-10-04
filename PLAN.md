# Swatch Match: build plan

## Context
Small fabric/saree wholesalers get WhatsApp enquiries as photos, text (often Hindi, Gujarati or Hinglish), or both. Staff search shelves from memory. Swatch Match turns an enquiry into a top-5 shortlist from the shop's own catalogue with stock and rate from stock.csv, plus a draft reply the owner edits and approves. It shortlists, it never decides, and it never sends anything.

Branch `claude/upbeat-tesla-gzht0g`. Decisions taken: Gemini as first LLM provider, deploy to Hugging Face Spaces (Docker, free CPU tier, 16 GB RAM), sample data needed. Skill level: I will write beginner-friendly code (plain functions, short comments, no clever patterns), which also reads fine for intermediate devs.

## Key design choices (simple and reliable)
1. **Agent = deterministic router + real tools, not a free-running LLM loop.** The orchestrator looks at the enquiry type (image only / text only / both / vague) and calls tools in a fixed, explainable order. Every call is logged to the trace. The LLM is used *inside* tools (tagging, parsing, clarifying question). This cannot loop forever, works identically in fallback mode, and the trace panel is always meaningful.
2. **Numbers never come from the LLM.** Stock and rate are read from the `stock` table (loaded only from stock.csv). Reply lines with stock/rate are filled by templates, not generated text.
3. **One-line reasons are computed, not generated.** Compare attribute tags + a cheap Pillow colour check (brightness/hue) to produce "same border and pattern, shade darker". No hallucination risk.
4. **Fallbacks everywhere.**
   - Tagging without LLM: CLIP zero-shot ("a photo of a red saree" vs other values).
   - Text parsing without LLM: keyword lexicon (English + Hinglish + Devanagari + Gujarati words for colours, patterns, garment types, "under 2000").
   - Clarifying question / reply without LLM: templates.
   - Every LLM call wrapped in try/except with a timeout; failure sets `fallback_mode=true` and the UI shows a small notice.
5. **Scoring** in `config.yaml`: `score = w_img*image_sim + w_attr*attr_match + w_text*clip_text_sim` (weights shift by enquiry type). Labels: Very close / Similar / Alternative by thresholds; below lowest = "No match in stock" + nearest alternatives. "Shade may differ in photo" note when colour contributes most of the attribute match.
6. **"This design but in blue"**: image_search for the design, then attribute_filter with the colour override, re-rank.
7. **Embeddings**: `clip-ViT-B-32` via sentence-transformers, image + text in one space, vectors stored as BLOBs in SQLite, loaded into a numpy array at startup (catalogue is small, brute-force cosine is instant).

## File structure
```
swatch-match/
  README.md                 problem, how it works, Mermaid diagram, setup, run, limits, future, AI tools used
  .env.example              GEMINI_API_KEY=
  .gitignore                .env, data/, node_modules, dist, __pycache__
  Dockerfile                builds frontend, serves everything from uvicorn on :7860 (HF Spaces)
  run.sh                    one-command local run: install, ingest if needed, build UI, start server
  requirements.txt
  config.yaml               thresholds, weights, attribute vocabulary, Gemini model name, upload limits
  evaluate.py               top-1 / top-5 hit rate from test_queries.csv
  test_queries.csv          query_image, query_text, expected_design_id
  test_queries/             query photos (must differ from catalogue files; evaluate.py checks)
  catalogue/
    stock.csv               design_id,image_file,name,quantity_available,rate,unit
    *.jpg
    CREDITS.md              licence + source for every sample image
  scripts/
    fetch_sample_catalogue.py   downloads ~30 openly licensed images (Wikimedia Commons), writes stock.csv with made-up stock/rate, CREDITS.md
  backend/
    main.py                 FastAPI routes; serves frontend/dist
    config.py               loads config.yaml + .env
    db.py                   SQLite schema + helpers (designs, tags, embeddings, stock, audit_log)
    images.py               validate type, size limit, EXIF rotate, downscale
    embeddings.py           load CLIP once, encode image/text, cosine search
    llm.py                  THE only file that talks to an LLM: tag_image, parse_text, clarify; GeminiProvider + NullProvider
    tagging.py              LLM tagging with CLIP zero-shot fallback
    ingest.py               python -m backend.ingest: stock.csv -> embeddings -> tags -> SQLite
    agent/
      tools.py              image_search, parse_text_to_attributes, attribute_filter, check_stock, ask_clarifying_question, draft_reply
      orchestrator.py       routes enquiry type -> tool sequence, records trace
      scoring.py            score combination, labels, reasons, shade note
      lexicon.py            multilingual keyword fallback
      templates.py          English / Hindi reply + clarifying question templates
  frontend/
    package.json, vite.config.js, tailwind.config.js, index.html
    src/
      main.jsx, App.jsx (bottom tab nav: Enquiry / Catalogue / Log), api.js
      pages/EnquiryPage.jsx, CataloguePage.jsx (tag editor), AuditLogPage.jsx
      components/ResultCard.jsx, TracePanel.jsx, ReplyBox.jsx, FallbackBanner.jsx
```

## API
- `GET /api/designs`, `PATCH /api/designs/{id}/tags`, `GET /api/images/{file}`
- `POST /api/enquiry` (multipart: optional image, optional text) -> `{enquiry_id, mode, fallback_mode, results[], clarifying_question?, trace[]}`
- `POST /api/reply` (enquiry_id, picked ids, lang) -> draft text
- `POST /api/approve` (enquiry_id, picked ids, final text) -> logs to audit_log
- `GET /api/audit`

## Build order (one feature at a time, stop for your OK, commit after each)
| Step | What | Est. |
|---|---|---|
| 0 | Skeleton: folders, .gitignore, .env.example, config.yaml, requirements, sample-data script, Vite+Tailwind app with 3 empty tabs | 45 min |
| 1 | Ingestion (embeddings + Gemini tags + CLIP fallback) and Catalogue tag-editor screen | 1.5 h (flag: over 1 h) |
| 2 | Enquiry screen: photo + text, validation errors shown nicely | 30 min |
| 3 | Agent tools + orchestrator + fallback mode | 2 h (flag: over 1 h) |
| 4 | Results cards: labels, reasons, stock/rate, no-match + shade note; then evaluate.py | 1.5 h |
| 5 | Vague enquiry -> one clarifying question | 30 min |
| 6 | Draft reply (Hindi/English toggle, editable, "Is it one of these?"), Approve copies + logs | 45 min |
| 7 | Agent trace panel | 30 min |
| 8 | Audit log table | 30 min |
| 9 | README, Dockerfile, HF Spaces deploy | 1 h |

Total about 10 h of build, leaving buffer. **Simpler versions if time runs short:** step 1 can skip Gemini tagging and use CLIP zero-shot only; step 3 can drop Gujarati script from the lexicon (Gemini still handles it when available).

## Honesty notes for evaluate.py
- Refuses (or loudly warns) if a query image is byte-identical to a catalogue image.
- Prints counts, not only percentages, and whether it ran in fallback mode.
- Sample data caveat: with fetched sample images, test queries will be crops/rotations/lighting changes plus team-written text queries. README will label that number as "sample data, augmented queries" and recommend real phone photos for the number reported to judges.

## Verification per step
Each step ends with exact commands to run (e.g. `python -m backend.ingest`, `./run.sh`, open `http://localhost:7860` in Chrome devtools at 380px) and what you should see. Fallback is tested by blanking `GEMINI_API_KEY` and confirming the notice appears and nothing crashes. Bad input tested with a .pdf, a 20 MB image, and an empty submit.

## Environment
Cloud container already has git 2.43, Python 3.11, Node 22, 4 CPUs, 15 GB RAM. Its network policy was blocking huggingface.co and wikimedia, and you are allowing these: huggingface.co, cdn-lfs.huggingface.co, cas-bridge.xethub.hf.co, commons.wikimedia.org, upload.wikimedia.org, generativelanguage.googleapis.com. Step 0 starts by checking these are reachable. If they still fail (the setting may only apply to a new session), I build the parts that don't need them and tell you.

## Status / handoff
- Step 0 done and pushed to `claude/upbeat-tesla-gzht0g` (skeleton, config.yaml, run.sh, sample-data script, React shell with 3 tabs, verified at 380px).
- huggingface.co and wikimedia still blocked in this session. User is allowing the domains and continuing in a **new session** on the same branch, starting at Step 1.
- New session first checks reachability, then runs `python scripts/fetch_sample_catalogue.py --download --count 30`, then builds Step 1.
- Gemini key goes in environment secrets / local `.env` as `GEMINI_API_KEY`, never in chat or git.

## Risks
- Wikimedia download may be blocked by network; fallback is you dropping ~30 photos into /catalogue and running a helper that writes stock.csv.
- First CLIP model download is ~600 MB; Dockerfile pre-downloads it at build time so the Space starts fast.
- Gemini model name lives in config.yaml so it can be changed without code edits.
