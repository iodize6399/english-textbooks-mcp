import data from "./generated/corpus.json" with { type: "json" };
import type { Book, Chunk, CorpusData } from "./types.ts";

const stopWords = new Set("a an and are as at be by for from how i in is it me of on or that the this to was what when with".split(" "));

export function normalize(text: string): string {
  return text.normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase()
    .replace(/[’‘]/g, "'").replace(/[^\p{L}\p{N}']+/gu, " ").trim();
}

function tokens(text: string): string[] {
  return normalize(text).split(/\s+/).filter((word) => word && !stopWords.has(word));
}

function integer(value: number, min: number, max: number, label: string): void {
  if (!Number.isInteger(value) || value < min || value > max) {
    throw new Error(`${label} must be an integer between ${min} and ${max}.`);
  }
}

export class TextbookCorpus {
  readonly data: CorpusData;
  private readonly documents;
  private readonly frequency = new Map<string, number>();
  private readonly averageLength: number;

  constructor(corpus: CorpusData) {
    this.data = corpus;
    this.documents = corpus.chunks.map((chunk) => {
      const words = tokens(chunk.text);
      const counts = new Map<string, number>();
      for (const word of words) counts.set(word, (counts.get(word) ?? 0) + 1);
      for (const word of counts.keys()) this.frequency.set(word, (this.frequency.get(word) ?? 0) + 1);
      return { chunk, counts, length: words.length, title: normalize(chunk.lesson_title ?? ""), normalized: normalize(chunk.text) };
    });
    this.averageLength = this.documents.reduce((sum, doc) => sum + doc.length, 0) / (this.documents.length || 1);
  }

  listBooks() {
    return { books: this.data.books, corpus_sha256: this.data.corpus_sha256 };
  }

  book(bookId?: string): Book {
    if (!bookId && this.data.books.length === 1) return this.data.books[0]!;
    if (!bookId) throw new Error("Choose book_id using list_books; more than one textbook is available.");
    const found = this.data.books.find((b) => b.id === bookId);
    if (!found) throw new Error(`Unknown book_id '${bookId}'. Call list_books for available IDs.`);
    return found;
  }

  listLessons(bookId?: string) {
    const book = this.book(bookId);
    return { book, lessons: this.data.lessons.filter((lesson) => lesson.book_id === book.id) };
  }

  cite(chunk: Chunk) {
    const book = this.book(chunk.book_id);
    return { ...chunk, citation: `${book.title}${chunk.lesson_number ? `, section ${chunk.lesson_number}${chunk.section_id ? ` (${chunk.section_id})` : ""}` : ""}, ${chunk.printed_page ? `printed p. ${chunk.printed_page}, ` : ""}PDF p. ${chunk.pdf_page} (${chunk.side})`,
      source_uri: `textbook://${book.id}/pages/${chunk.page_id}` };
  }

  getLesson(lessonNumber: number, bookId?: string, sectionId?: string, offset = 0, limit = 12) {
    integer(offset, 0, Number.MAX_SAFE_INTEGER, "offset");
    integer(limit, 1, 30, "limit");
    const book = this.book(bookId);
    const lesson = this.data.lessons.find((entry) => entry.book_id === book.id && entry.number === lessonNumber);
    if (!lesson) throw new Error(`Lesson ${lessonNumber} was not found in '${book.id}'. Call list_lessons.`);
    if (sectionId && !lesson.sections.includes(sectionId)) {
      throw new Error(`Section '${sectionId}' is unavailable in lesson ${lessonNumber}. Available: ${lesson.sections.join(", ") || "none"}.`);
    }
    const chunks = this.data.chunks.filter((chunk) => chunk.book_id === book.id && chunk.lesson_number === lessonNumber && (!sectionId || chunk.section_id === sectionId));
    return { book, lesson, section_id: sectionId ?? null,
      chunks: chunks.slice(offset, offset + limit).map((chunk) => this.cite(chunk)),
      total_chunks: chunks.length, offset,
      next_offset: offset + limit < chunks.length ? offset + limit : null };
  }

  getPage(page: string, bookId?: string) {
    const book = this.book(bookId);
    const found = this.data.pages.find((p) => p.book_id === book.id && (p.id === page || p.printed_page === page.toLowerCase()));
    if (!found) throw new Error(`Page '${page}' was not found in '${book.id}'. Use a printed page number or source page ID from search results.`);
    return { ...found,
      citation: `${book.title}, ${found.printed_page ? `printed p. ${found.printed_page}, ` : ""}PDF p. ${found.pdf_page} (${found.side})`,
      source_uri: `textbook://${book.id}/pages/${found.id}`,
      image_note: found.assets.length ? "This page includes images stored in the local corpus. The MCP returns OCR text; consult the original PDF for the visual layout." : null };
  }

  search(query: string, options: { book_id?: string; lesson_number?: number; limit?: number; offset?: number; include_reference?: boolean } = {}) {
    const cleaned = normalize(query);
    if (!cleaned) throw new Error("Enter a word or phrase to search for.");
    const words = [...new Set(tokens(query))];
    if (!words.length) words.push(...cleaned.split(/\s+/));
    const limit = options.limit ?? 5;
    const offset = options.offset ?? 0;
    integer(limit, 1, 20, "limit");
    integer(offset, 0, Number.MAX_SAFE_INTEGER, "offset");
    const book = options.book_id ? this.book(options.book_id) : undefined;
    if (options.lesson_number !== undefined) {
      if (book) this.getLesson(options.lesson_number, book.id);
      else if (!this.data.lessons.some((l) => l.number === options.lesson_number)) throw new Error("Lesson number was not found. Call list_lessons.");
    }
    const ranked = this.documents.flatMap((doc, position) => {
      const chunk = doc.chunk;
      if (book && chunk.book_id !== book.id) return [];
      if (options.lesson_number !== undefined && chunk.lesson_number !== options.lesson_number) return [];
      if (!options.include_reference && chunk.kind !== "lesson") return [];
      let score = 0;
      let matched = 0;
      for (const word of words) {
        const count = doc.counts.get(word) ?? 0;
        const inTitle = doc.title.split(" ").includes(word);
        if (!count && !inTitle) continue;
        matched++;
        const frequency = this.frequency.get(word) ?? 0;
        const idf = Math.log(1 + (this.documents.length - frequency + 0.5) / (frequency + 0.5));
        const denominator = count + 1.2 * (0.25 + 0.75 * doc.length / (this.averageLength || 1));
        score += idf * (count * 2.2 / denominator + (inTitle ? 2 : 0));
      }
      if (!matched) return [];
      score *= matched / words.length;
      if (doc.normalized.includes(cleaned)) score += 5;
      if (doc.title.includes(cleaned)) score += 8;
      if (chunk.section_id && query.trim() === chunk.section_id) score += 20;
      return [{ score, position, chunk }];
    }).sort((a, b) => b.score - a.score || a.position - b.position);
    return { query, total_results: ranked.length, offset,
      next_offset: offset + limit < ranked.length ? offset + limit : null,
      results: ranked.slice(offset, offset + limit).map(({ score, chunk }) => ({ ...this.cite(chunk), score: Math.round(score * 1000) / 1000 })) };
  }
}

export const corpus = new TextbookCorpus(data as CorpusData);
