# BOL — Bill of Lading Splitter

Automates the daily BOL workflow: a warehouse scans a stack of Bills of Lading into
one PDF; this tool splits it into individual documents, reads the key fields, renames
each file, and files them into monthly folders — ready for distribution.

No paid APIs and no LLM: extraction is [Tesseract](https://github.com/tesseract-ocr/tesseract)
OCR + rule-based parsing, with [TheFuzz](https://github.com/seatgeek/thefuzz) to map
messy OCR text onto a clean list of known company/customer names.

## What it does

1. **Render** each page (pdf2image + Poppler) and **OCR** the top of the form (Tesseract).
2. **Group** pages into documents using the printed `PAGE 1 OF N` marker (not the
   handwritten `D#`, which repeats and is often missing).
3. **Validate** each document's page sequence — a missing page (e.g. `1 OF 4` jumping
   to `3 OF 4`) is flagged, not silently filed.
4. **Extract** Company (Shipping From), Customer (Ship To), and Date; fuzzy-match the
   company/customer against `candidates.json`.
5. **Name & file** as `Company - Customer - M-D-YYYY.pdf` under a monthly folder
   (`YYYY-MM/`). Duplicate names get ` (2)`, ` (3)` … so no shipment is ever overwritten.
6. Anything low-confidence or incomplete goes to a **`Needs Review/`** folder with reasons.
   A `manifest.json` records every document and decision.

> The B-number (BOL#) is intentionally **not** used — it is handwritten/fuzzy and
> unreliable. See `Needs Review/` + the collision suffix for how uniqueness is kept
> without it.

## Setup

```bash
cp candidates.example.json candidates.json   # then have Joseph fill in the real names
mkdir -p input output
docker compose build
```

## Run

```bash
# put the scanned batch at input/batch.pdf, then:
docker compose run --rm bol-splitter /data/input/batch.pdf --out-dir /data/output
```

Results land in `output/<YYYY-MM>/` (and `output/Needs Review/` for exceptions).

## Configuration — `candidates.json`

```json
{
  "companies": ["FitForLife c/o Rialto Distribution LLC"],
  "customers": ["Walmart", "TJ Maxx", "Ross", "Burlington", "Winners"],
  "fuzzy_threshold": 80
}
```

`fuzzy_threshold` (0–100) is the minimum match confidence; below it, a document is
routed to `Needs Review/` rather than guessed.

## Status / not yet built

- **Email intake** and **external distribution** are handled by Microsoft Power
  Automate (watches the mailbox, invokes this tool, forwards flagged files) — not in
  this repo yet.
- **Egnyte** storage integration is deferred until the core split/OCR is proven.
- Reliable handwritten-`D#` reading is out of scope (would need a vision model).

## Known limitations

- Very short customer names (e.g. "Ross") can fuzzy-match spuriously against unrelated
  page text. Prefer distinctive candidate names; region-cropping the Ship-To block is a
  future refinement.
