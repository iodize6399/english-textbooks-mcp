#!/usr/bin/env python3
"""Flag nearly empty scan halves for source review; never change OCR automatically."""
import argparse
import json
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]


def audit_scans(source: Path, layout: str) -> dict:
    metrics = []
    threshold = bytes(1 if value < 96 else 0 for value in range(256))
    with pymupdf.open(source) as document:
        for page in document:
            for side in (["left", "right"] if layout == "two-page" else ["full"]):
                rect = pymupdf.Rect(page.rect)
                if side == "left":
                    rect.x1 = rect.x0 + rect.width / 2
                elif side == "right":
                    rect.x0 += rect.width / 2
                # Ignore marginal specks and bleed from neighbouring scans.
                rect = pymupdf.Rect(rect.x0 + rect.width * .05, rect.y0 + rect.height * .04,
                                    rect.x1 - rect.width * .05, rect.y1 - rect.height * .04)
                image = page.get_pixmap(matrix=pymupdf.Matrix(1, 1), clip=rect,
                                        colorspace=pymupdf.csGRAY, alpha=False)
                pixels = image.samples
                ratio = pixels.translate(threshold).count(b"\x01") / len(pixels)
                metrics.append({"id": f"pdf-{page.number + 1:03d}-{side}", "ink_ratio": round(ratio, 6)})
    return {"method": "72 dpi grayscale, central 90% width / 92% height, pixel intensity below 96",
            "review_threshold": 0.005, "pages": metrics}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book", required=True)
    args = parser.parse_args()
    directory = ROOT / "books" / args.book
    book = json.loads((directory / "book.json").read_text())
    result = audit_scans(ROOT / book["source_file"], book["layout"])
    path = directory / "ocr/scan-audit.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n")
    candidates = [page["id"] for page in result["pages"] if page["ink_ratio"] < result["review_threshold"]]
    print("Sparse scan pages to review:", ", ".join(candidates) or "none")


if __name__ == "__main__":
    main()
