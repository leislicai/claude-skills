# 真实管线示例

本目录包含一次真实管线执行的源文件和产物——处理对象为天水市住房公积金政策文件。

**执行时间：** 2026-06-11  
**源文件数：** 21 份 HTML 政策文件  
**领域配置：** gov-services.yaml（政务服务政策文件）

## 管线产出

| Stage | 产物 | 数量 |
|-------|------|------|
| Stage 1 | `pipeline-output/blocks/` | 259 个知识块（展示 3 个） |
| Stage 2 | `pipeline-output/entities.json` | 171 个实体 + 35 条关系 |
| Stage 3 | `pipeline-output/wiki/` | 15 个 Wiki 页面（展示 1 个） |
| Stage 4 | `pipeline-output/qa_pairs.json` | 50 个问答对 |

## 示例源文件

`source-doc.html` — 《住房公积金管理条例》全文

## 文件说明

```
examples/
├── source-doc.html                           # 原始文件
├── README.md                                  # 本文件
└── pipeline-output/
    ├── blocks/
    │   ├── kb_001.json                        # 条例前言 + 颁布信息
    │   ├── kb_002.json                        # 第一章 总则（第1-7条）
    │   └── kb_003.json                        # 第二章 机构及职责（第8-12条）
    ├── entities.json                          # 全量实体目录
    ├── wiki/
    │   └── ent_住房公积金管理条例.md           # 核心 Wiki 页面
    └── qa_pairs.json                          # 全量 QA 对
```

所有产物均通过 Between-Stages 校验，entity ID 为描述性中文名称（`ent_` 前缀），所有答案可溯源至原文段落。
