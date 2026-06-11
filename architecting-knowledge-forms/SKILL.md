---
name: architecting-knowledge-forms
description: Designing multi-form knowledge systems — blocks, graph, wiki, QA pairs
version: 2.0.0
tags: [knowledge-management, rag, architecture, data-modeling, pipeline]
author: leislicai
---

# Architecting Knowledge Forms

## Overview

**Knowledge blocks are the single write target; graph, wiki, and QA pairs are derived from them — each with different update characteristics.** This skill provides both the architecture to design such systems and the execution pipeline to process documents through all four stages.

## When to Use

**Apply when:**
- Designing a knowledge system's data model
- Processing documents through a multi-stage knowledge pipeline
- Deciding how chunks / graph / wiki / QA relate
- Evaluating separate stores vs unified architecture

**Do NOT use when:**
- Building a simple FAQ bot (just blocks + QA, skip graph and wiki)
- Pure document search (blocks + vector index, nothing else)
- Already have a working single-store architecture (don't over-design)

## Core Pattern

### The Four Forms

| Form | Role | Update |
|------|------|--------|
| **Knowledge Block** | Atomic, source-traced knowledge unit | **Write target** (immutable) |
| **Knowledge Graph** | Entity-relation index | Near-real-time (from blocks.entities[]) |
| **Wiki** | Curated entity pages, compiled | On block update (deferred build step) |
| **QA Pairs** | Q+A anchored to source | After Wiki (two-hop derivation) |

### Compilation Pipeline

```
Document → [Chunk] → Knowledge Blocks (single write target)
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
   Stage 2:        Stage 3:       Stage 4:
   Entity          Wiki           QA
   Extraction      Compilation    Generation
   (blocks.        (blocks GROUP  (from Wiki
   entities[]      BY entity →    pages →
   → entities      sections       Q+A pairs)
   + relations)    per entity)
```

### The Rules

1. **One write target.** Blocks are the only write target. Graph, Wiki, QA derived via controlled pipeline steps, not independent write paths.
2. **Entity granularity aligns.** Block entity tags, graph nodes, and wiki pages share one granularity.
3. **Wiki is compiled, not rendered.** Build step triggered by block updates — preserves curated structure. Compile incrementally; never render dynamically from graph queries.
4. **QA pairs derive from Wiki.** Wiki provides curated context — higher precision, less noise. Without Wiki, derive from blocks with explicit quality trade-off.
5. **Block quality gates derivation.** Content non-empty. Source trace valid. Entities[] resolvable. A corrupt block poisons all downstream views — validate at write time.

### Partial Forms

| Subset | Use Case | First Build |
|--------|----------|-------------|
| Blocks only | Semantic search | Block extraction |
| Blocks + Graph | Search + relationship nav | + entity extraction |
| Blocks + Wiki | Knowledge browsing | + compilation |
| Blocks + QA | RAG Q&A | + Q generation |
| All four | Full knowledge platform | Full pipeline |

Constraint: **if >1 form, sync via derivation from blocks, never ETL between views.**

## Pipeline Execution

### Step 0: Gather Context

Before dispatching any agent, ask the user:

1. **What domain?** Examples: 公积金, 医保, 法务, or "通用". Load the matching config from [domains/](domains/). If no config exists, fall back to generic heuristics and offer to save the session's rules as a new domain config.
2. **What subset?** Default to all four forms. User can say "stop after graph" or "just blocks + QA".
3. **Where are the source documents?** A directory path or list of files.

### Step 1: Dispatch Stage 1 — Block Extraction

Launch a sub-agent with [prompts/block-extraction.md](prompts/block-extraction.md). Pass:
- `input_dir`: source document directory
- `domain_config_path`: path to the loaded domain config

Output lands at `pipeline-output/blocks/*.json` following [schemas/blocks.schema.yaml](schemas/blocks.schema.yaml).

### Step 2: Dispatch Stage 2 — Entity Extraction

Once Stage 1 completes, launch a sub-agent with [prompts/entity-extraction.md](prompts/entity-extraction.md). The agent reads `pipeline-output/blocks/` and domain config, outputs `pipeline-output/entities.json` following [schemas/entities.schema.yaml](schemas/entities.schema.yaml).

### Step 3: Dispatch Stage 3 — Wiki Compilation

Once Stage 2 completes, launch **parallel** sub-agents — one per entity — with [prompts/wiki-compilation.md](prompts/wiki-compilation.md). Each agent reads `pipeline-output/blocks/` + `pipeline-output/entities.json`, outputs `pipeline-output/wiki/{entity_id}.md` following [schemas/wiki.schema.yaml](schemas/wiki.schema.yaml).

Parallel dispatch is safe here because wiki pages are independent (each agent reads the same blocks + entities, writes to a different file).

### Step 4: Dispatch Stage 4 — QA Generation

Once all wiki pages are compiled, launch a sub-agent with [prompts/qa-generation.md](prompts/qa-generation.md). The agent reads `pipeline-output/wiki/` + `pipeline-output/entities.json`, outputs `pipeline-output/qa_pairs.json` following [schemas/qa.schema.yaml](schemas/qa.schema.yaml).

### Cascade Update

When re-running on changed documents, only re-derive affected artifacts:

```
1 changed doc → N blocks changed → M entities affected → M wikis stale → ~5M QAs stale
```

Use `source_block_ids` as the reverse index. Compare timestamps: any artifact whose sources are newer than its own compilation timestamp is stale.

### Intermediate Artifacts

All data passes between agents via files, not through the orchestrator context:

```
pipeline-output/
├── blocks/          # Stage 1 → read by Stage 2, 3, 4
├── entities.json    # Stage 2 → read by Stage 3, 4
├── wiki/            # Stage 3 → read by Stage 4
└── qa_pairs.json    # Stage 4 → final output
```

This enables: inspecting intermediate results, hand-editing before the next stage, resuming from any stage after a failure, and parallel wiki compilation.

## Domain Configuration

See [domains/gov-services.yaml](domains/gov-services.yaml) for the gov-services domain template. Each domain config provides: chunking strategy, entity types, relation predicates, wiki skeleton, QA templates, and quality rules.

## Data Model

- [data-model.md](data-model.md) — Four-form schemas, cross-reference topology, cascade model
- [schemas/](schemas/) — Per-stage output schemas (the contract each sub-agent must follow)

## Anti-Patterns

| Anti-Pattern | Why It Fails |
|-------------|--------------|
| N independent stores + ETL | N×ETL maintenance; granularity drift; inconsistency |
| Graph as write-primary | Loses atomic traceability; blocks degrade to text chunks |
| Wiki as dynamic graph render | Auto-update destroys curation |
| QA from raw documents | Inherits noise; misses Wiki context |
| Entity granularity mismatch | Graph coarse, blocks fine → can't trace across forms |

## Red Flags

| Rationalization | Reality | Action |
|----------------|---------|--------|
| "Four databases synced via ETL" | Building N stores. | Surface Rule 1 (one write target). Ask to refactor before proceeding. |
| "The graph IS the knowledge" | Graph is the *relationship index*. | Point to data-model.md: blocks are the write target, graph is a derived view. |
| "QA from raw docs is simpler" | Simpler to generate, worse quality. | Suggest deriving from Wiki first. If no Wiki exists, accept the trade-off explicitly. |
| "Wiki auto-updates from graph" | Auto-update = no curation. | Explain compiled vs rendered. Offer incremental compilation as middle ground. |
| "Views in different DBs = multi-store" | Different engines for READ are OK. | Confirm: is the write path still unified? If yes, different engines are fine. |
