"""Tests that Tailwind-preflight-stripped styles are restored for chat markdown.

Tailwind's preflight resets list-style, margins, etc. The `.agent-message-content`
CSS block in base.html must restore them so markdown renders correctly in chat
bubbles for both patients and providers.
"""

import pytest
from django.template.loader import render_to_string


class TestMarkdownChatStyles:
    """Verify .agent-message-content CSS restores styles stripped by Tailwind preflight."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        """Read the base template CSS directly."""
        # Render a minimal template that extends base.html to get the <style> block
        html = render_to_string("base.html", {"request": None})
        self.html = html

    def test_ul_list_style_restored(self):
        """UL inside chat bubbles must have disc bullets."""
        assert ".agent-message-content ul" in self.html
        assert "list-style-type: disc" in self.html

    def test_ol_list_style_restored(self):
        """OL inside chat bubbles must have decimal numbering."""
        assert ".agent-message-content ol" in self.html
        assert "list-style-type: decimal" in self.html

    def test_nested_ul_uses_circle(self):
        """Nested ULs use circle style for visual hierarchy."""
        assert ".agent-message-content li > ul" in self.html
        assert "list-style-type: circle" in self.html

    def test_nested_ol_uses_lower_alpha(self):
        """Nested OLs use lower-alpha for visual hierarchy."""
        assert ".agent-message-content li > ol" in self.html
        assert "list-style-type: lower-alpha" in self.html

    def test_blockquote_styled(self):
        """Blockquotes should have a left border."""
        assert ".agent-message-content blockquote" in self.html
        assert "border-left:" in self.html

    def test_link_styled(self):
        """Links inside chat content should be underlined and use primary color."""
        assert ".agent-message-content a" in self.html
        assert "text-decoration: underline" in self.html

    def test_code_block_styled(self):
        """Code blocks should have background and padding."""
        assert ".agent-message-content code" in self.html

    def test_pre_block_styled(self):
        """Pre blocks should have overflow handling."""
        assert ".agent-message-content pre" in self.html
        assert "overflow-x: auto" in self.html

    def test_headings_styled(self):
        """Headings inside chat content should have weight and margin."""
        assert ".agent-message-content h1" in self.html

    def test_hr_styled(self):
        """Horizontal rules should be visible."""
        assert ".agent-message-content hr" in self.html

    def test_emphasis_styled(self):
        """Italic/em text should be italic."""
        assert ".agent-message-content em" in self.html
        assert "font-style: italic" in self.html
