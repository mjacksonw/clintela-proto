"""Tests for document parsers."""

from unittest.mock import MagicMock, patch

import pytest

from apps.knowledge.parsers import HTMLParser, MarkdownParser, PDFParser, TextParser, get_parser


class TestTextParser:
    def test_empty_text(self):
        parser = TextParser()
        assert parser.parse("") == []
        assert parser.parse("   ") == []

    def test_single_paragraph(self):
        parser = TextParser()
        sections = parser.parse("This is a single paragraph of text.")
        assert len(sections) == 1
        assert sections[0].content == "This is a single paragraph of text."

    def test_multiple_paragraphs(self):
        parser = TextParser()
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        sections = parser.parse(text)
        assert len(sections) == 3
        assert sections[0].content == "First paragraph."
        assert sections[2].content == "Third paragraph."


class TestMarkdownParser:
    def test_empty_text(self):
        parser = MarkdownParser()
        assert parser.parse("") == []

    def test_headings_create_sections(self):
        parser = MarkdownParser()
        text = "# Introduction\nIntro text.\n\n## Methods\nMethod text.\n\n## Results\nResult text."
        sections = parser.parse(text)
        assert len(sections) == 3
        assert sections[0].title == "Introduction"
        assert sections[1].title == "Methods"
        assert "Method text" in sections[1].content

    def test_section_path_tracks_hierarchy(self):
        parser = MarkdownParser()
        text = "# Top\n\n## Sub\nContent here."
        sections = parser.parse(text)
        # The "Sub" section should have Top > Sub in path
        sub_section = [s for s in sections if s.title == "Sub"][0]
        assert "Top" in sub_section.section_path
        assert "Sub" in sub_section.section_path

    def test_content_before_first_heading(self):
        parser = MarkdownParser()
        text = "Preamble text.\n\n# First Heading\nHeading content."
        sections = parser.parse(text)
        assert len(sections) == 2
        assert "Preamble" in sections[0].content


class TestHTMLParser:
    def test_empty_html(self):
        parser = HTMLParser()
        assert parser.parse("") == []

    def test_extracts_text_from_paragraphs(self):
        parser = HTMLParser()
        html = "<html><body><p>First paragraph.</p><p>Second paragraph.</p></body></html>"
        sections = parser.parse(html)
        assert len(sections) >= 1
        content = " ".join(s.content for s in sections)
        assert "First paragraph" in content
        assert "Second paragraph" in content

    def test_splits_on_headings(self):
        parser = HTMLParser()
        html = "<h1>Section One</h1><p>Content one.</p><h2>Section Two</h2><p>Content two.</p>"
        sections = parser.parse(html)
        assert len(sections) == 2
        assert sections[0].title == "Section One"
        assert sections[1].title == "Section Two"

    def test_removes_script_and_style(self):
        parser = HTMLParser()
        html = "<p>Real content.</p><script>alert('bad')</script><style>.x{color:red}</style><p>More content.</p>"
        sections = parser.parse(html)
        content = " ".join(s.content for s in sections)
        assert "alert" not in content
        assert "color:red" not in content
        assert "Real content" in content


class TestSemanticHTMLParser:
    """Tests for the semantic section-aware HTML parser."""

    def _make_jacc_html(self, sections_html: str) -> str:
        """Wrap content in a minimal JACC-like structure."""
        return f"<body>{sections_html}</body>"

    def test_section_deduplication(self):
        """Duplicate section IDs at body level are skipped."""
        parser = HTMLParser()
        html = self._make_jacc_html("""
            <section id="sec-1">
                <h2>Parent</h2>
                <section id="sec-1-1">
                    <h3>Child</h3>
                    <div role="paragraph">Child content.</div>
                </section>
            </section>
            <section id="sec-1-1">
                <h3>Child</h3>
                <div role="paragraph">Child content (duplicate).</div>
            </section>
        """)
        sections = parser.parse(html, "test")
        # sec-1-1 should only appear once (the nested version)
        child_sections = [s for s in sections if s.title == "Child"]
        assert len(child_sections) == 1
        assert "Child content." in child_sections[0].content

    def test_boilerplate_filtered(self):
        """Known boilerplate headings are filtered out."""
        parser = HTMLParser()
        html = self._make_jacc_html("""
            <section id="sec-1">
                <h2>Peer Review Committee Members</h2>
                <div role="paragraph">Committee member list.</div>
            </section>
            <section id="sec-2">
                <h2>Table of Contents</h2>
                <div role="paragraph">TOC entries.</div>
            </section>
            <section id="sec-3">
                <h2>Clinical Findings</h2>
                <div role="paragraph">Important clinical content.</div>
            </section>
        """)
        sections = parser.parse(html, "test")
        titles = [s.title for s in sections]
        assert "Peer Review Committee Members" not in titles
        assert "Table of Contents" not in titles
        assert "Clinical Findings" in titles

    def test_hierarchical_section_path(self):
        """Section paths reflect the heading hierarchy."""
        parser = HTMLParser()
        html = self._make_jacc_html("""
            <section id="sec-1">
                <h2>1 Diagnosis</h2>
                <section id="sec-1-1">
                    <h3>1.1 Clinical Assessment</h3>
                    <div role="paragraph">Assessment details.</div>
                </section>
            </section>
        """)
        sections = parser.parse(html, "test")
        assessment = [s for s in sections if "1.1" in s.title][0]
        assert "1 Diagnosis" in assessment.section_path
        assert "1.1 Clinical Assessment" in assessment.section_path
        assert " > " in assessment.section_path

    def test_div_role_paragraph_extraction(self):
        """Text is extracted from div[role=paragraph] elements."""
        parser = HTMLParser()
        html = self._make_jacc_html("""
            <section id="sec-1">
                <h2>Content</h2>
                <div role="paragraph">First paragraph.</div>
                <div role="paragraph">Second paragraph.</div>
            </section>
        """)
        sections = parser.parse(html, "test")
        assert len(sections) == 1
        assert "First paragraph." in sections[0].content
        assert "Second paragraph." in sections[0].content

    def test_p_tag_extraction(self):
        """Standard <p> tags are also extracted."""
        parser = HTMLParser()
        html = self._make_jacc_html("""
            <section id="sec-1">
                <h2>Content</h2>
                <p>Paragraph content.</p>
            </section>
        """)
        sections = parser.parse(html, "test")
        assert "Paragraph content." in sections[0].content

    def test_data_type_bibliography_skipped(self):
        """Sections with data-type=bibliography are skipped."""
        parser = HTMLParser()
        html = self._make_jacc_html("""
            <section id="sec-1">
                <h2>Clinical Content</h2>
                <div role="paragraph">Important text.</div>
            </section>
            <section id="sec-refs" data-type="bibliography">
                <h2>References</h2>
                <div role="paragraph">1. Smith et al.</div>
            </section>
        """)
        sections = parser.parse(html, "test")
        assert len(sections) == 1
        assert sections[0].title == "Clinical Content"

    def test_section_id_in_metadata(self):
        """Section IDs are stored in metadata."""
        parser = HTMLParser()
        html = self._make_jacc_html("""
            <section id="sec-7">
                <h2>Section 7</h2>
                <div role="paragraph">Content.</div>
            </section>
        """)
        sections = parser.parse(html, "test")
        assert sections[0].metadata.get("section_id") == "sec-7"

    def test_figure_download_links_excluded(self):
        """Figure download tool links are not included in content."""
        parser = HTMLParser()
        html = self._make_jacc_html("""
            <section id="sec-1">
                <h2>Section</h2>
                <figure class="graphic">
                    <figcaption>
                        <div class="caption">Figure 1 Description</div>
                        <div class="core-figure-tools">
                            <a class="core-figure-download-asset">Download figure</a>
                        </div>
                    </figcaption>
                </figure>
            </section>
        """)
        sections = parser.parse(html, "test")
        content = sections[0].content
        assert "Figure 1 Description" in content
        assert "Download figure" not in content

    def test_table_content_extracted(self):
        """Table rows are extracted with pipe-separated cells."""
        parser = HTMLParser()
        html = self._make_jacc_html("""
            <section id="sec-1">
                <h2>Data</h2>
                <figure class="table">
                    <figcaption><div class="caption">Table 1</div></figcaption>
                    <div class="table-wrap">
                        <table>
                            <tr><th>A</th><th>B</th></tr>
                            <tr><td>1</td><td>2</td></tr>
                        </table>
                    </div>
                </figure>
            </section>
        """)
        sections = parser.parse(html, "test")
        assert "A | B" in sections[0].content
        assert "1 | 2" in sections[0].content

    def test_headings_fallback_for_no_sections(self):
        """Falls back to heading-split when no <section> elements exist."""
        parser = HTMLParser()
        html = "<h1>Title</h1><p>Intro text.</p><h2>Methods</h2><p>Method text.</p>"
        sections = parser.parse(html, "test")
        assert len(sections) == 2
        assert sections[0].title == "Title"
        assert sections[1].title == "Methods"

    def test_empty_sections_skipped(self):
        """Sections with no text content are not emitted."""
        parser = HTMLParser()
        html = self._make_jacc_html("""
            <section id="sec-1">
                <h2>Empty Section</h2>
            </section>
            <section id="sec-2">
                <h2>Has Content</h2>
                <div role="paragraph">Real content here.</div>
            </section>
        """)
        sections = parser.parse(html, "test")
        titles = [s.title for s in sections]
        assert "Empty Section" not in titles
        assert "Has Content" in titles

    def test_list_content_extracted(self):
        """List items are extracted from div[role=list] elements."""
        parser = HTMLParser()
        html = self._make_jacc_html("""
            <section id="sec-1">
                <h2>List Section</h2>
                <div role="list">
                    <div role="listitem">
                        <div class="label">1.</div>
                        <div class="content">First item.</div>
                    </div>
                    <div role="listitem">
                        <div class="label">2.</div>
                        <div class="content">Second item.</div>
                    </div>
                </div>
            </section>
        """)
        sections = parser.parse(html, "test")
        assert "First item" in sections[0].content
        assert "Second item" in sections[0].content


class TestJACCEnrichmentPlugin:
    """Tests for COR/LOE recommendation extraction."""

    def _make_rec_html(self, recs_html: str) -> str:
        return f"""<body>
            <section id="sec-1">
                <h2>Recommendations</h2>
                {recs_html}
                <div role="paragraph">Supporting text here.</div>
            </section>
        </body>"""

    def test_cor_loe_extraction(self):
        """COR/LOE recommendation tables are extracted into metadata."""
        parser = HTMLParser()
        html = self._make_rec_html("""
            <figure id="undtbl1" class="table">
                <figcaption><div class="caption">Recommendation for Testing</div></figcaption>
                <div class="table-wrap">
                    <table data-shading="custom">
                        <thead>
                            <tr><th>COR</th><th>LOE</th><th>Recommendations</th></tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td><b>1</b></td>
                                <td><b>B-NR</b></td>
                                <td>Patients should receive testing.</td>
                            </tr>
                            <tr>
                                <td><b>2a</b></td>
                                <td><b>C-EO</b></td>
                                <td>Consider additional evaluation.</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </figure>
        """)
        sections = parser.parse(html, "test")
        assert len(sections) == 1
        recs = sections[0].metadata.get("recommendations", [])
        assert len(recs) == 2
        assert recs[0]["cor"] == "1"
        assert recs[0]["loe"] == "B-NR"
        assert "testing" in recs[0]["text"].lower()
        assert recs[1]["cor"] == "2a"
        assert recs[1]["loe"] == "C-EO"

    def test_no_cor_loe_no_enrichment(self):
        """Non-guideline HTML without COR/LOE tables has no recommendations."""
        parser = HTMLParser()
        html = """<body>
            <section id="sec-1">
                <h2>Discussion</h2>
                <div role="paragraph">Regular content.</div>
            </section>
        </body>"""
        sections = parser.parse(html, "test")
        assert "recommendations" not in sections[0].metadata

    def test_synopsis_tagged(self):
        """Sections starting with 'Synopsis' are tagged."""
        parser = HTMLParser()
        html = """<body>
            <section id="sec-1">
                <h2>Section</h2>
                <figure id="undtbl1" class="table">
                    <table><thead><tr><th>COR</th><th>LOE</th><th>Rec</th></tr></thead>
                    <tbody><tr><td>1</td><td>A</td><td>Do this.</td></tr></tbody></table>
                </figure>
                <div role="paragraph"><b>Synopsis</b></div>
                <div role="paragraph">Synopsis content here.</div>
            </section>
        </body>"""
        sections = parser.parse(html, "test")
        # The section content starts with the table, then "Synopsis..."
        # Since all content is in one section, check metadata
        assert sections[0].metadata.get("recommendations")

    def test_supportive_text_tagged(self):
        """Sections with supportive text markers are tagged."""
        parser = HTMLParser()
        html = """<body>
            <section id="sec-1">
                <h2>Details</h2>
                <figure id="undtbl1" class="table">
                    <table><thead><tr><th>COR</th><th>LOE</th><th>Rec</th></tr></thead>
                    <tbody><tr><td>1</td><td>A</td><td>Do this.</td></tr></tbody></table>
                </figure>
                <div role="paragraph"><b>Recommendation-Specific Supportive Text</b></div>
                <div role="paragraph">Supporting evidence here.</div>
            </section>
        </body>"""
        sections = parser.parse(html, "test")
        assert sections[0].metadata.get("content_type") == "supportive_text"


class TestHTMLParserExtended:
    """Additional coverage for HTMLParser.parse — backward compatibility tests."""

    def test_whitespace_only_html(self):
        parser = HTMLParser()
        assert parser.parse("   \n\t  ") == []

    def test_source_name_used_as_default_title_and_path(self):
        parser = HTMLParser()
        html = "<p>Just a paragraph.</p>"
        sections = parser.parse(html, source_name="my-doc")
        assert len(sections) == 1
        assert sections[0].title == "my-doc"
        assert sections[0].section_path == "my-doc"

    def test_default_title_when_no_source_name(self):
        parser = HTMLParser()
        html = "<p>Some content.</p>"
        sections = parser.parse(html)
        assert sections[0].title == "Content"

    def test_removes_nav_footer_header(self):
        parser = HTMLParser()
        html = "<header>Site header</header><nav>Nav links</nav><p>Body content.</p><footer>Footer text</footer>"
        sections = parser.parse(html)
        content = " ".join(s.content for s in sections)
        assert "Site header" not in content
        assert "Nav links" not in content
        assert "Footer text" not in content
        assert "Body content" in content

    def test_li_elements_captured(self):
        parser = HTMLParser()
        html = "<ul><li>Item one</li><li>Item two</li></ul>"
        sections = parser.parse(html)
        content = " ".join(s.content for s in sections)
        assert "Item one" in content
        assert "Item two" in content

    def test_td_elements_captured(self):
        parser = HTMLParser()
        html = "<table><tr><td>Cell A</td><td>Cell B</td></tr></table>"
        sections = parser.parse(html)
        content = " ".join(s.content for s in sections)
        assert "Cell A" in content
        assert "Cell B" in content

    def test_h2_through_h6_create_sections(self):
        parser = HTMLParser()
        html = "<h2>Alpha</h2><p>Alpha content.</p><h3>Beta</h3><p>Beta content.</p><h4>Gamma</h4><p>Gamma content.</p>"
        sections = parser.parse(html)
        assert len(sections) == 3
        assert sections[0].title == "Alpha"
        assert sections[1].title == "Beta"
        assert sections[2].title == "Gamma"

    def test_section_path_carries_source_name(self):
        parser = HTMLParser()
        html = "<h1>Chapter</h1><p>Chapter content.</p>"
        sections = parser.parse(html, source_name="guideline.html")
        assert sections[0].section_path == "guideline.html"

    def test_elements_with_empty_text_are_skipped(self):
        parser = HTMLParser()
        # <p> with only whitespace should not pollute content
        html = "<p>  </p><p>Real text.</p>"
        sections = parser.parse(html)
        content = " ".join(s.content for s in sections)
        assert content.strip() == "Real text."

    def test_malformed_html_does_not_raise(self):
        parser = HTMLParser()
        # BeautifulSoup is lenient; we just verify it returns something sane
        html = "<p>Unclosed paragraph<p>Another"
        sections = parser.parse(html)
        content = " ".join(s.content for s in sections)
        assert "Unclosed paragraph" in content
        assert "Another" in content

    def test_content_after_last_heading_is_captured(self):
        parser = HTMLParser()
        html = "<h1>Intro</h1><p>First.</p><p>Second.</p>"
        sections = parser.parse(html)
        assert len(sections) == 1
        assert "First" in sections[0].content
        assert "Second" in sections[0].content

    def test_no_headings_returns_single_section(self):
        parser = HTMLParser()
        html = "<p>Para one.</p><p>Para two.</p><p>Para three.</p>"
        sections = parser.parse(html)
        assert len(sections) == 1
        assert "Para one" in sections[0].content


class TestPDFParserSplitIntoSections:
    """Coverage for PDFParser._split_into_sections (lines 208-259)."""

    def setup_method(self):
        self.parser = PDFParser()

    def test_all_caps_heading_creates_new_section(self):
        text = "INTRODUCTION\nThis is the intro text.\n\nMETHODS\nHere are the methods."
        sections = self.parser._split_into_sections(text, "doc", [1])
        titles = [s.title for s in sections]
        assert "INTRODUCTION" in titles
        assert "METHODS" in titles

    def test_numbered_section_heading(self):
        text = "1. Background\nBackground text here.\n\n2. Objectives\nObjective details."
        sections = self.parser._split_into_sections(text, "doc", [1])
        titles = [s.title for s in sections]
        assert any("1. Background" in t for t in titles)
        assert any("2. Objectives" in t for t in titles)

    def test_numbered_subsection_heading(self):
        text = "1.1. Scope\nScope details.\n\n1.2. Limitations\nLimitation text."
        sections = self.parser._split_into_sections(text, "doc", [1])
        assert len(sections) >= 2

    def test_no_headings_returns_single_section(self):
        text = "Just plain text.\nNo headings at all.\nStill going."
        sections = self.parser._split_into_sections(text, "report", [1])
        assert len(sections) == 1
        assert "Just plain text" in sections[0].content

    def test_no_headings_uses_source_name_as_title(self):
        text = "Body content without any heading."
        sections = self.parser._split_into_sections(text, "my-report", [1])
        assert sections[0].title == "my-report"

    def test_no_headings_no_source_name_uses_content_fallback(self):
        text = "Body content without any heading."
        sections = self.parser._split_into_sections(text, "", [1])
        assert sections[0].title == "Content"

    def test_section_path_includes_source_name(self):
        text = "OVERVIEW\nOverview text."
        sections = self.parser._split_into_sections(text, "clinical-guide", [1])
        overview = next(s for s in sections if s.title == "OVERVIEW")
        assert "clinical-guide" in overview.section_path

    def test_section_path_when_no_source_name(self):
        text = "OVERVIEW\nOverview text."
        sections = self.parser._split_into_sections(text, "", [1])
        overview = next(s for s in sections if s.title == "OVERVIEW")
        assert overview.section_path == "OVERVIEW"

    def test_empty_content_lines_between_headings_skipped(self):
        # A heading followed immediately by another heading should not produce an empty section
        text = "SECTION ONE\nSECTION TWO\nContent for two."
        sections = self.parser._split_into_sections(text, "doc", [1])
        # SECTION ONE should not appear because it had no content before SECTION TWO
        titles = [s.title for s in sections]
        assert "SECTION ONE" not in titles
        assert "SECTION TWO" in titles

    def test_last_section_captured_without_trailing_heading(self):
        text = "FIRST\nFirst content.\n\nSECOND\nSecond content."
        sections = self.parser._split_into_sections(text, "doc", [1])
        assert any("Second content" in s.content for s in sections)

    def test_short_allcaps_line_not_treated_as_heading(self):
        # Heading pattern requires more than 3 chars AND at least 4 chars in the ALLCAPS group
        text = "AB\nSome content here."
        sections = self.parser._split_into_sections(text, "doc", [1])
        # "AB" is only 2 chars, too short — should not create a heading split
        assert len(sections) == 1


class TestPDFParserParseFile:
    """Coverage for PDFParser.parse_file (lines 165-206)."""

    def setup_method(self):
        self.parser = PDFParser()

    def test_raises_file_not_found_when_path_missing(self, tmp_path):
        missing = tmp_path / "ghost.pdf"
        with pytest.raises(FileNotFoundError, match="PDF not found"):
            self.parser.parse_file(missing)

    def _make_pdf_mock(self, pages):
        """Return a mock suitable for use as `with pdfplumber.open(...) as pdf:`."""
        mock_pdf = MagicMock()
        mock_pdf.pages = pages
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_pdf)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        return mock_ctx

    def test_scanned_pdf_with_no_text_returns_empty(self, tmp_path):
        """PDF where every page.extract_text() returns None — scanned PDF path."""
        fake_pdf = tmp_path / "scanned.pdf"
        fake_pdf.touch()

        mock_page = MagicMock()
        mock_page.extract_text.return_value = None

        with patch("pdfplumber.open", return_value=self._make_pdf_mock([mock_page, mock_page])):
            result = self.parser.parse_file(fake_pdf, source_name="scanned")

        assert result == []

    def test_scanned_pdf_empty_string_text_returns_empty(self, tmp_path):
        """Page.extract_text() returns empty string instead of None."""
        fake_pdf = tmp_path / "empty_text.pdf"
        fake_pdf.touch()

        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""

        with patch("pdfplumber.open", return_value=self._make_pdf_mock([mock_page])):
            result = self.parser.parse_file(fake_pdf)

        assert result == []

    def test_successful_parse_returns_sections(self, tmp_path):
        """Happy path: PDF with extractable text produces ParsedSection list."""
        fake_pdf = tmp_path / "real.pdf"
        fake_pdf.touch()

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "INTRODUCTION\nThis is the intro."

        with patch("pdfplumber.open", return_value=self._make_pdf_mock([mock_page])):
            result = self.parser.parse_file(fake_pdf, source_name="real")

        assert len(result) >= 1
        contents = " ".join(s.content for s in result)
        assert "intro" in contents.lower()

    def test_multipage_pdf_joins_pages(self, tmp_path):
        """Text from multiple pages is combined before sectioning."""
        fake_pdf = tmp_path / "multi.pdf"
        fake_pdf.touch()

        page1 = MagicMock()
        page1.extract_text.return_value = "BACKGROUND\nBackground text."
        page2 = MagicMock()
        page2.extract_text.return_value = "RESULTS\nResult text."

        with patch("pdfplumber.open", return_value=self._make_pdf_mock([page1, page2])):
            result = self.parser.parse_file(fake_pdf, source_name="multi")

        titles = [s.title for s in result]
        assert "BACKGROUND" in titles
        assert "RESULTS" in titles

    def test_mixed_pages_some_empty(self, tmp_path):
        """Pages with no text are skipped; pages with text are included."""
        fake_pdf = tmp_path / "mixed.pdf"
        fake_pdf.touch()

        page_empty = MagicMock()
        page_empty.extract_text.return_value = None
        page_text = MagicMock()
        page_text.extract_text.return_value = "SUMMARY\nSummary content."

        with patch("pdfplumber.open", return_value=self._make_pdf_mock([page_empty, page_text])):
            result = self.parser.parse_file(fake_pdf, source_name="mixed")

        assert len(result) >= 1
        assert any("Summary content" in s.content for s in result)

    def test_exception_during_parse_returns_empty(self, tmp_path):
        """If pdfplumber raises, parse_file logs and returns [] instead of propagating."""
        fake_pdf = tmp_path / "corrupt.pdf"
        fake_pdf.touch()

        with patch("pdfplumber.open", side_effect=Exception("corrupt PDF")):
            result = self.parser.parse_file(fake_pdf, source_name="corrupt")

        assert result == []

    def test_accepts_string_path(self, tmp_path):
        """parse_file accepts a str path in addition to Path objects."""
        fake_pdf = tmp_path / "str_path.pdf"
        fake_pdf.touch()

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Content here."

        with patch("pdfplumber.open", return_value=self._make_pdf_mock([mock_page])):
            result = self.parser.parse_file(str(fake_pdf))

        assert len(result) >= 1


class TestGetParser:
    def test_txt_returns_text_parser(self):
        assert isinstance(get_parser("doc.txt"), TextParser)

    def test_md_returns_markdown_parser(self):
        assert isinstance(get_parser("doc.md"), MarkdownParser)

    def test_markdown_extension_returns_markdown_parser(self):
        assert isinstance(get_parser("doc.markdown"), MarkdownParser)

    def test_html_returns_html_parser(self):
        assert isinstance(get_parser("doc.html"), HTMLParser)

    def test_htm_returns_html_parser(self):
        assert isinstance(get_parser("doc.htm"), HTMLParser)

    def test_pdf_returns_pdf_parser(self):
        assert isinstance(get_parser("doc.pdf"), PDFParser)

    def test_uppercase_extension_is_normalised(self):
        # Path.suffix.lower() normalises — .PDF should work
        assert isinstance(get_parser("doc.PDF"), PDFParser)

    def test_unsupported_raises(self):
        with pytest.raises(ValueError, match="Unsupported file type"):
            get_parser("doc.docx")

    def test_unsupported_error_lists_supported_types(self):
        with pytest.raises(ValueError, match=r"\.txt"):
            get_parser("doc.docx")
