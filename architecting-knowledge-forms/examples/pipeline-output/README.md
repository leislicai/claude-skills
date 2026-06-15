# 管线示例输出

本目录包含一次精简管线执行产物——3 份天水市住房公积金政策文档经过 Stage 1 块提取的结构化输出。

**格式版本：** v2.7（内联 JSON 模板验证通过）  
**源文档：** 住房公积金管理条例、治理违规提取通知、2025年度缴存基数调整  
**产出：** 48 个知识块

## 文件结构

```
pipeline-output/
└── blocks/               # 48 个知识块（JSON）
    ├── kb_001.json       # 管理条例（27 块）
    ├── kb_028.json       # 治理通知（10 块）
    └── kb_038.json       # 2025年度调整（11 块）
```

## Block 格式

```json
{
  "id": "kb_001",
  "content": "完整原始文本",
  "summary": "一句中文概括",
  "entities": ["ent_中文名"],
  "tags": ["condition"],
  "source": {"file": "文件名", "title": "标题", "section": "章节", "line_range": "18-19"},
  "quality": {"confidence": 0.95}
}
```

- entities 为字符串数组，中文 ent_ 前缀
- source 统一为 {file, title, section, line_range}
- 7 个标准字段，不增不减
