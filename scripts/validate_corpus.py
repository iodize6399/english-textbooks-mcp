#!/usr/bin/env python3
"""Fail on missing OCR pages, lost text, mismatched sources, or broken chapter boundaries."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def validate() -> None:
    corpus = json.loads((ROOT / "src/generated/corpus.json").read_text())
    digest = corpus.pop("corpus_sha256")
    assert digest == hashlib.sha256(json.dumps(corpus, ensure_ascii=False, sort_keys=True).encode()).hexdigest(), "Runtime bundle fingerprint differs"
    book_ids = [b["id"] for b in corpus["books"]]
    assert len(book_ids) == len(set(book_ids)), "Duplicate book IDs"
    ids = [c["id"] for c in corpus["chunks"]]
    assert len(ids) == len(set(ids)), "Duplicate chunk IDs"
    by_page = defaultdict(list)
    for chunk in corpus["chunks"]:
        assert chunk["book_id"] in book_ids
        assert chunk["text"].strip() and len(chunk["text"]) <= 3500
        if chunk["section_id"]:
            assert int(chunk["section_id"].split(".")[0]) == chunk["lesson_number"], chunk["id"]
        by_page[chunk["book_id"], chunk["page_id"]].append(chunk)
    for book in corpus["books"]:
        directory = ROOT / "books" / book["id"]
        manifest = json.loads((directory / "book.json").read_text())
        pages = [p for p in corpus["pages"] if p["book_id"] == book["id"]]
        assert len(pages) == book["reading_pages"]
        assert [p["reading_order"] for p in pages] == list(range(1, len(pages) + 1))
        raw_count = len(list((directory / "ocr").glob("pdf-*.json")))
        assert raw_count == len(pages), "OCR checkpoint coverage differs"
        lessons = [l for l in corpus["lessons"] if l["book_id"] == book["id"]]
        assert len(lessons) == book["lesson_count"] == len(manifest["lessons"])
        for page in pages:
            chunks = by_page[book["id"], page["id"]]
            joined = "".join(c["text"] for c in chunks)
            squash = lambda text: re.sub(r"\s+", "", text)
            assert squash(joined) == squash(page["text"]), f"Text lost or duplicated: {page['id']}"
            assert (directory / "pages" / f"{page['id']}.md").exists()
            assert page["confidence"] is None or 0 <= page["confidence"] <= 1
            for chunk in chunks:
                for field in ["pdf_page", "side", "printed_page", "confidence", "quality_flags"]:
                    assert chunk[field] == page[field], f"Citation mismatch: {chunk['id']} {field}"
            if "source_reviewed_blank" in page["quality_flags"]:
                assert not page["text"] and not chunks
        for lesson in lessons:
            chunks = [c for c in corpus["chunks"] if c["book_id"] == book["id"] and c["lesson_number"] == lesson["number"]]
            assert len(chunks) == lesson["chunk_count"] > 0
            assert int(chunks[0]["printed_page"]) == lesson["start_page"]
            assert (directory / "lessons" / f"{lesson['number']:02}.md").exists()
        print(f"Validated {book['title']}: {len(pages)} source pages, {len(lessons)} lessons, no missing or duplicated text.")


if __name__ == "__main__":
    validate()
