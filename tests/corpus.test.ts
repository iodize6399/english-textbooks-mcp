import assert from "node:assert/strict";
import { test } from "node:test";
import { corpus as library, normalize, TextbookCorpus } from "../src/corpus.ts";
import type { CorpusData } from "../src/types.ts";

// Book-specific regression tests stay valid when other books join the library.
const currentId = "living-english-structure";
const corpus = new TextbookCorpus({ ...library.data,
  books: library.data.books.filter((b) => b.id === currentId),
  lessons: library.data.lessons.filter((l) => l.book_id === currentId),
  pages: library.data.pages.filter((p) => p.book_id === currentId),
  chunks: library.data.chunks.filter((c) => c.book_id === currentId),
});

test("the current book has 58 lessons and complete source page coverage", () => {
  assert.equal(corpus.listBooks().books.length, 1);
  assert.equal(corpus.listLessons().lessons.length, 58);
  assert.equal(corpus.data.pages.length, 350);
  assert.equal(corpus.getPage("1").id, "pdf-006-right");
  assert.equal(corpus.getPage("338").id, "pdf-175-left");
});

test("chapters sharing a page never leak their neighbour's text", () => {
  const time = corpus.getLesson(9, undefined, undefined, 0, 30);
  const enough = corpus.getLesson(10, undefined, undefined, 0, 30);
  assert.match(time.chunks.map((c) => c.text).join("\n"), /Say the following times/);
  assert.doesNotMatch(time.chunks.map((c) => c.text).join("\n"), /adverb of excess/i);
  assert.match(enough.chunks.map((c) => c.text).join("\n"), /adverb of excess/i);
  assert.doesNotMatch(enough.chunks.map((c) => c.text).join("\n"), /Say the following times/);
});

test("exercise IDs work with bold OCR headings and continue onto the next page", () => {
  const subsection = corpus.getLesson(14, undefined, "14.3", 0, 30);
  assert(subsection.chunks.every((c) => c.section_id === "14.3"));
  assert(subsection.chunks.some((c) => c.printed_page === "31"));
  assert(subsection.chunks.some((c) => c.printed_page === "32"));
  assert(corpus.listLessons().lessons.find((l) => l.number === 31)?.sections.includes("31.11"));
});

test("pagination retrieves every chunk exactly once and terminates", () => {
  const seen: string[] = [];
  let offset: number | null = 0;
  let expected = 0;
  while (offset !== null) {
    const page = corpus.getLesson(28, undefined, undefined, offset, 3);
    expected = page.total_chunks;
    seen.push(...page.chunks.map((c) => c.id));
    offset = page.next_offset;
    assert(seen.length <= expected);
  }
  assert.equal(seen.length, expected);
  assert.equal(new Set(seen).size, expected);
});

test("search ranks relevant text, respects filters, and returns provenance", () => {
  const result = corpus.search("present perfect", { lesson_number: 23 });
  assert(result.results.length > 0);
  for (const chunk of result.results) {
    assert.equal(chunk.lesson_number, 23);
    assert.equal(chunk.book_id, "living-english-structure");
    assert.match(chunk.source_uri, /^textbook:\/\/living-english-structure\/pages\//);
    assert.match(chunk.citation, /printed p\..*PDF p\./);
  }
  assert.equal(corpus.search("zzxxyyunfindable").results.length, 0);
  assert.throws(() => corpus.search("  !!!  "), /word or phrase/);
  assert.equal(normalize("‘Enough’ — ENOUGH"), "'enough' enough");
});

test("reviewed blank pages cannot return hallucinated text", () => {
  for (const id of ["pdf-001-left", "pdf-002-left", "pdf-006-left", "pdf-170-left", "pdf-175-right"]) {
    const page = corpus.getPage(id);
    assert.equal(page.text, "");
    assert(page.quality_flags.includes("source_reviewed_blank"));
  }
  assert.equal(corpus.search("项目", { include_reference: true }).results.length, 0);
});

test("a second book requires explicit selection and never mixes lesson sources", () => {
  const original = corpus.data;
  const first = original.books[0]!;
  const secondId = "another-book";
  const fixture: CorpusData = {
    ...original,
    books: [first, { ...first, id: secondId, title: "Another Book" }],
    lessons: [...original.lessons, { ...original.lessons[0]!, book_id: secondId }],
    pages: [...original.pages, { ...original.pages[0]!, book_id: secondId }],
    chunks: [...original.chunks, { ...original.chunks.find((c) => c.lesson_number === 1)!,
      id: `${secondId}:one`, book_id: secondId, text: "Uniqueotherbook grammar sample." }],
  };
  const multiple = new TextbookCorpus(fixture);
  assert.throws(() => multiple.listLessons(), /Choose book_id/);
  assert.throws(() => multiple.getLesson(1), /Choose book_id/);
  assert(multiple.getLesson(1, secondId).chunks.every((c) => c.book_id === secondId));
  assert.equal(multiple.search("Uniqueotherbook", { book_id: first.id }).results.length, 0);
  assert.equal(multiple.search("Uniqueotherbook", { book_id: secondId }).results.length, 1);
});

test("invalid book, lesson, section and pagination inputs produce actionable errors", () => {
  assert.throws(() => corpus.getLesson(999), /list_lessons/);
  assert.throws(() => corpus.getLesson(1, "missing"), /list_books/);
  assert.throws(() => corpus.getLesson(1, undefined, "2.1"), /unavailable/);
  assert.throws(() => corpus.getPage("999"), /not found/);
  assert.throws(() => corpus.getLesson(1, undefined, undefined, -1), /offset/);
  assert.throws(() => corpus.search("English", { limit: 100 }), /limit/);
});
