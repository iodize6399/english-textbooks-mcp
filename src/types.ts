export interface Book {
  id: string;
  title: string;
  subtitle?: string;
  author?: string;
  edition?: string;
  publisher?: string;
  language: string;
  notes?: string;
  has_answer_key: boolean;
  source_sha256: string;
  pdf_pages: number;
  reading_pages: number;
  lesson_count: number;
  chunk_count: number;
  ocr_models: string[];
  quality_flag_counts: Record<string, number>;
}

export interface Lesson {
  book_id: string;
  number: number;
  title: string;
  start_page: number;
  end_page: number;
  sections: string[];
  chunk_count: number;
}

export interface Page {
  book_id: string;
  id: string;
  pdf_page: number;
  side: "left" | "right" | "full";
  reading_order: number;
  printed_page: string | null;
  text: string;
  header: string | null;
  footer: string | null;
  confidence: number | null;
  minimum_confidence: number | null;
  quality_flags: string[];
  assets: string[];
  ocr_model: string;
}

export interface Chunk {
  id: string;
  book_id: string;
  lesson_number: number | null;
  lesson_title: string | null;
  section_id: string | null;
  kind: "lesson" | "index" | "front_matter";
  page_id: string;
  pdf_page: number;
  side: "left" | "right" | "full";
  printed_page: string | null;
  confidence: number | null;
  quality_flags: string[];
  text: string;
}

export interface CorpusData {
  schema_version: number;
  corpus_sha256: string;
  books: Book[];
  lessons: Lesson[];
  pages: Page[];
  chunks: Chunk[];
}
