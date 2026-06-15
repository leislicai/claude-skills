# 管线示例输出（v2.7）

3 份天水市住房公积金政策文档经四阶段管线处理的全量产出。

**源文档：**
1. 住房公积金管理条例
2. 治理违规提取住房公积金通知
3. 2025年度缴存基数调整通知

**格式：** 全部使用 v2.7 内联 JSON 模板验证通过的统一格式。

## 产出总览

| 阶段 | 产出 | 质量 |
|------|------|------|
| Stage 1 — 块提取 | **29 blocks** | 0 errors, 0 warnings |
| Stage 2 — 实体提取 | **13 entities + 38 relations** | 100% related, 0 英文违规 |
| Stage 3 — Wiki 编译 | **13 pages** | 0 errors, 0 warnings |
| Stage 4 — QA 生成 | **95 QA pairs** | 0 errors, 0 warnings |

## 文件结构

```
pipeline-output/
├── blocks/              # 29 个知识块 (kb_001 ~ kb_029)
├── entities.json        # 13 个规范实体 + 38 条关系
├── wiki/                # 13 个 Wiki 页面
├── qa_pairs.json        # 95 个 QA 对
└── quality-reports/     # 4 份机械检查报告（全部 passed）
```

## 格式规范

**Block：** entities 为字符串数组，source 为 {file, title, section, line_range}  
**Entity：** 中文描述名，relations 含 evidence_block_ids ≥3  
**Wiki：** 扁平 YAML frontmatter（entity_id/title/entity_type/version/status/compiled_at/source_block_ids/related_entities）  
**QA：** {qa_pairs: [...]} 包装，每个 QA 含 source_block_ids + quality.confidence + quality.wiki_version
