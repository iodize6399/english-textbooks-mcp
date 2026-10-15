#!/usr/bin/env python3
"""Resumable OCR. Run with `uv run scripts/ingest.py --book <id>`.

The API key is read from MISTRAL_API_KEY or an explicitly supplied private file.
Never log request bodies, headers, credentials, or uploaded document URLs.
"""

from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

import httpx
import pymupdf
from audit_scans import audit_scans

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.mistral.ai/v1"


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def parse_pages(value: str | None, count: int) -> set[int]:
    if not value:
        return set(range(1, count + 1))
    result = set()
    for part in value.split(","):
        ends = [int(x) for x in part.strip().split("-")]
        if len(ends) == 1:
            result.add(ends[0])
        elif len(ends) == 2 and ends[0] <= ends[1]:
            result.update(range(ends[0], ends[1] + 1))
        else:
            raise ValueError(f"Invalid PDF page range: {part}")
    if not result or min(result) < 1 or max(result) > count:
        raise ValueError(f"PDF pages must be between 1 and {count}.")
    return result


def provenance(manifest: dict, source: Path) -> dict:
    with source.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    with pymupdf.open(source) as doc:
        count = len(doc)
    expected = manifest.get("expected_pdf_pages")
    if expected and expected != count:
        raise ValueError(f"Expected {expected} PDF pages, found {count}.")
    return {"source_sha256": digest, "source_pdf_pages": count,
            "layout": manifest.get("layout", "single-page")}


def page_map(meta: dict) -> list[dict]:
    split = meta["layout"] == "two-page"
    return [
        {"id": f"pdf-{page:03d}-{side}", "pdf_page": page,
         "side": side, "reading_order": i + 1}
        for i, (page, side) in enumerate(
            (page, side)
            for page in range(1, meta["source_pdf_pages"] + 1)
            for side in (["left", "right"] if split else ["full"])
        )
    ]


def extract_pdf(source: Path, entries: list[dict]) -> bytes:
    """Create real half-width PDF pages; do not depend on cropbox handling."""
    with pymupdf.open(source) as original, pymupdf.open() as output:
        for entry in entries:
            page = original[entry["pdf_page"] - 1]
            rect = pymupdf.Rect(page.rect)
            if entry["side"] == "left":
                rect.x1 = rect.x0 + rect.width / 2
            elif entry["side"] == "right":
                rect.x0 += rect.width / 2
            target = output.new_page(width=rect.width, height=rect.height)
            target.show_pdf_page(target.rect, original, page.number, clip=rect)
        return output.tobytes(garbage=4, deflate=True)


def process_batch(source: Path, entries: list[dict], directory: Path,
                  meta: dict, settings: dict, key: str, force: bool) -> int:
    pending = []
    for entry in entries:
        path = directory / "ocr" / f"{entry['id']}.json"
        if path.exists() and not force:
            cached = json.loads(path.read_text())
            if cached["provenance"] != meta or cached["settings"] != settings:
                raise ValueError("OCR checkpoint does not match source/settings; use a new book ID or --force.")
        else:
            pending.append(entry)
    if not pending:
        return 0
    pdf = extract_pdf(source, pending)
    payload = {**settings, "document": {"type": "document_url",
               "document_url": "data:application/pdf;base64," + base64.b64encode(pdf).decode()}}
    response = None
    with httpx.Client(timeout=httpx.Timeout(360, connect=30)) as client:
        for attempt in range(6):
            try:
                response = client.post(API + "/ocr", json=payload,
                                       headers={"Authorization": "Bearer " + key})
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == 5:
                    raise RuntimeError("OCR network failure after retries; rerun to resume.") from None
                time.sleep(min(2 ** attempt, 30))
                continue
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < 5:
                    retry = response.headers.get("retry-after", "")
                    time.sleep(min(float(retry) if retry.isdigit() else 2 ** attempt, 60))
                    continue
            if response.status_code >= 400:
                # Deliberately exclude response bodies: they can echo request details.
                raise RuntimeError(f"Mistral OCR HTTP {response.status_code}; check the key, billing and model access.")
            break
        else:
            raise RuntimeError("OCR failed after retries.")
    assert response is not None
    data = response.json()
    pages = data.get("pages", [])
    if len(pages) != len(pending) or [p["index"] for p in pages] != list(range(len(pending))):
        raise RuntimeError("OCR page count/order differs from submitted pages; no checkpoint written.")
    stamp = datetime.now(timezone.utc).isoformat()
    batch_id = f"{pending[0]['id']}--{pending[-1]['id']}"
    write_json(directory / "ocr" / "batches" / f"{batch_id}.json", {
        "provenance": meta, "settings": settings, "created_at": stamp,
        "source_pages": pending, "model": data["model"],
        "usage_info": data.get("usage_info", {}), "request_id": response.headers.get("x-request-id")})
    for entry, page in zip(pending, pages):
        write_json(directory / "ocr" / f"{entry['id']}.json", {
            "source": entry, "provenance": meta, "settings": settings,
            "created_at": stamp, "model": data["model"], "page": page})
    print(f"OCR saved {len(pending)} pages: {pending[0]['id']} … {pending[-1]['id']} (model {data['model']})", flush=True)
    return len(pending)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book", required=True, help="Folder ID under books/")
    parser.add_argument("--pdf", type=Path, help="Override source PDF path")
    parser.add_argument("--key-file", type=Path, help="Private file containing the API key; never committed")
    parser.add_argument("--model", default="mistral-ocr-latest")
    parser.add_argument("--pdf-pages", help="Optional original PDF pages, e.g. 2-4,175")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--force", action="store_true", help="Reprocess selected pages, incurring API usage")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", args.book):
        parser.error("Book ID must be lowercase words separated by hyphens.")
    if not 1 <= args.batch_size <= 64 or not 1 <= args.workers <= 8:
        parser.error("Batch size must be 1–64 and workers 1–8.")
    directory = ROOT / "books" / args.book
    manifest = json.loads((directory / "book.json").read_text())
    source = args.pdf or ROOT / manifest["source_file"]
    key = args.key_file.read_text().strip() if args.key_file else os.environ.get("MISTRAL_API_KEY", "").strip()
    if not key:
        parser.error("Set MISTRAL_API_KEY or supply --key-file. Credentials are only needed for ingestion.")
    meta = provenance(manifest, source)
    selected = parse_pages(args.pdf_pages, meta["source_pdf_pages"])
    entries = [p for p in page_map(meta) if p["pdf_page"] in selected]
    settings = {"model": args.model, "include_blocks": True,
                "confidence_scores_granularity": "block", "include_image_base64": True,
                "extract_header": True, "extract_footer": True}
    source_path = directory / "ocr" / "source.json"
    source_changed = source_path.exists() and json.loads(source_path.read_text()) != meta
    if source_changed and (not args.force or args.pdf_pages):
        raise ValueError("The source PDF changed. Use a new book ID, or reprocess the whole book with --force and review existing corrections.")
    write_json(directory / "ocr" / "source.json", meta)
    audit_path = directory / "ocr" / "scan-audit.json"
    if not audit_path.exists() or source_changed:
        write_json(audit_path, audit_scans(source, meta["layout"]))
    catalog_path = directory / "ocr" / "model-catalog.json"
    if not catalog_path.exists():
        with httpx.Client(timeout=30) as client:
            response = client.get(API + "/models", headers={"Authorization": "Bearer " + key})
        if response.status_code != 200:
            raise RuntimeError(f"Mistral model lookup HTTP {response.status_code}; check key and account access.")
        models = [{"id": model["id"], "aliases": model.get("aliases", [])}
                  for model in response.json()["data"] if model.get("capabilities", {}).get("ocr")]
        write_json(catalog_path, {"checked_at": datetime.now(timezone.utc).isoformat(), "models": models})
    batches = [entries[i:i + args.batch_size] for i in range(0, len(entries), args.batch_size)]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(process_batch, source, batch, directory, meta, settings, key, args.force)
                   for batch in batches]
        completed = sum(f.result() for f in as_completed(futures))
    print(f"Complete: {completed} pages processed; {len(entries) - completed} cached.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"Ingestion stopped: {exc}", file=sys.stderr)
        sys.exit(1)
