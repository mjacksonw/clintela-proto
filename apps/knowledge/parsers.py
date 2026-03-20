"""Document parsers for knowledge ingestion.

Supported formats:
- PDF (via pdfplumber) — text-based PDFs with section structure detection
- Plain text
- Markdown — splits on headings
- HTML (via BeautifulSoup) — extracts text with section structure

Scanned PDFs with no extractable text are skipped with a warning (see TODO-011).
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ParsedSection:
    """A section extracted from a document."""

    title: str
    content: str
    page_numbers: list[int] = field(default_factory=list)
    section_path: str = ""
    metadata: dict = field(default_factory=dict)


class TextParser:
    """Parse plain text documents, splitting on blank lines."""

    def parse(self, text: str, source_name: str = "") -> list[ParsedSection]:
        if not text.strip():
            return []

        # Split on double newlines (paragraph boundaries)
        paragraphs = re.split(r"\n{2,}", text.strip())
        sections = []
        for i, para in enumerate(paragraphs):
            para = para.strip()
            if para:
                sections.append(
                    ParsedSection(
                        title=f"Section {i + 1}",
                        content=para,
                        section_path=source_name,
                    )
                )
        return sections


class MarkdownParser:
    """Parse Markdown documents, splitting on headings."""

    def parse(self, text: str, source_name: str = "") -> list[ParsedSection]:
        if not text.strip():
            return []

        sections = []
        current_title = source_name or "Introduction"
        current_content = []
        heading_stack = []

        for line in text.split("\n"):
            heading_match = re.match(r"^(#{1,6})\s+(.+)", line)
            if heading_match:
                # Save previous section
                content = "\n".join(current_content).strip()
                if content:
                    sections.append(
                        ParsedSection(
                            title=current_title,
                            content=content,
                            section_path=" > ".join(heading_stack) if heading_stack else source_name,
                        )
                    )

                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                current_title = title
                current_content = []

                # Maintain heading stack for section_path
                while heading_stack and len(heading_stack) >= level:
                    heading_stack.pop()
                heading_stack.append(title)
            else:
                current_content.append(line)

        # Don't forget the last section
        content = "\n".join(current_content).strip()
        if content:
            sections.append(
                ParsedSection(
                    title=current_title,
                    content=content,
                    section_path=" > ".join(heading_stack) if heading_stack else source_name,
                )
            )

        return sections


class HTMLParser:
    """Parse HTML documents using BeautifulSoup."""

    def parse(self, html: str, source_name: str = "") -> list[ParsedSection]:
        from bs4 import BeautifulSoup

        if not html.strip():
            return []

        soup = BeautifulSoup(html, "html.parser")

        # Remove script, style, nav elements
        for tag in soup.find_all(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        sections = []
        current_title = source_name or "Content"
        current_content = []

        for element in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td"]):
            if element.name and element.name.startswith("h"):
                # Save previous section
                content = "\n".join(current_content).strip()
                if content:
                    sections.append(
                        ParsedSection(
                            title=current_title,
                            content=content,
                            section_path=source_name,
                        )
                    )
                current_title = element.get_text(strip=True)
                current_content = []
            else:
                text = element.get_text(strip=True)
                if text:
                    current_content.append(text)

        # Last section
        content = "\n".join(current_content).strip()
        if content:
            sections.append(
                ParsedSection(
                    title=current_title,
                    content=content,
                    section_path=source_name,
                )
            )

        return sections


class PDFParser:
    """Parse PDF documents using pdfplumber.

    Handles text-based PDFs with section structure detection.
    Scanned PDFs with no extractable text are skipped with a warning.
    """

    def parse_file(self, file_path: str | Path, source_name: str = "") -> list[ParsedSection]:
        """Parse a PDF file into sections.

        Args:
            file_path: Path to the PDF file.
            source_name: Name for logging and section paths.

        Returns:
            List of ParsedSection. Empty list if PDF has no extractable text.
        """
        import pdfplumber

        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"PDF not found: {file_path}")

        try:
            with pdfplumber.open(file_path) as pdf:
                all_text = []
                page_map = []  # Track which page each section came from

                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()
                    if text:
                        all_text.append(text)
                        page_map.append(page_num)

                if not all_text:
                    logger.warning(
                        "PDF has no extractable text (scanned?): %s — skipping. " "See TODO-011 for OCR support.",
                        file_path.name,
                    )
                    return []

                # Join all pages and parse as text with heading detection
                full_text = "\n\n".join(all_text)
                sections = self._split_into_sections(full_text, source_name, page_map)
                return sections

        except Exception:
            logger.exception("Failed to parse PDF: %s", file_path.name)
            return []

    def _split_into_sections(self, text: str, source_name: str, page_map: list[int]) -> list[ParsedSection]:
        """Split PDF text into sections based on heading patterns."""
        # Common heading patterns in clinical documents
        heading_pattern = re.compile(
            r"^([A-Z][A-Z\s]{3,}(?:\d+\.?\d*)?)\s*$"  # ALL CAPS LINES
            r"|^(\d+\.(?:\d+\.)*\s+.+)$",  # Numbered sections: 1. Title, 1.1 Title
            re.MULTILINE,
        )

        sections = []
        current_title = source_name or "Content"
        current_content = []

        for line in text.split("\n"):
            match = heading_pattern.match(line.strip())
            if match and len(line.strip()) > 3:
                content = "\n".join(current_content).strip()
                if content:
                    sections.append(
                        ParsedSection(
                            title=current_title,
                            content=content,
                            section_path=f"{source_name} > {current_title}" if source_name else current_title,
                        )
                    )
                current_title = (match.group(1) or match.group(2)).strip()
                current_content = []
            else:
                current_content.append(line)

        # Last section
        content = "\n".join(current_content).strip()
        if content:
            sections.append(
                ParsedSection(
                    title=current_title,
                    content=content,
                    section_path=f"{source_name} > {current_title}" if source_name else current_title,
                )
            )

        # If no headings were found, return single section
        if not sections:
            sections.append(
                ParsedSection(
                    title=source_name or "Content",
                    content=text.strip(),
                    section_path=source_name,
                )
            )

        return sections


def get_parser(file_path: str | Path) -> TextParser | MarkdownParser | HTMLParser | PDFParser:
    """Get the appropriate parser for a file based on its extension."""
    ext = Path(file_path).suffix.lower()
    parsers = {
        ".txt": TextParser(),
        ".md": MarkdownParser(),
        ".markdown": MarkdownParser(),
        ".html": HTMLParser(),
        ".htm": HTMLParser(),
        ".pdf": PDFParser(),
    }
    parser = parsers.get(ext)
    if parser is None:
        raise ValueError(f"Unsupported file type: {ext}. Supported: {', '.join(parsers.keys())}")
    return parser
