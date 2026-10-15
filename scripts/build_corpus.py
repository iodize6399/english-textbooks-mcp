#!/usr/bin/env python3
"""Build the canonical corpus and compact Worker bundle without API calls/dependencies."""

from __future__ import annotations

import base64
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]


def dump(path: Path, value: object, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=False, indent=None if compact else 2,
                      separators=(",", ":") if compact else None) + "\n"
    if not path.exists() or path.read_text() != data:
        path.write_text(data)


def roman(number: int) -> str:
    result = ""
    for value, letters in [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"),
                           (100, "c"), (90, "xc"), (50, "l"), (40, "xl"),
                           (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]:
        while number >= value:
            result += letters
            number -= value
    return result


def printed_page(book: dict, reading: int) -> str | None:
    for mapping in book["printed_page_ranges"]:
        if mapping["reading_start"] <= reading <= mapping["reading_end"]:
            number = reading - mapping["reading_start"] + mapping["first_page"]
            return roman(number) if mapping.get("style") == "roman" else str(number)
    return None


def normalize(value: str) -> str:
    return re.sub(r"[^\w]+", " ", unicodedata.normalize("NFKD", value).casefold()).strip()


SECTION_PATTERN = r"(?m)^(?:#{1,6}\s*)?[*(\[$]*(\d{1,2}\.\d{1,2})(?![\d.])[^\n]*"


def canonical_text(text: str, corrections: dict) -> tuple[str, list[str]]:
    """Apply only logged source-reviewed changes and mechanical list cleanup."""
    flags = []
    if corrections.get("blank"):
        return "", ["source_reviewed_blank"]
    for change in corrections.get("replacements", []):
        if change["before"] not in text:
            raise ValueError("Reviewed correction no longer matches its raw OCR page.")
        text = text.replace(change["before"], change["after"], 1)
        flags.append("source_reviewed_correction")
    text, count = re.subn(r"(?m)^(\d+)\.\s+\1\s+", r"\1. ", text)
    if count:
        flags.append("duplicate_list_markers_normalized")
    return text, flags


def chapter_offset(text: str, lesson: dict) -> int:
    """Find chapter titles on their TOC page, including shared-page boundaries."""
    if "start_offset" in lesson:
        offset = lesson["start_offset"]
        if not 0 <= offset < len(text):
            raise ValueError(f"Invalid start_offset for lesson {lesson['number']}")
        return offset
    number = lesson["number"]
    target = set(normalize(lesson.get("heading", lesson["title"])).split())
    for match in re.finditer(rf"(?m)^(?:#{{1,6}}\s*)?{number}(?![\d.])\s+(.+)$", text):
        words = set(normalize(match[1]).split())
        if target and len(words & target) / len(target) >= 0.5:
            return match.start()
    # Some OCR headings put the chapter number on its own line.
    for match in re.finditer(rf"(?m)^(?:#{{1,6}}\s*)?{number}\s*\n+([^\n]+)", text):
        words = set(normalize(match[1]).split())
        if target and len(words & target) / len(target) >= 0.5:
            return match.start()
    raise ValueError(f"Cannot locate chapter {number} title on printed page {lesson['start_page']}; review OCR and set start_offset if needed.")


def pieces(text: str, size: int = 3500) -> list[str]:
    """Keep paragraphs/exercise lines intact when possible; never drop text."""
    result = []
    current = ""
    for line in text.splitlines(keepends=True):
        if current and len(current) + len(line) > size:
            result.append(current)
            current = ""
        while len(line) > size:
            if current:
                result.append(current)
                current = ""
            result.append(line[:size])
            line = line[size:]
        current += line
    if current:
        result.append(current)
    return result


def build_book(directory: Path) -> tuple[dict, list[dict], list[dict], list[dict]]:
    book = json.loads((directory / "book.json").read_text())
    if book["id"] != directory.name:
        raise ValueError(f"Book ID must match its folder name: {directory.name}")
    if not book.get("lessons") or not book.get("printed_page_ranges"):
        raise ValueError(f"{book['id']}: review the contents and add lessons and printed_page_ranges to book.json before building.")
    source = json.loads((directory / "ocr" / "source.json").read_text())
    corrections_path = directory / "corrections.json"
    corrections = json.loads(corrections_path.read_text()) if corrections_path.exists() else {}
    audit_path = directory / "ocr" / "scan-audit.json"
    scan_audit = json.loads(audit_path.read_text()) if audit_path.exists() else None
    sparse = {p["id"] for p in scan_audit["pages"] if p["ink_ratio"] < scan_audit["review_threshold"]} if scan_audit else set()
    raw = [json.loads(p.read_text()) for p in sorted((directory / "ocr").glob("pdf-*.json"))]
    raw.sort(key=lambda p: p["source"]["reading_order"])
    expected = source["source_pdf_pages"] * (2 if book.get("layout") == "two-page" else 1)
    if [p["source"]["reading_order"] for p in raw] != list(range(1, expected + 1)):
        raise ValueError(f"{book['id']}: OCR is incomplete; expected {expected} reading pages, found {len(raw)}.")
    pages = []
    for item in raw:
        if item["provenance"] != source:
            raise ValueError(f"{book['id']}: source fingerprint differs across OCR pages.")
        origin, ocr = item["source"], item["page"]
        scores = ocr.get("confidence_scores") or {}
        confidence = scores.get("average_page_confidence_score")
        minimum = scores.get("minimum_page_confidence_score")
        text, flags = canonical_text(ocr.get("markdown", "").strip(), corrections.get(origin["id"], {}))
        if origin["id"] in sparse and text and not corrections.get(origin["id"], {}).get("source_reviewed"):
            raise ValueError(f"Sparse scan {origin['id']} has OCR text: review the source and mark blank or source_reviewed in corrections.json.")
        if confidence is None:
            flags.append("confidence_unavailable")
        elif confidence < 0.95:
            flags.append("low_page_confidence")
        if minimum is not None and minimum < 0.5:
            flags.append("low_confidence_tokens")
        assets = []
        for extracted in ocr.get("images", []):
            image_id = extracted["id"]
            safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", image_id)
            filename = f"{origin['id']}-{safe_name}"
            encoded = extracted.get("image_base64")
            if encoded:
                target = directory / "assets" / filename
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(base64.b64decode(encoded.split(",", 1)[-1]))
                text = text.replace(f"]({image_id})", f"](../assets/{filename})")
                assets.append(str(target.relative_to(ROOT)))
            else:
                flags.append("image_not_extracted")
        if assets:
            flags.append("contains_image")
        # Default ingestion keeps tables inline; handle explicit table extraction too.
        for table in ocr.get("tables", []):
            text = text.replace(f"[{table['id']}]({table['id']})", table["content"])
        footer = ocr.get("footer")
        if footer and not re.fullmatch(r"[\divxlcdm\s]+", footer, flags=re.IGNORECASE) and not corrections.get(origin["id"], {}).get("blank"):
            text += "\n\n[Page footer]\n" + footer
        if not text:
            flags.append("empty_page")
        page = {"book_id": book["id"], **origin,
                "printed_page": printed_page(book, origin["reading_order"]),
                "text": text, "header": ocr.get("header"), "footer": ocr.get("footer"),
                "confidence": confidence, "minimum_confidence": minimum,
                "quality_flags": sorted(set(flags)), "assets": assets,
                "ocr_model": item["model"]}
        pages.append(page)
        label = f"Printed page {page['printed_page']}" if page["printed_page"] else "Unnumbered page"
        readable = (f"# {book['title']} — {label}\n\n"
                    f"Source: PDF page {page['pdf_page']}, {page['side']}; `{page['id']}`\n\n"
                    f"OCR confidence: {confidence}; flags: {', '.join(page['quality_flags']) or 'none'}\n\n"
                    + (f"Header: {page['header']}\n\n" if page["header"] else "")
                    + text + "\n"
                    + (f"\nFooter: {page['footer']}\n" if page["footer"] else ""))
        path = directory / "pages" / f"{page['id']}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(readable)
    numbered = {int(p["printed_page"]): p for p in pages
                if p["printed_page"] and p["printed_page"].isdigit()}
    numbered_count = sum(bool(p["printed_page"] and p["printed_page"].isdigit()) for p in pages)
    if len(numbered) != numbered_count:
        raise ValueError(f"{book['id']}: printed-page mappings contain duplicate page numbers.")
    boundaries = []
    for lesson in book["lessons"]:
        page = numbered[lesson["start_page"]]
        offset = chapter_offset(page["text"], lesson)
        boundaries.append(((page["reading_order"], offset), lesson))
    if [b[0] for b in boundaries] != sorted(set(b[0] for b in boundaries)):
        raise ValueError(f"{book['id']}: chapter boundaries are not unique and ordered.")
    index_page = book.get("index_start_page")
    if index_page is not None:
        boundaries.append(((numbered[index_page]["reading_order"], 0), None))
    chunks = []
    section = None
    active_lesson = None
    for page in pages:
        start_key = (page["reading_order"], 0)
        end_key = (page["reading_order"], len(page["text"]))
        cuts = [(0, next((lesson for key, lesson in reversed(boundaries) if key <= start_key), None))]
        cuts.extend((key[1], lesson) for key, lesson in boundaries if start_key < key < end_key)
        serial = 0
        for i, (start, lesson) in enumerate(cuts):
            end = cuts[i + 1][0] if i + 1 < len(cuts) else len(page["text"])
            segment = page["text"][start:end]
            lesson_number = lesson["number"] if lesson else None
            if lesson_number != active_lesson:
                section = None
                active_lesson = lesson_number
            matches = list(re.finditer(SECTION_PATTERN, segment))
            starts = [0] + [m.start() for m in matches if m.start() > 0]
            for j, block_start in enumerate(starts):
                block_end = starts[j + 1] if j + 1 < len(starts) else len(segment)
                block = segment[block_start:block_end]
                heading = re.match(SECTION_PATTERN, block)
                if heading and lesson_number == int(heading[1].split(".")[0]):
                    section = heading[1]
                for piece in pieces(block):
                    if not piece.strip():
                        continue
                    serial += 1
                    kind = "lesson" if lesson else ("index" if index_page and page["printed_page"] and page["printed_page"].isdigit() and int(page["printed_page"]) >= index_page else "front_matter")
                    chunks.append({"id": f"{book['id']}:{page['id']}:{serial:02}",
                                   "book_id": book["id"], "lesson_number": lesson_number,
                                   "lesson_title": lesson["title"] if lesson else None,
                                   "section_id": section, "kind": kind,
                                   "page_id": page["id"], "pdf_page": page["pdf_page"],
                                   "side": page["side"], "printed_page": page["printed_page"],
                                   "confidence": page["confidence"],
                                   "quality_flags": page["quality_flags"], "text": piece.strip()})
    lessons = []
    for entry in book["lessons"]:
        selected = [c for c in chunks if c["lesson_number"] == entry["number"]]
        if not selected:
            raise ValueError(f"{book['id']}: chapter {entry['number']} has no chunks.")
        metadata = {"book_id": book["id"], **entry,
                    "end_page": int(selected[-1]["printed_page"]),
                    "sections": sorted({c["section_id"] for c in selected if c["section_id"]},
                                       key=lambda s: tuple(map(int, s.split(".")))),
                    "chunk_count": len(selected)}
        lessons.append(metadata)
        path = directory / "lessons" / f"{entry['number']:02}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {entry['number']}. {entry['title']}\n\n" + "\n\n".join(
            f"<!-- {c['id']} | printed p. {c['printed_page']} | PDF p. {c['pdf_page']} {c['side']} -->\n\n{c['text']}"
            for c in selected) + "\n")
    (directory / "chunks.jsonl").write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in chunks))
    dump(directory / "pages.json", pages)
    dump(directory / "lessons.json", lessons)
    public_book = {key: book[key] for key in ["id", "title", "subtitle", "author", "edition", "publisher", "language", "notes", "has_answer_key"] if key in book}
    public_book.update({"source_sha256": source["source_sha256"], "pdf_pages": source["source_pdf_pages"],
                        "reading_pages": len(pages), "lesson_count": len(lessons),
                        "chunk_count": len(chunks), "ocr_models": sorted({p["ocr_model"] for p in pages}),
                        "quality_flag_counts": dict(Counter(f for p in pages for f in p["quality_flags"]))})
    return public_book, lessons, pages, chunks


def main() -> None:
    corpus = {"schema_version": 1, "books": [], "lessons": [], "pages": [], "chunks": []}
    for path in sorted((ROOT / "books").glob("*/book.json")):
        book, lessons, pages, chunks = build_book(path.parent)
        corpus["books"].append(book)
        corpus["lessons"].extend(lessons)
        corpus["pages"].extend(pages)
        corpus["chunks"].extend(chunks)
    if not corpus["books"]:
        raise ValueError("No book manifests found in books/.")
    digest = hashlib.sha256(json.dumps(corpus, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    corpus["corpus_sha256"] = digest
    dump(ROOT / "src" / "generated" / "corpus.json", corpus, compact=True)
    print(f"Built {len(corpus['books'])} books, {len(corpus['lessons'])} lessons, {len(corpus['pages'])} pages, {len(corpus['chunks'])} chunks.")


if __name__ == "__main__":
    main()
