"""Focused tests for the knowledge-base document loader."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.rag.loader import FrontMatterError, load_document, load_documents


KNOWLEDGE_BASE = PROJECT_ROOT / "knowledge-base"


def _document_by_filename(filename: str):
    return next(document for document in load_documents(KNOWLEDGE_BASE) if document.filename == filename)


class LoaderTests(unittest.TestCase):
    def test_loads_active_current_policy_metadata(self) -> None:
        document = _document_by_filename("01-returns-policy-current.md")
        self.assertEqual(document.metadata["document_id"], "RET-2026-01")
        self.assertEqual(document.metadata["status"], "active")
        self.assertEqual(document.metadata["effective_date"], "2026-04-01")
        self.assertEqual(document.metadata["last_reviewed"], "2026-07-15")
        self.assertEqual(document.metadata["audience"], "customer")
        self.assertEqual(document.metadata["policy_authority"], "official")
        self.assertEqual(document.metadata["supersedes"], "RET-2024-01")

    def test_loads_superseded_legacy_metadata(self) -> None:
        document = _document_by_filename("02-returns-policy-legacy.md")
        self.assertEqual(document.metadata["status"], "superseded")
        self.assertEqual(document.metadata["superseded_by"], "RET-2026-01")
        self.assertEqual(document.metadata["superseded_date"], "2026-04-01")

    def test_loads_internal_migration_note_metadata(self) -> None:
        document = _document_by_filename("14-internal-content-migration-notes.md")
        self.assertEqual(document.metadata["audience"], "internal")
        self.assertEqual(document.metadata["policy_authority"], "none")
        self.assertIs(document.metadata["customer_answering"], False)
        self.assertIn("SYSTEM INSTRUCTION", document.text)

    def test_preserves_full_text_and_extracts_headings(self) -> None:
        document = _document_by_filename("01-returns-policy-current.md")
        self.assertTrue(document.text.startswith("---\n"))
        self.assertTrue(document.body.startswith("\n# Returns Policy"))
        self.assertEqual(
            [(heading.level, heading.text) for heading in document.headings],
            [
                (1, "Returns Policy"),
                (2, "Standard return window"),
                (2, "Item condition"),
                (2, "Return shipping and refunds"),
                (2, "Exclusions and exceptions"),
            ],
        )
        self.assertEqual(document.headings[0].line_number, 12)

    def test_loads_all_knowledge_base_documents_in_filename_order(self) -> None:
        documents = load_documents(KNOWLEDGE_BASE)
        self.assertEqual(len(documents), len(list(KNOWLEDGE_BASE.glob("*.md"))))
        self.assertEqual(
            [document.filename for document in documents],
            sorted((path.name for path in KNOWLEDGE_BASE.glob("*.md")), key=str.casefold),
        )

    def test_missing_optional_metadata_and_front_matter_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "minimal.md"
            path.write_text("# Minimal document\n\nBody text.\n", encoding="utf-8")
            document = load_document(path)
        self.assertEqual(document.metadata, {})
        self.assertFalse(document.has_front_matter)
        self.assertEqual(document.body, document.text)
        self.assertEqual(document.headings[0].text, "Minimal document")

    def test_malformed_front_matter_raises_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "broken.md"
            path.write_text("---\ndocument_id BAD\n---\n# Broken\n", encoding="utf-8")
            with self.assertRaisesRegex(FrontMatterError, "expected 'key: value'"):
                load_document(path)
