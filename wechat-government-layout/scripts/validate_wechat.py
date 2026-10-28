#!/usr/bin/env python3
"""Validate a generated WeChat HTML fragment against the configured safe subset."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from render_wechat import DEFAULT_THEME_PATH, DocumentError, load_theme, validate_html


def main() -> int:
    parser = argparse.ArgumentParser(description="校验微信公众号可粘贴 HTML 片段。")
    parser.add_argument("html_file", type=Path, help="待校验的 HTML 片段")
    parser.add_argument("--config", type=Path, default=DEFAULT_THEME_PATH, help="主题配置 JSON")
    args = parser.parse_args()

    try:
        fragment = args.html_file.read_text(encoding="utf-8")
        theme = load_theme(args.config)
        errors = validate_html(fragment, theme)
    except (OSError, DocumentError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    if errors:
        print("未通过微信兼容性校验：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("通过微信 HTML 本地兼容性校验。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
