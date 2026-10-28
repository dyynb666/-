---
name: wechat-government-layout
description: Convert approved, structured Chinese government releases (policy interpretations, work updates, and assessment briefs) into restrained, WeChat-editor-ready HTML with inline styles and a local copyable preview. Use when formatting rather than rewriting the content.
---

# 政务微信排版

将已审核的结构化政务发布稿转换为可粘贴进微信公众号编辑器的 HTML 片段。保持原文事实、语气和标题，不添加营销化标题、自动配图或改写内容。统一使用红金庄重政务母版。

## 工作方式

1. 提交结构化文本与要求：按[输入结构](references/input-schema.md)提供八要素，并填写用途、目标篇幅（如有）。缺少标题、正文、重点、引用、数据、配图说明、来源单位或责编时退回补全。
2. 解析与结构化：正文按内容类型使用 paragraph、heading、highlight、quote、data、image；不改写标题和结论。图片说明只能生成占位提示，不能擅自生成图片。
3. 受约束排版重排：块顺序可以按发布逻辑重排，但启用 source_paragraphs 后每个块必须通过 source_ref 回指原文；summary 必须通过 summary_source_ref 回指原文。回不去就补锚或还原，不交付。
4. 按红金政务母版渲染：使用 scripts/render_wechat.py 生成内联 HTML 和独立预览页；字号、行距、主色和引用样式只在 config/default_theme.json 中配置。
5. 自查与放行：运行 scripts/validate_wechat.py，确认 HTML 安全、三要素落款齐全、标题克制、手机端图片不溢出，再交付。

## 命令

    python scripts/render_wechat.py --input examples/policy-interpretation.json --output output/article.html --preview output/preview.html
    python scripts/validate_wechat.py output/article.html

输出文件 article.html 是仅包含内容的 HTML 片段，可复制粘贴；preview.html 仅供本地预览和复制，复制控件不在正文片段中。

## 边界

- 使用 section、p、span、strong、blockquote、table 和 img 等保守标签，全部内联样式；不得把 style、script、class、CSS 变量或事件属性放进可粘贴的 HTML。
- 限制为干净、克制的红金政务样式。不要新增模板市场、拖拽编辑器、动画、渐变大色块或内容创作能力。
- 图片 URL 只有在用户已提供时才输出为图片；否则输出“配图建议”占位，提醒在公众号后台上传图片。
