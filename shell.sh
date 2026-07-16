#!/usr/bin/env bash
# Open an interactive shell INSIDE the toolbox so you can run each tool by hand.
# Usage:  ./shell.sh        (put any test PDFs in ./input first)
set -euo pipefail
cd "$(dirname "$0")"

[ -f candidates.json ] || cp candidates.example.json candidates.json
mkdir -p input output

cat <<'INFO'
You're about to drop INTO the container. Once inside, try:

  # 1) Turn a PDF into page images (Poppler):
  pdftoppm -png -r 300 /data/input/batch.pdf /tmp/page

  # 2) OCR one page and print the text (Tesseract):
  tesseract /tmp/page-01.png stdout

  # 3) Try fuzzy matching (TheFuzz) in Python:
  python -c "from thefuzz import fuzz; print(fuzz.partial_ratio('TJ Maxx','SHIP TO T.J.MAXX DC #897'))"

  # 4) Run OUR pipeline one step at a time (Python):
  python
  >>> from bol_splitter.render import render_pages
  >>> from bol_splitter.ocr import ocr_top
  >>> imgs = render_pages("/data/input/batch.pdf")
  >>> print(ocr_top(imgs[0]))     # OCR of page 1's header

  # 5) Run the whole thing:
  python -m bol_splitter.cli /data/input/batch.pdf --out-dir /data/output

  # type 'exit' to leave the box
INFO
echo ""
docker compose run --rm --entrypoint bash bol-splitter
