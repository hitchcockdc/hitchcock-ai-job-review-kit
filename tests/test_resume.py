import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from get_a_job.resume import (
    extract_docx_text, generate_tailored_docx, replace_docx_atomically,
    replace_resume_atomically, tailored_resume_draft,
)


class ResumeTests(unittest.TestCase):
    def test_failed_extraction_keeps_existing_resume_and_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf_path = root / "resume.private.pdf"
            text_path = root / "resume.private.txt"
            pdf_path.write_bytes(b"old PDF")
            text_path.write_text("old extracted text", encoding="utf-8")
            with patch("get_a_job.resume.extract_pdf_text", side_effect=ValueError("unreadable PDF")):
                with self.assertRaisesRegex(ValueError, "unreadable PDF"):
                    replace_resume_atomically(pdf_path, text_path, b"new PDF")
            self.assertEqual(pdf_path.read_bytes(), b"old PDF")
            self.assertEqual(text_path.read_text(encoding="utf-8"), "old extracted text")
            self.assertFalse((root / "resume.private.pdf.uploading").exists())
            self.assertFalse((root / "resume.private.txt.uploading").exists())

    def test_successful_extraction_replaces_pdf_and_text_together(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf_path = root / "resume.private.pdf"
            text_path = root / "resume.private.txt"
            with patch("get_a_job.resume.extract_pdf_text", return_value="complete extracted text"):
                result = replace_resume_atomically(pdf_path, text_path, b"new PDF")
            self.assertEqual(result, "complete extracted text")
            self.assertEqual(pdf_path.read_bytes(), b"new PDF")
            self.assertEqual(text_path.read_text(encoding="utf-8"), "complete extracted text")

    def test_tailored_draft_only_reorders_existing_material(self):
        text = """PROFESSIONAL SUMMARY\nExperienced technology leader. Built AI architecture with Python.\nCORE EXPERTISE\nPython | AWS | AI Architecture\nPROFESSIONAL EXPERIENCE\n• Built AI architecture with Python.\n"""
        draft = tailored_resume_draft(
            text,
            job_title="AI Architect",
            company="Acme",
            matched_skills=["Python", "AI Architecture"],
            matched_required_skills=["AI Architecture"],
            missing_skills=["Kubernetes"],
            evidence=["Built AI architecture with Python."],
        )
        self.assertEqual(draft["reordered_core_expertise"][:2], ["AI Architecture", "Python"])
        self.assertEqual(draft["tailored_summary"], "Built AI architecture with Python. Experienced technology leader.")
        self.assertTrue(draft["summary_reordered"])
        self.assertEqual(draft["experience_bullet_options"], ["Built AI architecture with Python."])
        self.assertEqual(draft["selected_experience_bullets"], [])
        self.assertEqual(draft["skills_not_added"], ["Kubernetes"])
        self.assertNotIn("Kubernetes", " ".join(draft["reordered_core_expertise"]))

    def test_failed_docx_extraction_keeps_existing_text_and_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docx_path = root / "resume.private.docx"
            text_path = root / "resume.private.txt"
            docx_path.write_bytes(b"old DOCX")
            text_path.write_text("old extracted text", encoding="utf-8")
            with patch("get_a_job.resume.extract_docx_text", side_effect=ValueError("unreadable DOCX")):
                with self.assertRaisesRegex(ValueError, "unreadable DOCX"):
                    replace_docx_atomically(docx_path, text_path, b"new DOCX")
            self.assertEqual(docx_path.read_bytes(), b"old DOCX")
            self.assertEqual(text_path.read_text(encoding="utf-8"), "old extracted text")

    def test_generated_docx_reorders_summary_and_core_expertise(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "resume.private.docx"
            output = Path(directory) / "tailored.private.docx"
            document_xml = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\" xmlns:mc=\"http://schemas.openxmlformats.org/markup-compatibility/2006\" xmlns:w14=\"http://schemas.microsoft.com/office/word/2010/wordml\" mc:Ignorable=\"w14\"><w:body>
<w:p><w:r><w:t>PROFESSIONAL SUMMARY</w:t></w:r></w:p>
<w:p><w:r><w:t>Experienced technology leader. Built AI architecture with Python.</w:t></w:r></w:p>
<w:p><w:r><w:t>CORE EXPERTISE</w:t></w:r></w:p>
<w:p><w:r><w:t>Python | AWS | AI Architecture</w:t></w:r></w:p>
<w:p><w:r><w:t>PROFESSIONAL EXPERIENCE</w:t></w:r></w:p>
<w:p><w:r><w:t>Acme | Architect</w:t></w:r></w:p>
<w:p><w:r><w:t>• Built platform services.</w:t></w:r></w:p>
<w:p><w:r><w:t>• Built AI architecture with Python.</w:t></w:r></w:p>
<w:p><w:r><w:t>• Led delivery operations.</w:t></w:r></w:p>
</w:body></w:document>"""
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("word/document.xml", document_xml)
            applied = generate_tailored_docx(source, output, {"tailored_summary": "Built AI architecture with Python. Experienced technology leader.", "reordered_core_expertise": ["AI Architecture", "Python", "AWS"], "selected_experience_bullets": ["Built AI architecture with Python."]})
            self.assertEqual(extract_docx_text(output).splitlines()[1], "Built AI architecture with Python. Experienced technology leader.")
            self.assertEqual(extract_docx_text(output).splitlines()[3], "AI Architecture | Python | AWS")
            self.assertEqual(extract_docx_text(source).splitlines()[1], "Experienced technology leader. Built AI architecture with Python.")
            self.assertEqual(extract_docx_text(source).splitlines()[3], "Python | AWS | AI Architecture")
            self.assertEqual(extract_docx_text(output).splitlines()[6:9], ["• Built AI architecture with Python.", "• Built platform services.", "• Led delivery operations."])
            self.assertEqual(applied, ["Built AI architecture with Python."])
            with zipfile.ZipFile(output) as archive:
                output_xml = archive.read("word/document.xml").decode("utf-8")
            self.assertIn('mc:Ignorable="w14"', output_xml)
            self.assertIn('xmlns:w14=', output_xml)

    def test_synthetic_tailoring_fixture_round_trips_through_a_valid_docx_package(self):
        """Exercise the complete tailoring writer with synthetic, non-candidate data."""
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "synthetic-source.docx"
            output = Path(directory) / "synthetic-tailored.docx"
            document_xml = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
<w:p><w:r><w:t>PROFESSIONAL SUMMARY</w:t></w:r></w:p><w:p><w:r><w:t>Platform leader. Built reliable Python services.</w:t></w:r></w:p>
<w:p><w:r><w:t>CORE EXPERTISE</w:t></w:r></w:p><w:p><w:r><w:t>Python | AWS | Reliability</w:t></w:r></w:p>
<w:p><w:r><w:t>PROFESSIONAL EXPERIENCE</w:t></w:r></w:p><w:p><w:r><w:t>• Built reliable Python services.</w:t></w:r></w:p>
</w:body></w:document>"""
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("[Content_Types].xml", """<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>""")
                archive.writestr("_rels/.rels", """<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>""")
                archive.writestr("word/document.xml", document_xml)
            generate_tailored_docx(source, output, {"tailored_summary": "Built reliable Python services. Platform leader.", "reordered_core_expertise": ["Reliability", "Python", "AWS"], "selected_experience_bullets": ["Built reliable Python services."]})
            self.assertTrue(zipfile.is_zipfile(output))
            self.assertIn("Built reliable Python services. Platform leader.", extract_docx_text(output))
            self.assertIn("Reliability | Python | AWS", extract_docx_text(output))


if __name__ == "__main__":
    unittest.main()
