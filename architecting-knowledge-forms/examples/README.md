# 真实管线示例

本目录包含一次真实管线执行的源文件和产物——天水市住房公积金政策文件管线执行结果。

**执行时间：** 2026-06-11
**源文件数：** 21 份 HTML 政策文件
**领域配置：** gov-services.yaml（政务服务政策文件）
**Prompt 版本：** v2.2（此示例生成后 prompt 有所更新——当前 v2.5 的 entity 粒度规则更严格）

## 管线产出

| Stage | 产物 | 数量 |
|-------|------|------|
| Stage 1 | `pipeline-output/blocks/` | 259 个知识块（展示 3 个） |
| Stage 2 | `pipeline-output/entities.json` | 147 个实体（77 个有关联关系，52%），1,100 条关系边 |
| Stage 3 | `pipeline-output/wiki/` | 15 个 Wiki 页面（展示 1 个） |
| Stage 4 | `pipeline-output/qa_pairs.json` | 50 个问答对 |

**注意：** 此示例生成于 v2.2 prompt 版本。当前 v2.5 的规则更严格：
- entities[] 必须带 `ent_` 前缀（示例中部分 block 缺少）
- entities[] 必须为跨 block 概念（示例中 `ent_30年期限` 仅 1 个 block）
- 这些不影响示例的教育用途，但新执行时产出的数据结构更规范

## 文件结构

```
examples/
├── source-doc.html                           # 原始文件（住房公积金管理条例）
├── README.md                                  # 本文件
└── pipeline-output/
    ├── blocks/
    │   ├── kb_001.json                        # 条例前言 + 颁布信息
    │   ├── kb_002.json                        # 治理违规提取背景
    │   └── kb_003.json                        # 规范改进提取政策
    ├── entities.json                          # 全量实体目录（147 实体，1,100 关系边）
    ├── wiki/
    │   └── ent_住房公积金管理条例.md          # 核心 Wiki 页面
    └── qa_pairs.json                          # 全量 QA 对（50 条）
```
