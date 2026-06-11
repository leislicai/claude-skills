# Data Model Reference

Concrete schemas for the four knowledge forms. These are **logical schemas** — land them as JSON files on disk, then optionally ingest into databases. The cross-reference topology is what matters, not the storage engine.

## Knowledge Block（唯一写入点）

```yaml
knowledge_block:
  id: "kb_001"
  content: "原始文本全文"
  summary: "一句话摘要"
  entities: ["ent_博士安家费", "ent_人才引进"]   # → graph nodes
  tags: ["安家费", "博士"]
  source: {doc_id, paragraph, line_range}        # 原文锚点
  embedding: [...]                                # 向量
```

**Quality constraints:** content MUST be non-empty. source MUST resolve to a real document location. entities[] values MUST exist in the graph after entity extraction runs.

## Knowledge Graph（从 blocks.entities 抽取）

```yaml
entity:
  id: "ent_博士安家费"                             # == blocks.entities 中的值
  name: "博士安家费"
  type: "政策条款"
  properties: {金额: "30万", 发放: "一次性"}
  relations:
    - {target: "ent_人才引进", predicate: "属于"}
  source_block_ids: ["kb_001", "kb_015"]          # ← 溯源回 blocks
```

Entities and relations extracted from blocks, written to a flat JSON array or graph DB. Relations are direct entity→entity edges (not mediated through blocks).

## Wiki Page（从 blocks 按 entity 聚合编译）

```yaml
wiki_page:
  entity_id: "ent_博士安家费"                      # 1:1 对应 graph entity
  title: "博士安家费"
  sections:                                        # 编译结构，非动态渲染
    - heading: "标准"
      content: "..."
      source_block_ids: ["kb_001"]                # ← 溯源回 blocks
    - heading: "适用范围"
      content: "..."
      source_block_ids: ["kb_015", "kb_022"]
  related_entities: ["ent_人才引进", "ent_购房补贴"]
```

Compilation is a build step: GROUP blocks BY entity → organize into sections → preserve source_block_ids per section.

## QA Pair（从 Wiki 推导，锚定到 blocks）

```yaml
qa_pair:
  id: "qa_001"
  question: "博士安家费标准是多少？"
  answer: "博士安家费标准为30万元，一次性发放。"
  source_block_ids: ["kb_001"]                    # ← 溯源回原文
  entities: ["ent_博士安家费"]
  intents: ["查询标准"]
```

## Cross-Reference Topology

```
                    ┌──────────────────────────────────────┐
                    │          Knowledge Block              │
                    │  (唯一写入 + 所有溯源终点)              │
                    └──┬─────────────┬─────────────────┬───┘
       source_block_ids │  entities[] │                 │ source_block_ids
                       │             │                 │
           ┌───────────┘             ▼                 └───────────┐
           ▼                   ┌──────────┐                       ▼
     ┌───────────┐             │  Entity   │──relations[]──▶ 其他 Entity
     │  QA Pair  │             │ id, name  │                (直接边，
     │ question  │             │ properties│                 不经过Block)
     │ answer    │             └─────┬─────┘
     └───────────┘                   │ entity_id (1:1)
                                     ▼
                               ┌───────────┐
                               │ Wiki Page │
                               │ sections  │
                               └───────────┘
```

**溯源箭头（source_block_ids）回到 Block。遍历箭头（relations）直接连接 Entity。两者是不同目的的边。**
