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
