from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from render_wechat import DocumentError, build_preview, load_theme, render_document, validate_html


class RenderWechatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.theme = load_theme()
        cls.example = json.loads(
            (SKILL_DIR / "examples" / "policy-interpretation.json").read_text(encoding="utf-8")
        )

    def test_rendered_fragment_is_wechat_safe(self) -> None:
        fragment = render_document(self.example, self.theme)
        self.assertIn("font-size: 16px", fragment)
        self.assertIn("line-height: 1.75", fragment)
        self.assertIn("来源：", fragment)
        self.assertIn("【配图建议】", fragment)
        self.assertNotIn("<style", fragment.lower())
        self.assertNotIn("class=", fragment.lower())
        self.assertEqual(validate_html(fragment, self.theme), [])

    def test_user_text_is_escaped(self) -> None:
        document = dict(self.example)
        document["blocks"] = [{"type": "paragraph", "text": "请勿输入 <script>alert(1)</script>。"}]
        fragment = render_document(document, self.theme)
        self.assertIn("&lt;script&gt;", fragment)
        self.assertEqual(validate_html(fragment, self.theme), [])

    def test_missing_publication_metadata_is_rejected(self) -> None:
        document = dict(self.example)
        del document["editor"]
        with self.assertRaises(DocumentError):
            render_document(document, self.theme)

    def test_preview_keeps_controls_outside_article_fragment(self) -> None:
        fragment = render_document(self.example, self.theme)
        preview = build_preview(fragment, self.example["title"])
        self.assertIn('id="wechat-content">' + fragment + "</div>", preview)
        self.assertIn("复制可粘贴 HTML", preview)


if __name__ == "__main__":
    unittest.main()
