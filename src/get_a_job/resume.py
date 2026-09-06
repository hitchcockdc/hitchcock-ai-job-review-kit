from __future__ import annotations

import re
import subprocess
import zipfile
from html import unescape
from datetime import datetime, timezone
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree
from xml.sax.saxutils import escape

from get_a_job.models import CandidateProfile


def extract_pdf_text(path: Path) -> str:
    result = subprocess.run(
        ["pdftotext", str(path), "-"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    text = result.stdout.strip()
    if not text:
        raise ValueError("no readable text found in the PDF")
    return text


def replace_resume_atomically(pdf_path: Path, text_path: Path, data: bytes) -> str:
    """Extract a new resume before replacing either currently active resume file."""
    pdf_upload = pdf_path.with_name(f"{pdf_path.name}.uploading")
    text_upload = text_path.with_name(f"{text_path.name}.uploading")
    try:
        pdf_upload.write_bytes(data)
        extracted = extract_pdf_text(pdf_upload)
        text_upload.write_text(extracted, encoding="utf-8")
        pdf_upload.replace(pdf_path)
        text_upload.replace(text_path)
        return extracted
    finally:
        # Failed extraction leaves the current PDF and extracted text untouched.
        pdf_upload.unlink(missing_ok=True)
        text_upload.unlink(missing_ok=True)


def extract_docx_text(path: Path) -> str:
    """Extract paragraph text from an OOXML Word document without changing it."""
    try:
        with zipfile.ZipFile(path) as document:
            info = document.getinfo("word/document.xml")
            if info.file_size > 5 * 1024 * 1024:
                raise ValueError("DOCX document text is too large")
            xml = document.read(info).decode("utf-8")
        root = ElementTree.fromstring(xml)
    except (ElementTree.ParseError, KeyError, OSError, UnicodeDecodeError, zipfile.BadZipFile) as error:
        raise ValueError("DOCX file is not a readable Word document") from error
    paragraphs = root.iter(f"{{{_WORD_NAMESPACE}}}p")
    text = "\n".join(
        re.sub(r"\s+", " ", unescape("".join(node.text or "" for node in paragraph.iter(f"{{{_WORD_NAMESPACE}}}t")))).strip()
        for paragraph in paragraphs
    ).strip()
    if not text:
        raise ValueError("no readable text found in the DOCX")
    return text


def replace_docx_atomically(docx_path: Path, text_path: Path, data: bytes) -> str:
    """Extract a DOCX before making it the preferred resume source."""
    docx_upload = docx_path.with_name(f"{docx_path.name}.uploading")
    text_upload = text_path.with_name(f"{text_path.name}.uploading")
    try:
        docx_upload.write_bytes(data)
        extracted = extract_docx_text(docx_upload)
        text_upload.write_text(extracted, encoding="utf-8")
        docx_upload.replace(docx_path)
        text_upload.replace(text_path)
        return extracted
    finally:
        docx_upload.unlink(missing_ok=True)
        text_upload.unlink(missing_ok=True)


def draft_profile(profile: CandidateProfile, text: str) -> dict[str, object]:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    search_text = text.lower()
    known_skills = [
        "AI architecture", "technical program leadership", "generative AI", "LLM", "RAG",
        "agentic AI", "AI evaluation", "data platforms", "API integration", "Python",
        "SQL", "AWS", "Docker", "Kubernetes", "Terraform", "Agile",
    ]
    skills = list(dict.fromkeys([
        *profile.skills,
        *(skill for skill in known_skills if skill.lower() in search_text),
    ]))
    evidence = [
        line for line in lines
        if re.search(r"\b(architect|built|delivered|design|lead|managed|implemented|launched)\b", line, re.I)
    ][:6]
    draft = asdict(profile)
    draft["skills"] = skills
    if lines:
        draft["name"] = lines[0] if len(lines[0]) < 80 else profile.name
    if evidence:
        draft["evidence_inventory"] = [{"source": "updated resume", "evidence": evidence}]
    draft["source"] = "resume PDF reviewed locally"
    draft["source_date"] = date.today().isoformat()
    return draft


def _resume_section(text: str, heading: str, next_headings: Iterable[str]) -> str:
    """Return a normalized, bounded section from pdftotext output."""
    headings = "|".join(re.escape(value) for value in next_headings)
    match = re.search(
        rf"(?:^|\n){re.escape(heading)}\s*\n(.*?)(?=\n(?:{headings})\b|\Z)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""


def tailored_resume_draft(
    text: str,
    *,
    job_title: str,
    company: str,
    matched_skills: list[str],
    matched_required_skills: list[str],
    missing_skills: list[str],
    evidence: list[str],
) -> dict[str, object]:
    """Build a conservative, reviewable tailoring plan from existing resume text.

    This intentionally never writes a missing role skill into proposed resume content.
    It only identifies existing evidence and changes the order of existing summary
    sentences and core expertise for a selected role.
    """
    summary = _resume_section(text, "PROFESSIONAL SUMMARY", ("CORE EXPERTISE", "PROFESSIONAL EXPERIENCE"))
    core_expertise = _resume_section(text, "CORE EXPERTISE", ("PROFESSIONAL EXPERIENCE",))
    core_items = [item.strip() for item in core_expertise.split("|") if item.strip()]
    emphasis = list(dict.fromkeys([*matched_required_skills, *matched_skills]))

    def relevance(item: str) -> tuple[int, str]:
        normalized = item.lower()
        hits = sum(skill.lower() in normalized or normalized in skill.lower() for skill in emphasis)
        return (-hits, normalized)

    reordered_core = sorted(core_items, key=relevance)
    summary_sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", summary) if sentence.strip()]
    tailored_summary = " ".join(sorted(summary_sentences, key=relevance))
    resume_lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    matching_evidence = list(dict.fromkeys([
        line for line in resume_lines if line and any(skill.lower() in line.lower() for skill in emphasis)
    ]))[:6]
    matching_evidence = list(dict.fromkeys([*evidence, *matching_evidence]))[:6]
    in_experience = False
    experience_options: list[str] = []
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if line.upper() == "PROFESSIONAL EXPERIENCE":
            in_experience = True
            continue
        if in_experience and line.startswith(("•", "-", "*")) and any(skill.lower() in line.lower() for skill in emphasis):
            experience_options.append(line.lstrip("•-* ").strip())
    experience_options = list(dict.fromkeys(experience_options))[:6]
    return {
        "target": {"title": job_title, "company": company},
        "current_summary": summary,
        "tailored_summary": tailored_summary,
        "summary_reordered": bool(summary and tailored_summary != summary),
        "reviewer_instruction": (
            "Keep statements factual. Emphasize the verified capabilities below for this role; "
            "do not add the listed gaps unless they are genuinely supported by your experience."
        ),
        "emphasize_existing_skills": emphasis,
        "reordered_core_expertise": reordered_core,
        "supporting_resume_evidence": matching_evidence,
        # These are existing statements only. The reviewer may choose which ones
        # belong in this role's tailoring plan before approving it.
        "experience_bullet_options": experience_options,
        "selected_experience_bullets": [],
        "skills_not_added": missing_skills,
        "source_resume_preserved": True,
    }


def save_tailored_resume_draft(path: Path, draft: dict[str, object]) -> None:
    """Persist an approved tailoring plan privately without replacing the source resume."""
    temporary = path.with_name(f"{path.name}.writing")
    try:
        import json

        temporary.write_text(json.dumps(draft, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


_WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_WORD = f"{{{_WORD_NAMESPACE}}}"


def tailored_docx_filename(company: str, title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", f"{company}-{title}".lower()).strip("-")[:72] or "role"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"tailored-resume-{timestamp}-{slug}.private.docx"


def generate_tailored_docx(source: Path, output: Path, draft: dict[str, object]) -> list[str]:
    """Create a new DOCX with safe, reviewable summary and expertise reordering.

    The source document is never modified. This intentionally supports only a single
    pipe-separated expertise paragraph and a single summary paragraph. The edits keep
    their surrounding paragraphs and runs, so the source document remains intact and
    no unsupported content is introduced. Selected experience bullets are reordered
    only when they map to one contiguous bullet group under Professional Experience.
    """
    reordered = [str(item).strip() for item in draft.get("reordered_core_expertise", []) if str(item).strip()]
    if not reordered:
        raise ValueError("the tailoring plan has no Core Expertise order to apply")
    try:
        with zipfile.ZipFile(source) as archive:
            document_xml = archive.read("word/document.xml")
            package = [(entry, archive.read(entry.filename)) for entry in archive.infolist()]
    except (OSError, KeyError, zipfile.BadZipFile) as error:
        raise ValueError("the selected DOCX could not be read") from error

    xml = document_xml.decode("utf-8")
    paragraphs = re.findall(r"<w:p(?:\s[^>]*)?>.*?</w:p>", xml, flags=re.DOTALL)
    expertise_index = next(
        (index for index, paragraph in enumerate(paragraphs) if _xml_text(paragraph).strip().upper() == "CORE EXPERTISE"),
        None,
    )
    if expertise_index is None:
        raise ValueError("could not find Core Expertise in the selected DOCX")
    expertise_paragraph = next(
        (
            paragraph for paragraph in paragraphs[expertise_index + 1 :]
            if _xml_text(paragraph).strip()
            and "|" in _xml_text(paragraph)
            and not _xml_text(paragraph).strip().upper().startswith("PROFESSIONAL EXPERIENCE")
        ),
        None,
    )
    if expertise_paragraph is None:
        raise ValueError("could not find a single pipe-separated Core Expertise line in the selected DOCX")
    updated_expertise = _replace_docx_paragraph_text(expertise_paragraph, " | ".join(reordered))
    if updated_expertise is None:
        raise ValueError("could not safely update the Core Expertise text in the selected DOCX")
    updated_xml = xml.replace(expertise_paragraph, updated_expertise, 1)

    tailored_summary = str(draft.get("tailored_summary", "")).strip()
    if tailored_summary:
        summary_index = next(
            (index for index, paragraph in enumerate(paragraphs) if _xml_text(paragraph).strip().upper() == "PROFESSIONAL SUMMARY"),
            None,
        )
        if summary_index is not None:
            summary_paragraph = next(
                (
                    paragraph for paragraph in paragraphs[summary_index + 1 :]
                    if _xml_text(paragraph).strip()
                    and _xml_text(paragraph).strip().upper() not in {"CORE EXPERTISE", "PROFESSIONAL EXPERIENCE"}
                ),
                None,
            )
            if summary_paragraph is not None:
                replacement = _replace_docx_paragraph_text(summary_paragraph, tailored_summary)
                if replacement is None:
                    raise ValueError("could not safely update the Professional Summary text in the selected DOCX")
                updated_xml = updated_xml.replace(summary_paragraph, replacement, 1)
    selected_bullets = [str(item).strip() for item in draft.get("selected_experience_bullets", []) if str(item).strip()]
    applied_bullets: list[str] = []
    if selected_bullets:
        updated_xml, applied_bullets = _reorder_selected_experience_bullets(updated_xml, selected_bullets)
    updated_xml = updated_xml.encode("utf-8")

    temporary = output.with_name(f"{output.name}.writing")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for entry, content in package:
                archive.writestr(
                    entry,
                    updated_xml if entry.filename == "word/document.xml" else content,
                )
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return applied_bullets


def _xml_text(fragment: str) -> str:
    return unescape(re.sub(r"<[^>]+>", "", fragment))


def _replace_docx_paragraph_text(paragraph: str, replacement: str) -> str | None:
    """Replace only w:t content, preserving the OOXML paragraph and run structure."""
    text_nodes = list(re.finditer(r"(<w:t(?:\s[^>]*)?>)(.*?)(</w:t>)", paragraph, flags=re.DOTALL))
    if not text_nodes:
        return None
    pieces: list[str] = []
    cursor = 0
    for index, match in enumerate(text_nodes):
        pieces.append(paragraph[cursor : match.start(2)])
        pieces.append(escape(replacement) if index == 0 else "")
        cursor = match.end(2)
    pieces.append(paragraph[cursor:])
    return "".join(pieces)


def _normalized_bullet(value: str) -> str:
    return re.sub(r"\s+", " ", value.lstrip("•-*· ")).strip().casefold()


def _reorder_selected_experience_bullets(xml: str, selected: list[str]) -> tuple[str, list[str]]:
    """Move approved existing bullets only within their original contiguous group."""
    matches = list(re.finditer(r"<w:p(?:\s[^>]*)?>.*?</w:p>", xml, flags=re.DOTALL))
    paragraphs = [match.group() for match in matches]
    experience_index = next(
        (index for index, paragraph in enumerate(paragraphs) if _xml_text(paragraph).strip().upper() == "PROFESSIONAL EXPERIENCE"),
        None,
    )
    if experience_index is None:
        raise ValueError("could not find Professional Experience for the selected evidence")
    selected_order = [_normalized_bullet(item) for item in selected]
    selected_indexes = [
        next(
            (
                index for index in range(experience_index + 1, len(paragraphs))
                if _normalized_bullet(_xml_text(paragraphs[index])) == wanted
            ),
            None,
        )
        for wanted in selected_order
    ]
    if any(index is None for index in selected_indexes):
        raise ValueError("a selected experience statement could not be mapped to the selected DOCX")
    first = min(index for index in selected_indexes if index is not None)
    last = max(index for index in selected_indexes if index is not None)

    def is_bullet(index: int) -> bool:
        return _xml_text(paragraphs[index]).strip().startswith(("•", "-", "*", "·"))

    while first > experience_index + 1 and is_bullet(first - 1):
        first -= 1
    while last + 1 < len(paragraphs) and is_bullet(last + 1):
        last += 1
    if not all(first <= index <= last and is_bullet(index) for index in selected_indexes if index is not None):
        raise ValueError("selected experience statements must belong to one recognized bullet group")
    group = paragraphs[first : last + 1]
    selected_set = set(selected_order)
    by_text = {_normalized_bullet(_xml_text(paragraph)): paragraph for paragraph in group}
    reordered = [by_text[wanted] for wanted in selected_order] + [
        paragraph for paragraph in group if _normalized_bullet(_xml_text(paragraph)) not in selected_set
    ]
    start, end = matches[first].start(), matches[last].end()
    return xml[:start] + "".join(reordered) + xml[end:], selected
