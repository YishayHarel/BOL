#!/usr/bin/env bash
# Process one scanned BOL batch. Usage:  ./run.sh /path/to/scan.pdf
set -euo pipefail
cd "$(dirname "$0")"

if [ $# -lt 1 ]; then
  echo "Usage: ./run.sh /path/to/scan.pdf"
  exit 1
fi

# First run: make sure the config + folders exist.
if [ ! -f candidates.json ]; then
  cp candidates.example.json candidates.json
  echo "Created candidates.json from the example — edit it with your real customer names."
fi
mkdir -p input output

# Put the chosen PDF where the container expects it, then run the pipeline.
cp "$1" input/batch.pdf
docker compose run --rm bol-splitter /data/input/batch.pdf --out-dir /data/output

echo ""
echo "Done. Opening the results folder..."
open output 2>/dev/null || true
