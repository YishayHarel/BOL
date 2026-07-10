import argparse
import sys

from .config import load_candidates
from .pipeline import process_batch


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Split a scanned Bill of Lading batch into individual named PDFs."
    )
    parser.add_argument("pdf_path", help="Path to the scanned batch PDF")
    parser.add_argument("--out-dir", default="output", help="Directory to write results into")
    parser.add_argument("--candidates", default="candidates.json", help="Path to candidate name list JSON")
    parser.add_argument("--dpi", type=int, default=300, help="OCR render DPI")
    args = parser.parse_args()

    candidates = load_candidates(args.candidates)
    results = process_batch(args.pdf_path, args.out_dir, candidates, dpi=args.dpi)

    print(f"\nSplit into {len(results)} document(s):\n")
    for r in results:
        page_range = f"{r.source_pages[0]}-{r.source_pages[-1]}"
        flag = "  [NEEDS REVIEW]" if r.needs_review else ""
        print(f"[pages {page_range}] -> {r.output_path}{flag}")
        for reason in r.reasons:
            print(f"      - {reason}")

    review_count = sum(1 for r in results if r.needs_review)
    print(f"\n{review_count} document(s) need review.")
    sys.exit(1 if review_count else 0)


if __name__ == "__main__":
    main()
