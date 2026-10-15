#!/usr/bin/env python3
"""Register another PDF without moving it or making any paid API calls."""
import argparse
import json
from pathlib import Path
import re

import pymupdf

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--author", default="")
    parser.add_argument("--layout", choices=["single-page", "two-page"], default="single-page")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", args.id):
        parser.error("ID must be lowercase words separated by hyphens.")
    source = args.pdf.resolve()
    if not source.is_file():
        parser.error("PDF was not found.")
    try:
        relative = source.relative_to(ROOT)
    except ValueError:
        parser.error("Put the PDF somewhere inside this workspace before registering it.")
    directory = ROOT / "books" / args.id
    if directory.exists():
        parser.error("Book ID already exists; choose a new ID or edit its existing manifest.")
    with pymupdf.open(source) as doc:
        count = len(doc)
    directory.mkdir(parents=True)
    manifest = {"id": args.id, "title": args.title, "author": args.author,
                "language": "en", "source_file": str(relative), "layout": args.layout,
                "expected_pdf_pages": count, "has_answer_key": False,
                "printed_page_ranges": [], "lessons": [], "notes": ""}
    (directory / "book.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(f"Registered {args.title}: {count} PDF pages. Original PDF preserved.")
    print(f"Next: uv run scripts/ingest.py --book {args.id}")
    print(f"Then review books/{args.id}/book.json: add printed_page_ranges and lessons from the contents.")
    print("Finally: npm run check")


if __name__ == "__main__":
    main()
