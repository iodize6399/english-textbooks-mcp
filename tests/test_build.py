import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_corpus import canonical_text, chapter_offset, pieces


class IngestionIntegrityTest(unittest.TestCase):
    def test_long_exercise_text_is_never_dropped(self):
        text = "1. A short question.\n\n" + "A" * 7001 + "\n2. Another question.\n"
        chunks = pieces(text)
        self.assertEqual("".join(chunks), text)
        self.assertTrue(all(len(c) <= 3500 for c in chunks))

    def test_shared_page_boundary_points_to_correct_heading(self):
        text = "8.1 continued\n\n## 9 Telling the Time\n\n9.1\n\n## 10 *too* and *enough*\n"
        position = chapter_offset(text, {"number": 10, "title": "too and enough", "start_page": 19})
        self.assertTrue(text[position:].startswith("## 10"))

    def test_reviewed_changes_fail_when_raw_ocr_changes(self):
        with self.assertRaisesRegex(ValueError, "no longer matches"):
            canonical_text("New extraction", {"replacements": [{"before": "Old extraction", "after": "Correction"}]})

    def test_exercise_cleanup_preserves_question_text_and_nondoubled_numbers(self):
        cleaned, flags = canonical_text("1. 1 A dog is an animal.\n2. 2 A cow gives milk.\n3. 14 fish.\n", {})
        self.assertEqual(cleaned, "1. A dog is an animal.\n2. A cow gives milk.\n3. 14 fish.\n")
        self.assertIn("duplicate_list_markers_normalized", flags)


if __name__ == "__main__":
    unittest.main()
