# 输入结构

渲染器接收 UTF-8 JSON 对象。固定八要素是标题、正文段落、重点句、引用政策、数据、配图说明、来源单位、责编；此外必须提供发布日期。用途和目标篇幅用于提交阶段的约束，可选填写。文本会被 HTML 转义，因此不要在字段中预先写 HTML。

    {
      "title": "标题",
      "purpose": "policy-interpretation",
      "target_length": "800-1200字",
      "summary": "可选导语",
      "blocks": [
        {"type": "paragraph", "text": "正文。", "emphasis": ["需要强调的短语"], "source_ref": ["p1"]},
        {"type": "heading", "text": "一、一级小标题", "source_ref": ["p2"]},
        {"type": "highlight", "text": "经审核的重点提醒。", "source_ref": ["p3"]},
        {"type": "quote", "text": "政策原文或权威表述。", "source": "《政策名称》", "source_ref": ["p4"]},
        {"type": "data", "items": [{"label": "事项", "value": "数值", "note": "可选注释"}], "source_ref": ["p5"]},
        {"type": "image", "alt": "图片无障碍说明", "caption": "图注", "src": "可选、由用户提供的图片地址", "source_ref": ["p6"]}
      ],
      "source_paragraphs": [{"id": "p1", "text": "对应的原文段落。"}],
      "summary_source_ref": "p1",
      "source": "来源单位",
      "editor": "责编姓名或部门",
      "date": "2026-10-26"
    }

块顺序即发布顺序。source_ref 是可回溯锚点：启用 source_paragraphs 后，每个块都必须回指一个或多个原文段落，summary 也必须通过 summary_source_ref 回指原文。无法回指时应补充锚点或还原为原文，不得交付。

image 没有 src 时会生成“配图建议”占位文本，提示编辑人员在公众号后台上传图片；它不会编造或下载图片。当前 1.0 只做结构化文本到微信可粘贴排版稿，不自动改写标题、不自动生成图片。
