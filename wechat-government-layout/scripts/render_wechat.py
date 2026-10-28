#!/usr/bin/env python3
"""Render approved structured government copy as a WeChat-safe HTML fragment."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping, Sequence


SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_THEME_PATH = SKILL_DIR / "config" / "default_theme.json"
REQUIRED_STYLE_NAMES = {
    "root",
    "title",
    "summary",
    "heading",
    "paragraph",
    "highlight",
    "inline_highlight",
    "quote",
    "quote_source",
    "data_table",
    "data_label",
    "data_value",
    "data_note",
    "image",
    "image_placeholder",
    "image_caption",
    "footer",
    "footer_label",
    "footer_separator",
}


class DocumentError(ValueError):
    """Raised when the source document is not publishable structured input."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise DocumentError(f"无法读取文件：{path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise DocumentError(f"JSON 格式错误：{path}:{exc.lineno}:{exc.colno}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise DocumentError(f"顶层 JSON 必须是对象：{path}")
    return data


def load_theme(path: Path = DEFAULT_THEME_PATH) -> dict[str, Any]:
    theme = load_json(path)
    styles = theme.get("styles")
    validation = theme.get("validation")
    if not isinstance(styles, dict) or not isinstance(validation, dict):
        raise DocumentError("主题必须包含 styles 和 validation 对象。")
    missing = sorted(REQUIRED_STYLE_NAMES.difference(styles))
    if missing:
        raise DocumentError(f"主题缺少样式参数：{', '.join(missing)}")
    if not all(isinstance(styles[name], str) and styles[name].strip() for name in REQUIRED_STYLE_NAMES):
        raise DocumentError("主题样式必须为非空字符串。")
    return theme


def required_text(document: Mapping[str, Any], field: str) -> str:
    value = document.get(field)
    if not isinstance(value, str) or not value.strip():
        raise DocumentError(f"缺少必填字段或字段为空：{field}")
    return value.strip()


def optional_text(document: Mapping[str, Any], field: str) -> str | None:
    value = document.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise DocumentError(f"字段必须是字符串：{field}")
    value = value.strip()
    return value or None


def validate_date(value: str) -> None:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise DocumentError("date 必须采用 YYYY-MM-DD 格式。")


def validate_release_input(document: Mapping[str, Any]) -> None:
    """Apply the design document's parse, traceability and release gates."""
    title = required_text(document, "title")
    if "!" in title or "！" in title:
        raise DocumentError("标题不得使用感叹号式营销表达。")
    for field in ("purpose", "target_length"):
        value = document.get(field)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise DocumentError(f"{field} 必须是非空字符串。")

    blocks = document.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise DocumentError("blocks 必须是非空数组。")
    if not any(isinstance(block, Mapping) and block.get("type") == "paragraph" for block in blocks):
        raise DocumentError("正文至少需要一个 paragraph 块。")

    source_paragraphs = document.get("source_paragraphs")
    if source_paragraphs is None:
        return
    if not isinstance(source_paragraphs, list) or not source_paragraphs:
        raise DocumentError("source_paragraphs 必须是非空数组。")
    source_ids: set[str] = set()
    for index, item in enumerate(source_paragraphs, start=1):
        if not isinstance(item, Mapping):
            raise DocumentError(f"source_paragraphs[{index}] 必须是对象。")
        source_id = item.get("id")
        source_text = item.get("text")
        if not isinstance(source_id, str) or not source_id.strip() or not isinstance(source_text, str) or not source_text.strip():
            raise DocumentError(f"source_paragraphs[{index}] 必须包含非空 id 和 text。")
        if source_id in source_ids:
            raise DocumentError(f"source_paragraphs 出现重复 id：{source_id}")
        source_ids.add(source_id)

    summary = document.get("summary")
    summary_ref = document.get("summary_source_ref")
    if summary and (not isinstance(summary_ref, str) or summary_ref not in source_ids):
        raise DocumentError("提供 summary 时，summary_source_ref 必须指向原文段落。")
    for index, block in enumerate(blocks, start=1):
        if not isinstance(block, Mapping):
            raise DocumentError(f"blocks[{index}] 必须是对象。")
        refs = block.get("source_ref")
        if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) and ref in source_ids for ref in refs):
            raise DocumentError(f"blocks[{index}] 必须用 source_ref 回指 source_paragraphs。")


def escaped_text_with_emphasis(text: str, phrases: Any, emphasis_style: str) -> str:
    if phrases is None:
        return html.escape(text)
    if not isinstance(phrases, list) or not all(isinstance(item, str) for item in phrases):
        raise DocumentError("paragraph.emphasis 必须是字符串数组。")
    unique_phrases = sorted({item for item in phrases if item}, key=len, reverse=True)
    if not unique_phrases:
        return html.escape(text)
    expression = re.compile("|".join(re.escape(item) for item in unique_phrases))
    output: list[str] = []
    last_end = 0
    for match in expression.finditer(text):
        output.append(html.escape(text[last_end:match.start()]))
        output.append(
            '<span style="' + html.escape(emphasis_style, quote=True) + '">'
            + html.escape(match.group(0))
            + "</span>"
        )
        last_end = match.end()
    output.append(html.escape(text[last_end:]))
    return "".join(output)


def block_text(block: Mapping[str, Any], field: str = "text") -> str:
    value = block.get(field)
    if not isinstance(value, str) or not value.strip():
        raise DocumentError(f"{block.get('type', '未知')} 块缺少非空 {field}。")
    return value.strip()


def render_block(block: Mapping[str, Any], styles: Mapping[str, str]) -> str:
    block_type = block.get("type")
    if not isinstance(block_type, str):
        raise DocumentError("每个 block 都必须包含字符串 type。")

    if block_type == "paragraph":
        text = block_text(block)
        content = escaped_text_with_emphasis(text, block.get("emphasis"), styles["inline_highlight"])
        return '<p style="' + styles["paragraph"] + '">' + content + "</p>"

    if block_type == "heading":
        return (
            '<p style="' + styles["heading"] + '"><strong>'
            + html.escape(block_text(block))
            + "</strong></p>"
        )

    if block_type == "highlight":
        return '<p style="' + styles["highlight"] + '">' + html.escape(block_text(block)) + "</p>"

    if block_type == "quote":
        quote = '<blockquote style="' + styles["quote"] + '">' + html.escape(block_text(block))
        source = block.get("source")
        if source is not None:
            if not isinstance(source, str) or not source.strip():
                raise DocumentError("quote.source 必须是非空字符串。")
            quote += '<p style="' + styles["quote_source"] + '">' + html.escape(source.strip()) + "</p>"
        return quote + "</blockquote>"

    if block_type == "data":
        items = block.get("items")
        if not isinstance(items, list) or not items:
            raise DocumentError("data.items 必须是非空数组。")
        rows: list[str] = []
        for index, item in enumerate(items, start=1):
            if not isinstance(item, Mapping):
                raise DocumentError(f"data.items[{index}] 必须是对象。")
            label = required_text(item, "label")
            value = required_text(item, "value")
            note = optional_text(item, "note")
            value_html = "<strong>" + html.escape(value) + "</strong>"
            if note:
                value_html += '<p style="' + styles["data_note"] + '">' + html.escape(note) + "</p>"
            rows.append(
                "<tr><td style=\""
                + styles["data_label"]
                + "\">"
                + html.escape(label)
                + "</td><td style=\""
                + styles["data_value"]
                + "\">"
                + value_html
                + "</td></tr>"
            )
        return '<table style="' + styles["data_table"] + '"><tbody>' + "".join(rows) + "</tbody></table>"

    if block_type == "image":
        alt = block_text(block, "alt")
        caption = optional_text(block, "caption")
        source = optional_text(block, "src")
        if source:
            if source.lower().startswith(("javascript:", "data:text/html")):
                raise DocumentError("image.src 不能使用脚本或 HTML data URL。")
            image_html = (
                '<img style="'
                + styles["image"]
                + '" src="'
                + html.escape(source, quote=True)
                + '" alt="'
                + html.escape(alt, quote=True)
                + '">'
            )
        else:
            placeholder = caption or alt
            image_html = (
                '<section style="'
                + styles["image_placeholder"]
                + '">【配图建议】请在微信公众号后台上传图片：'
                + html.escape(placeholder)
                + "</section>"
            )
        if caption:
            image_html += '<p style="' + styles["image_caption"] + '">' + html.escape(caption) + "</p>"
        return image_html

    raise DocumentError(f"不支持的 block.type：{block_type}")


def render_document(document: Mapping[str, Any], theme: Mapping[str, Any]) -> str:
    validate_release_input(document)
    styles = theme["styles"]
    title = required_text(document, "title")
    source = required_text(document, "source")
    editor = required_text(document, "editor")
    published_date = required_text(document, "date")
    validate_date(published_date)
    summary = optional_text(document, "summary")
    blocks = document.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise DocumentError("blocks 必须是非空数组。")

    rendered_blocks = []
    for index, block in enumerate(blocks, start=1):
        if not isinstance(block, Mapping):
            raise DocumentError(f"blocks[{index}] 必须是对象。")
        rendered_blocks.append(render_block(block, styles))

    footer = (
        '<p style="'
        + styles["footer"]
        + '"><span style="'
        + styles["footer_label"]
        + '">来源：</span>'
        + html.escape(source)
        + '<span style="'
        + styles["footer_separator"]
        + '">|</span><span style="'
        + styles["footer_label"]
        + '">责编：</span>'
        + html.escape(editor)
        + '<span style="'
        + styles["footer_separator"]
        + '">|</span><span style="'
        + styles["footer_label"]
        + '">发布日期：</span>'
        + html.escape(published_date)
        + "</p>"
    )
    parts = [
        '<section style="' + styles["root"] + '">',
        '<p style="' + styles["title"] + '"><strong>' + html.escape(title) + "</strong></p>",
    ]
    if summary:
        parts.append('<p style="' + styles["summary"] + '">' + html.escape(summary) + "</p>")
    parts.extend(rendered_blocks)
    parts.append(footer)
    parts.append("</section>")
    fragment = "".join(parts)
    errors = validate_html(fragment, theme)
    if errors:
        raise DocumentError("生成结果未通过兼容性校验：" + "；".join(errors))
    return fragment


class FragmentInspector(HTMLParser):
    def __init__(self, theme: Mapping[str, Any]) -> None:
        super().__init__(convert_charrefs=True)
        validation = theme["validation"]
        self.allowed_tags = set(validation["allowed_tags"])
        self.allowed_attributes = set(validation["allowed_attributes"])
        self.allowed_properties = set(validation["allowed_style_properties"])
        self.errors: list[str] = []
        self.image_styles: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._inspect_tag(tag, attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._inspect_tag(tag, attrs)

    def _inspect_tag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in self.allowed_tags:
            self.errors.append(f"不允许的 HTML 标签：{tag}")
        attr_map = dict(attrs)
        for name, value in attrs:
            if name not in self.allowed_attributes:
                self.errors.append(f"{tag} 含不允许的属性：{name}")
            if name.startswith("on"):
                self.errors.append(f"{tag} 含事件属性：{name}")
            if name == "style":
                self._inspect_style(tag, value or "")
            if name == "src" and (value or "").strip().lower().startswith(("javascript:", "data:text/html")):
                self.errors.append("图片 src 不能包含脚本或 HTML data URL。")
        if tag == "img":
            self.image_styles.append(attr_map.get("style") or "")

    def _inspect_style(self, tag: str, style: str) -> None:
        for declaration in style.split(";"):
            declaration = declaration.strip()
            if not declaration:
                continue
            if ":" not in declaration:
                self.errors.append(f"{tag} 存在无效的内联样式声明。")
                continue
            property_name, value = declaration.split(":", 1)
            property_name = property_name.strip().lower()
            value = value.strip().lower()
            if property_name not in self.allowed_properties:
                self.errors.append(f"不允许的 CSS 属性：{property_name}")
            if "var(" in value or "expression(" in value or "javascript:" in value:
                self.errors.append(f"{tag} 的样式值不安全。")


def validate_html(fragment: str, theme: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    lowered = fragment.lower()
    for fragment_to_forbid in ("<style", "<script", "<link", "<iframe", "javascript:", "var(--", "@media", "@keyframes"):
        if fragment_to_forbid in lowered:
            errors.append(f"发现不兼容内容：{fragment_to_forbid}")
    if re.search(r"\s(?:class|id|on[a-z]+)\s*=", lowered):
        errors.append("发现 class、id 或事件属性。")
    if re.search(r"(?<![-a-z])(?:position|animation|transition|transform)\s*:", lowered):
        errors.append("发现不建议粘贴到微信编辑器的动态或定位样式。")

    inspector = FragmentInspector(theme)
    try:
        inspector.feed(fragment)
        inspector.close()
    except Exception as exc:
        errors.append(f"HTML 解析失败：{exc}")
    errors.extend(inspector.errors)

    if "<section" not in lowered:
        errors.append("缺少内容根 section。")
    if "font-size: 16px" not in lowered:
        errors.append("缺少 16px 正文字号。")
    if "line-height: 1.75" not in lowered:
        errors.append("缺少 1.75 行距。")
    for field in ("来源：", "责编：", "发布日期："):
        if field not in fragment:
            errors.append(f"缺少文末落款字段：{field}")
    if not re.search(r"发布日期：</span>\d{4}-\d{2}-\d{2}", fragment):
        errors.append("发布日期格式不正确。")
    for style in inspector.image_styles:
        normalized = style.replace(" ", "").lower()
        if "width:100%" not in normalized or "max-width:100%" not in normalized:
            errors.append("图片必须设置 width: 100% 和 max-width: 100%。")
    return list(dict.fromkeys(errors))


def build_preview(fragment: str, title: str) -> str:
    safe_title = html.escape(title)
    return """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>""" + safe_title + """ - 微信排版预览</title>
<style>
body { margin: 0; background: #eef2f5; color: #1f2933; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
main { max-width: 760px; margin: 0 auto; padding: 24px 16px 48px; }
.toolbar { display: flex; gap: 12px; align-items: center; margin: 0 0 16px; padding: 12px; background: #ffffff; border: 1px solid #d8e0e7; border-radius: 6px; }
button { border: 0; border-radius: 4px; padding: 9px 14px; color: #ffffff; background: #1f5b8f; font-size: 14px; cursor: pointer; }
#copy-status { color: #52616b; font-size: 13px; }
#preview-shell { overflow: hidden; padding: 24px 16px; background: #ffffff; box-shadow: 0 1px 8px rgba(31, 91, 143, 0.12); }
</style>
</head>
<body>
<main>
  <div class="toolbar">
    <button id="copy-button" type="button">复制可粘贴 HTML</button>
    <span id="copy-status">复制后可直接粘贴到公众号编辑器。</span>
  </div>
  <div id="preview-shell">
    <div id="wechat-content">""" + fragment + """</div>
  </div>
</main>
<script>
(function () {
  var button = document.getElementById("copy-button");
  var status = document.getElementById("copy-status");
  var article = document.getElementById("wechat-content");
  function fallbackCopy() {
    var range = document.createRange();
    range.selectNodeContents(article);
    var selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    var copied = document.execCommand("copy");
    selection.removeAllRanges();
    return copied;
  }
  button.addEventListener("click", async function () {
    try {
      var source = article.innerHTML;
      if (window.ClipboardItem && navigator.clipboard && window.isSecureContext) {
        var item = new ClipboardItem({
          "text/html": new Blob([source], { type: "text/html" }),
          "text/plain": new Blob([article.innerText], { type: "text/plain" })
        });
        await navigator.clipboard.write([item]);
      } else if (!fallbackCopy()) {
        throw new Error("浏览器不允许复制");
      }
      status.textContent = "已复制 HTML；请粘贴到公众号测试图文并保存后复查。";
    } catch (error) {
      status.textContent = "自动复制失败，请手动选中正文区域复制。";
    }
  });
}());
</script>
</body>
</html>
"""


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="将结构化政务稿渲染为微信可粘贴的内联 HTML。")
    parser.add_argument("--input", required=True, type=Path, help="UTF-8 JSON 输入文件")
    parser.add_argument("--output", required=True, type=Path, help="输出 HTML 片段文件")
    parser.add_argument("--preview", type=Path, help="可选的本地预览 HTML 文件")
    parser.add_argument("--config", type=Path, default=DEFAULT_THEME_PATH, help="主题配置 JSON")
    args = parser.parse_args(argv)

    try:
        document = load_json(args.input)
        theme = load_theme(args.config)
        fragment = render_document(document, theme)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(fragment, encoding="utf-8")
        if args.preview:
            args.preview.parent.mkdir(parents=True, exist_ok=True)
            args.preview.write_text(build_preview(fragment, required_text(document, "title")), encoding="utf-8")
    except DocumentError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    print(f"已生成微信 HTML：{args.output}")
    if args.preview:
        print(f"已生成本地预览：{args.preview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
