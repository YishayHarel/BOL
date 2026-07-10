# BOL Project Plan

Automate the daily Bill of Lading workflow: warehouse emails a scanned batch →
software splits it into individual documents, reads Company / Customer / Date,
renames each file, files them into monthly folders, and forwards specific customers'
BOLs to external partners. **No paid APIs, no LLM** — fully open source.

**Cadence:** ~1 hour/week. Your hour goes to the things only you can do (data,
decisions, running/verifying, Power Automate). Code is written between sessions.

---

## ✅ Already done

- [x] Project scaffolded; repo structure + Docker (nothing installed on your Mac)
- [x] Open-source stack chosen & wired: **Tesseract** (OCR), **Poppler + pdf2image**
      (render), **pypdf** (split/merge, BSD — replaced AGPL PyMuPDF), **TheFuzz** (matching)
- [x] Extraction engine: OCR → parse Date / "Page X of Y" / "more pages" → fuzzy-match
      Company & Customer against a candidate list
- [x] Document grouping by printed **"PAGE 1 OF N"** (not the unreliable handwritten D#)
- [x] **Missing-page detection** — flags gaps (e.g. `1 OF 4` → `3 OF 4`) to *Needs Review*
- [x] Naming `Company - Customer - M-D-YYYY.pdf`, **monthly folders**, **auto-suffix**
      duplicates so no shipment is overwritten (BOL# intentionally excluded)
- [x] `Needs Review/` routing + `manifest.json` audit trail
- [x] Built the Docker image and **tested against the real 22-page sample** — split into
      10 docs, caught the missing page, produced a collision suffix, filed by month

## ⏳ To do

- [ ] Get **Joseph's candidate list** (exact company + top customers)
- [ ] Collect **2–3 more sample batches** for tuning
- [ ] **Tune OCR** — some dates & "Page X of Y" markers are missed; adjust match threshold
- [ ] Decide **two partner emails** + customer→partner mapping (Walmart→?, Marmax→?)
- [ ] Build **Power Automate** flow: watch alias → run tool → forward flagged files
- [ ] Decide **where the script runs** vs. Power Automate (recommend Power Automate Desktop)
- [ ] **Distribution rule engine** (customer → recipient) — code
- [ ] Live end-to-end test through the email alias
- [ ] *(Deferred)* **Egnyte** storage integration — scope after core is proven

---

## Timeline (4 weeks · 1 hr/week)

| Week | Focus | Your hour | I deliver |
|---|---|---|---|
| **1** | Real inputs | Get Joseph's list; gather 2–3 batches; pick partner emails; run it once & skim output | Wire in your config |
| **2** | Accuracy tuning | Re-run, confirm *Needs Review* shrinks to only bad scans | Fix date + page-marker OCR; tune threshold |
| **3** ⚠️ | Email + distribution | Build the Power Automate flow in O365 | Distribution rule engine + a clean command for PA to call |
| **4** | Live test + Egnyte | Send a real batch through the alias; verify end to end | Scope the Egnyte API integration |

**Risk:** Week 3 is the tight one — Power Automate + provisioning the mailbox/host can
exceed an hour. Fallback: keep filing automated, forward manually for a week while the
flow is finished.

## No API keys needed
By design there is **no Claude/LLM key** in this project (that was Evan's separate tool).
The only credentials are your existing Office 365 (Power Automate) and, later, Egnyte.
