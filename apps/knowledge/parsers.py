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
    """Parse HTML documents with semantic section awareness.

    Two parsing strategies:
    1. **Section tree walk** (primary) — if the HTML contains ``<section>`` elements,
       walks the tree building hierarchical section paths and deduplicating by ID.
       Handles JACC-style HTML where every subsection appears twice (nested + body-level).
    2. **Heading-split fallback** — for HTML without ``<section>`` elements (e.g. Drupal
       CMS pages), splits on heading tags like the original flat parser.

    Boilerplate filtering removes committee lists, references, preamble methodology,
    and other non-clinical content by heading text and ``data-type`` attributes.

    When COR/LOE recommendation tables are detected (JACC formal guidelines), the
    ``JACCEnrichmentPlugin`` automatically enriches sections with structured
    recommendation metadata.
    """

    # Boilerplate headings to skip (case-insensitive substring match).
    # These appear in ACC/AHA guidelines but are not clinically useful for RAG.
    SKIP_HEADINGS = [
        "peer review committee",
        "task force",
        "writing committee members",
        "table of contents",
        "presidents and staff",
        "president and staff",
        "solution set oversight",
        "methodology members",
        "subcommittee on prevention",
        "rating panel",
        "abbreviations",
        "relationships with industry",
        "document review and approval",
        "composition of the writing committee",
        "organization of the writing committee",
        "selection of writing committee members",
        "evidence review and evidence review committees",
        "class of recommendation and level of evidence",
        "class of recommendations and level of evidence",
        "guideline-directed management and therapy",
        "methodology and evidence review",
        "preamble",
        "intended use",
        "clinical implementation",
        "methodology and modernization",
        "joint committee on clinical practice guidelines",
        "joint committee on performance",
    ]

    # data-type attributes that indicate non-clinical content
    SKIP_DATA_TYPES = {"bibliography", "further-reading"}

    def parse(self, html: str, source_name: str = "") -> list[ParsedSection]:
        from bs4 import BeautifulSoup

        if not html.strip():
            return []

        soup = BeautifulSoup(html, "html.parser")

        # Remove non-content elements. Be selective with <header> and <footer>:
        # only remove them if they don't contain <section> elements (which would
        # indicate they're article content wrappers, not site chrome).
        for tag in soup.find_all(["script", "style", "nav"]):
            tag.decompose()
        for tag in soup.find_all(["footer", "header"]):
            if not tag.find("section"):
                tag.decompose()

        # Find the content root — the highest element that contains sections.
        # JACC extracted articles have sections as direct body children.
        # Full page saves may nest sections inside <main>, <article>, or <div>s.
        content_root = self._find_content_root(soup)

        if content_root is not None:
            sections = self._parse_sections(content_root, source_name)
        else:
            sections = self._parse_headings_fallback(soup, source_name)

        # Run JACC enrichment if COR/LOE tables are detected
        if sections and self._has_cor_loe_tables(soup):
            enrichment = JACCEnrichmentPlugin()
            sections = enrichment.enrich(sections, soup)

        return sections

    def _find_content_root(self, soup):
        """Find the element that directly contains the article's ``<section>`` elements.

        Handles both extracted articles (sections as body children) and full page saves
        (sections nested inside ``<main>``, ``<article>``, ``<div class="core-container">``,
        etc.). Uses a content section (one with an ``id`` attribute) as the starting point
        to avoid latching onto unrelated sections in site chrome (metrics, downloads).

        Returns ``None`` if no ``<section>`` elements exist in the document.
        """
        # Prefer a section with an id — these are real content sections, not site chrome.
        # Fall back to any section if none have IDs.
        anchor = soup.find("section", id=True) or soup.find("section")
        if anchor is None:
            return None

        # Walk up to find the nearest ancestor with multiple direct child sections.
        parent = anchor.parent
        while parent:
            child_sections = parent.find_all("section", recursive=False)
            if len(child_sections) >= 2:
                return parent
            parent = parent.parent

        # Fallback: use the anchor's parent
        return anchor.parent

    def _parse_sections(self, body, source_name: str) -> list[ParsedSection]:
        """Walk ``<section>`` tree, building hierarchical paths and deduplicating."""
        seen_ids: set[str] = set()
        sections: list[ParsedSection] = []
        self._walk_section_tree(body, [], seen_ids, sections, source_name)
        return sections

    def _find_child_sections(self, parent) -> list:
        """Find child ``<section>`` elements, traversing through wrapper divs.

        JACC full-page saves wrap sections in ``<div class="core-container">`` and
        ``<section id="bodymatter">``. This method looks for direct section children
        first, then searches one level deeper through non-section elements.
        """
        direct = parent.find_all("section", recursive=False)
        if direct:
            return direct

        # Look through non-section children (divs) for nested sections
        for child in parent.children:
            if hasattr(child, "name") and child.name and child.name != "section":
                nested = child.find_all("section", recursive=False)
                if nested:
                    return nested

        return []

    def _walk_section_tree(
        self,
        parent,
        heading_stack: list[str],
        seen_ids: set[str],
        results: list[ParsedSection],
        source_name: str,
    ) -> None:
        """Recursively walk section elements, extracting text at each level."""
        for section in self._find_child_sections(parent):
            section_id = section.get("id", "")

            # Deduplicate: JACC HTML duplicates every subsection at body level
            if section_id:
                if section_id in seen_ids:
                    continue
                seen_ids.add(section_id)

            # Skip non-clinical sections by data-type
            if section.get("data-type", "") in self.SKIP_DATA_TYPES:
                continue

            # Get heading for this section
            heading = section.find(["h1", "h2", "h3", "h4", "h5", "h6"], recursive=False)
            heading_text = heading.get_text(strip=True) if heading else ""

            # Skip boilerplate sections
            if self._is_boilerplate(heading_text):
                continue

            # Build section path
            current_stack = [*heading_stack, heading_text] if heading_text else list(heading_stack)

            # Extract direct text content (not from child sections)
            content = self._extract_section_text(section)

            if content.strip():
                section_path = " > ".join(current_stack) if current_stack else source_name
                results.append(
                    ParsedSection(
                        title=heading_text or source_name or "Content",
                        content=content.strip(),
                        section_path=section_path,
                        metadata={"section_id": section_id} if section_id else {},
                    )
                )

            # Recurse into child sections
            self._walk_section_tree(section, current_stack, seen_ids, results, source_name)

    def _extract_section_text(self, section) -> str:
        """Extract text from a section, excluding text that belongs to child sections."""
        texts: list[str] = []
        child_section_ids = {id(child) for child in section.find_all("section", recursive=False)}

        for element in section.children:
            # Skip child sections — they'll be processed recursively
            if hasattr(element, "name") and element.name == "section":
                continue

            # Skip heading (already captured as title)
            if hasattr(element, "name") and element.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                continue

            if hasattr(element, "name"):
                # Extract from paragraph divs, p tags, lists, figures, tables
                self._collect_text(element, texts, child_section_ids)

        return "\n".join(texts)

    def _is_list_element(self, element) -> bool:
        """Check if an element is a list (ul, ol, or div[role=list])."""
        return element.name in ("ul", "ol") or (element.name == "div" and element.get("role") == "list")

    def _collect_text(self, element, texts: list[str], skip_ids: set[int]) -> None:
        """Collect text from an element, handling JACC's div[role=paragraph] and figures."""
        if id(element) in skip_ids:
            return

        # Leaf text elements: div[role=paragraph] or <p>
        if element.name == "p" or (element.name == "div" and element.get("role") == "paragraph"):
            text = element.get_text(strip=True)
            if text:
                texts.append(text)
            return

        if element.name == "figure":
            self._extract_figure_text(element, texts)
            return

        if self._is_list_element(element):
            self._extract_list_text(element, texts)
            return

        # Generic div: recurse into children
        if element.name == "div":
            for child in element.children:
                if hasattr(child, "name"):
                    self._collect_text(child, texts, skip_ids)

    def _extract_list_text(self, element, texts: list[str]) -> None:
        """Extract text from list items (li or div[role=listitem])."""
        for item in element.find_all(
            lambda tag: tag.name == "li" or (tag.name == "div" and tag.get("role") == "listitem"),
            recursive=True,
        ):
            text = item.get_text(strip=True)
            if text:
                texts.append(text)

    def _extract_figure_text(self, figure, texts: list[str]) -> None:
        """Extract caption and table content from a figure element."""
        # Remove download tool links before extracting text
        for tools_div in figure.find_all("div", class_="core-figure-tools"):
            tools_div.decompose()

        # Caption
        caption = figure.find("figcaption")
        if caption:
            cap_text = caption.find("div", class_="caption")
            if cap_text:
                texts.append(cap_text.get_text(strip=True))

        # Table content (for recommendation tables and data tables)
        table = figure.find("table")
        if table:
            for row in table.find_all("tr"):
                cells = [td.get_text(strip=True) for td in row.find_all(["th", "td"])]
                row_text = " | ".join(c for c in cells if c)
                if row_text:
                    texts.append(row_text)

    def _is_boilerplate(self, heading_text: str) -> bool:
        """Check if a heading indicates non-clinical boilerplate content."""
        if not heading_text:
            return False
        lower = heading_text.lower()
        return any(skip in lower for skip in self.SKIP_HEADINGS)

    def _has_cor_loe_tables(self, soup) -> bool:
        """Check if the HTML contains COR/LOE recommendation tables."""
        return any(th.get_text(strip=True) == "COR" for th in soup.find_all("th"))

    def _parse_headings_fallback(self, soup, source_name: str) -> list[ParsedSection]:
        """Fallback parser for HTML without <section> elements.

        Splits on heading tags (h1-h6), collecting text from paragraphs,
        list items, and table cells. Works with any CMS-generated HTML.
        """
        sections = []
        current_title = source_name or "Content"
        current_content: list[str] = []

        for element in soup.find_all(
            ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td"]
            + [lambda tag: tag.name == "div" and tag.get("role") == "paragraph"]
        ):
            if hasattr(element, "name") and element.name and element.name.startswith("h"):
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


class JACCEnrichmentPlugin:
    """Extract structured COR/LOE recommendation data from JACC guideline tables.

    Enriches ``ParsedSection.metadata`` with structured recommendation data when
    COR/LOE tables are detected. Also tags Synopsis and Supportive Text sections.

    This plugin is automatically invoked by ``HTMLParser`` when the HTML contains
    ``<th>COR</th>`` headers, indicating formal ACC/AHA guideline content.
    """

    def enrich(self, sections: list[ParsedSection], soup) -> list[ParsedSection]:
        """Enrich sections with recommendation metadata and content type labels."""
        self._extract_recommendations(sections, soup)
        self._tag_content_types(sections)
        return sections

    def _extract_recommendations(self, sections: list[ParsedSection], soup) -> None:
        """Find COR/LOE tables and attach recommendation data to their parent sections."""
        for figure in soup.find_all("figure", class_="table"):
            recommendations = self._parse_rec_table(figure)
            if not recommendations:
                continue

            # Find the parent section and attach recommendations
            parent_section = figure.find_parent("section")
            if parent_section:
                parent_id = parent_section.get("id", "")
                self._attach_recs_to_section(sections, parent_id, recommendations)

    def _parse_rec_table(self, figure) -> list[dict]:
        """Parse a single COR/LOE recommendation table from a figure element."""
        table = figure.find("table")
        if not table:
            return []

        headers = [th.get_text(strip=True).upper() for th in table.find_all("th")]
        if "COR" not in headers or "LOE" not in headers:
            return []

        cor_idx = headers.index("COR")
        loe_idx = headers.index("LOE")
        rec_idx = max(i for i in range(len(headers)) if i not in (cor_idx, loe_idx))

        tbody = table.find("tbody", recursive=False)
        rows = tbody.find_all("tr") if tbody else []

        recommendations = []
        for row in rows:
            cells = row.find_all("td")
            if len(cells) <= max(cor_idx, loe_idx, rec_idx):
                continue
            rec_text = cells[rec_idx].get_text(strip=True)
            if rec_text:
                recommendations.append(
                    {
                        "cor": cells[cor_idx].get_text(strip=True),
                        "loe": cells[loe_idx].get_text(strip=True),
                        "text": rec_text,
                    }
                )
        return recommendations

    def _attach_recs_to_section(
        self, sections: list[ParsedSection], parent_id: str, recommendations: list[dict]
    ) -> None:
        """Attach recommendations to the section with the given ID."""
        for section in sections:
            if section.metadata.get("section_id") == parent_id:
                if "recommendations" not in section.metadata:
                    section.metadata["recommendations"] = []
                section.metadata["recommendations"].extend(recommendations)
                break

    def _tag_content_types(self, sections: list[ParsedSection]) -> None:
        """Tag sections that contain Synopsis or Supportive Text markers."""
        for section in sections:
            content_lower = section.content.lower()
            if content_lower.startswith("synopsis"):
                section.metadata["content_type"] = "synopsis"
            elif "recommendation-specific supportive text" in content_lower:
                section.metadata["content_type"] = "supportive_text"


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
                        "PDF has no extractable text (scanned?): %s — skipping. See TODO-011 for OCR support.",
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
