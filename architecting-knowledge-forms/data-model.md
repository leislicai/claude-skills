# Data Model Reference

Concrete schemas for the four knowledge forms. These are **logical schemas** — land them as JSON files on disk, then optionally ingest into databases. The cross-reference topology is what matters, not the storage engine.

## Knowledge Block (Single Write Target)

```yaml
knowledge_block:
  id: "kb_001"
  content: "Full original text"
  summary: "One-line summary"
  entities: ["ent_SigningBonusPolicy", "ent_TalentAcquisitionProgram"]  # → graph nodes
  tags: ["bonus", "phd"]
  source: {doc_id, paragraph, line_range}                              # Source anchor
  embedding: [...]                                                      # Vector
```

**Quality constraints:** content MUST be non-empty. source MUST resolve to a real document location. entities[] values MUST exist in the graph after entity extraction runs.

## Knowledge Graph (Extracted from blocks.entities[])

```yaml
entity:
  id: "ent_SigningBonusPolicy"                       # == value in blocks.entities[]
  name: "Signing Bonus Policy"
  type: "Policy Clause"
  properties: {amount: "30000", disbursement: "one-time"}
  relations:
    - {target: "ent_TalentAcquisitionProgram", predicate: "part_of"}
  source_block_ids: ["kb_001", "kb_015"]             # ← Trace back to blocks
```

Entities and relations extracted from blocks, written to a flat JSON array or graph DB. Relations are direct entity→entity edges (not mediated through blocks).

## Wiki Page (Compiled from blocks grouped by entity)

```yaml
wiki_page:
  entity_id: "ent_SigningBonusPolicy"                # 1:1 with graph entity
  title: "Signing Bonus Policy"
  sections:                                          # Compiled structure, not live-rendered
    - heading: "Standard"
      content: "..."
      source_block_ids: ["kb_001"]                   # ← Trace back to blocks
    - heading: "Scope"
      content: "..."
      source_block_ids: ["kb_015", "kb_022"]
  related_entities: ["ent_TalentAcquisitionProgram", "ent_HousingSubsidy"]
```

Compilation is a build step: GROUP blocks BY entity → organize into sections → preserve source_block_ids per section.

## QA Pair (Derived from Wiki, anchored to blocks)

```yaml
qa_pair:
  id: "qa_001"
  question: "What is the standard signing bonus for PhDs?"
  answer: "PhD signing bonus is $30,000, paid as a lump sum."
  source_block_ids: ["kb_001"]                       # ← Trace back to source
  entities: ["ent_SigningBonusPolicy"]
  intents: ["Query standard"]
```

## Cross-Reference Topology

```
                    ┌──────────────────────────────────────┐
                    │          Knowledge Block              │
                    │  (Single write target +               │
                    │   all trace endpoints)                │
                    └──┬─────────────┬─────────────────┬───┘
       source_block_ids │  entities[] │                 │ source_block_ids
                       │             │                 │
           ┌───────────┘             ▼                 └───────────┐
           ▼                   ┌──────────┐                       ▼
     ┌───────────┐             │  Entity   │──relations[]──▶ Other Entity
     │  QA Pair  │             │ id, name  │                (Direct edge,
     │ question  │             │ properties│                 not via Block)
     │ answer    │             └─────┬─────┘
     └───────────┘                   │ entity_id (1:1)
                                     ▼
                               ┌───────────┐
                               │ Wiki Page │
                               │ sections  │
                               └───────────┘
```

Trace arrows (source_block_ids) point back to Block. Traversal arrows (relations) connect Entity to Entity directly. These are edges with different purposes.

## Pipeline Output Directory

All intermediate artifacts land in `pipeline-output/` as JSON files. Sub-agents read from and write to this directory:

```
pipeline-output/
├── blocks/              # Stage 1 output
│   ├── kb_001.json
│   ├── kb_002.json
│   └── ...
├── entities.json        # Stage 2 output (single file)
├── wiki/                # Stage 3 output
│   ├── ent_SigningBonusPolicy.md
│   └── ...
└── qa_pairs.json        # Stage 4 output (single file)
```

Schemas for each file: see [schemas/](schemas/).

## Cascade Update Model

One document change triggers cascading updates across the pipeline:

```
1 document changed
  → N blocks re-extracted (Stage 1)
    → M entities updated (Stage 2)
      → M wiki pages recompiled (Stage 3)
        → ~5×M QA pairs regenerated (Stage 4)
```

**How to compute affected scope:** For each changed block, trace through `entities[]` to find affected entities. For each affected entity, find its wiki page. For each wiki page, find its QA pairs. The `source_block_ids` field on every artifact is the reverse index — it tells you what depends on what.

**Incremental strategy:** After Stage N completes, compare timestamps. Any downstream artifact whose source blocks have newer timestamps than its own `compiled_at` (wiki) or `wiki_version` (QA) is stale and must be re-derived.

## Domain Configuration

Domain-specific rules live in [domains/](domains/). Each domain config provides:
- Chunking strategy (structural, semantic, hybrid)
- Entity type system and relation predicates
- Wiki page skeleton
- QA templates
- Quality rules (format, semantic, domain-specific)

When no domain config matches, fall back to generic heuristics: semantic chunking, open entity discovery, flat wiki structure with overview+references sections.
