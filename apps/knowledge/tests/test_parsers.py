"""Tests for document parsers."""

import pytest

from apps.knowledge.parsers import HTMLParser, MarkdownParser, TextParser, get_parser


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
        html = "<h1>Section One</h1><p>Content one.</p>" "<h2>Section Two</h2><p>Content two.</p>"
        sections = parser.parse(html)
        assert len(sections) == 2
        assert sections[0].title == "Section One"
        assert sections[1].title == "Section Two"

    def test_removes_script_and_style(self):
        parser = HTMLParser()
        html = (
            "<p>Real content.</p>" "<script>alert('bad')</script>" "<style>.x{color:red}</style>" "<p>More content.</p>"
        )
        sections = parser.parse(html)
        content = " ".join(s.content for s in sections)
        assert "alert" not in content
        assert "color:red" not in content
        assert "Real content" in content


class TestGetParser:
    def test_txt_returns_text_parser(self):
        assert isinstance(get_parser("doc.txt"), TextParser)

    def test_md_returns_markdown_parser(self):
        assert isinstance(get_parser("doc.md"), MarkdownParser)

    def test_html_returns_html_parser(self):
        assert isinstance(get_parser("doc.html"), HTMLParser)

    def test_unsupported_raises(self):
        with pytest.raises(ValueError, match="Unsupported file type"):
            get_parser("doc.docx")
