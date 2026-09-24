# -*- coding: utf-8 -*-
from odoo.tests import BaseCase, tagged

from ..services.formatter import (
    CAPTION_LIMIT, TEXT_LIMIT, html_to_caption, html_to_telegram, telegram_to_html, visible_length,
)


@tagged("post_install", "-at_install", "telegram")
class TestFormatter(BaseCase):

    def test_keeps_supported_tags_and_maps_aliases(self):
        [out] = html_to_telegram("<p>Hi <strong>bold</strong> <em>it</em> <u>u</u> <del>s</del> <code>c</code></p>")
        self.assertEqual(out, "Hi <b>bold</b> <i>it</i> <u>u</u> <s>s</s> <code>c</code>")

    def test_escapes_text_and_strips_unsupported(self):
        [out] = html_to_telegram("<p>1 &lt; 2 &amp; <span style='color:red'>x</span><script>alert(1)</script></p>")
        self.assertEqual(out, "1 &lt; 2 &amp; x")

    def test_links_only_safe_schemes(self):
        [out] = html_to_telegram('<a href="javascript:alert(1)">bad</a> <a href="https://a.io/?x=1&y=2">ok</a>')
        self.assertEqual(out, 'bad <a href="https://a.io/?x=1&amp;y=2">ok</a>')

    def test_blocks_become_line_breaks(self):
        [out] = html_to_telegram("<p>one</p><p>two<br>three</p><ul><li>a</li><li>b</li></ul>")
        self.assertEqual(out, "one\ntwo\nthree\n• a\n• b")

    def test_empty_body(self):
        self.assertEqual(html_to_telegram(""), [])
        self.assertEqual(html_to_telegram("<p><br></p>"), [])

    def test_split_long_text_keeps_tags_balanced(self):
        body = "<p><b>" + ("word " * 2000) + "</b></p>"
        chunks = html_to_telegram(body)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(visible_length(chunk), TEXT_LIMIT)
            self.assertTrue(chunk.startswith("<b>") and chunk.endswith("</b>"), chunk[:20])

    def test_caption_overflow(self):
        caption, overflow = html_to_caption("<p>" + "x" * 1500 + "</p>")
        self.assertLessEqual(visible_length(caption), CAPTION_LIMIT)
        self.assertEqual(visible_length(caption) + sum(visible_length(o) for o in overflow), 1500)

    def test_pre_keeps_whitespace(self):
        [out] = html_to_telegram("<pre>a  b\n  c</pre>")
        self.assertEqual(out, "<pre>a  b\n  c</pre>")

    def test_inbound_entities_utf16_offsets(self):
        html = telegram_to_html("Hi 😀 bold link", [
            {"type": "bold", "offset": 6, "length": 4},
            {"type": "text_link", "offset": 11, "length": 4, "url": "https://e.com"},
        ])
        self.assertIn("<b>bold</b>", html)
        self.assertIn('<a href="https://e.com"', html)

    def test_inbound_escapes_and_line_breaks(self):
        html = telegram_to_html("<script>\nx", [])
        self.assertEqual(str(html), "&lt;script&gt;<br/>x")

    def test_inbound_rejects_unsafe_link(self):
        html = telegram_to_html("click", [{"type": "text_link", "offset": 0, "length": 5, "url": "javascript:x"}])
        self.assertEqual(str(html), "click")
