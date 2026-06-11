---
name: architecting-knowledge-forms
description: Use when designing knowledge management systems and facing pressure to build separate stores for search, graph, wiki, QA — or when deciding how chunks, entities, wiki pages, and QA pairs relate
---

# Architecting Knowledge Forms

## Overview

**Knowledge blocks are the single write target; graph, wiki, and QA pairs are derived from them — each with different update characteristics.** This prevents N independent stores + ETL sync, which causes inconsistency, granularity drift, and exponential maintenance.

## When to Use

**Apply when:**
- Designing a knowledge system's data model
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
Document → [Chunk] → Knowledge Blocks (唯一写入)
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

Each stage is a controlled pipeline step. Stage N+1 starts only after Stage N completes (for its affected blocks). Incremental: only re-derive views for changed blocks.

### The Rules

1. **One write target.** Blocks are the only write target. Graph, Wiki, QA derived via controlled pipeline steps, not independent write paths. Views CAN use different engines (Neo4j for graph, files for wiki, Qdrant for QA vectors).

2. **Entity granularity aligns.** Block entity tags, graph nodes, and wiki pages share one granularity. If graph has `博士安家费` as a node, there is a wiki page for it and blocks tagged with it.

3. **Wiki is compiled, not rendered.** Build step triggered by block updates — preserves curated structure (summaries, cross-references). Compile incrementally if near-real-time needed; never render dynamically from graph queries.

4. **QA pairs derive from Wiki.** Wiki provides curated context — higher precision, less noise. Without Wiki, derive from blocks with explicit quality trade-off.

5. **Block quality gates derivation.** Content must be non-empty. Source trace must resolve to a real document location. Entities[] must be resolvable after graph extraction runs. A corrupt block poisons all downstream views — validate at write time.

### Partial Forms

The pattern works with any subset. Common subsets and their starting point:

| Subset | Use Case | First Build |
|--------|----------|-------------|
| Blocks only | Semantic search | Block extraction |
| Blocks + Graph | Search + relationship nav | + entity extraction |
| Blocks + Wiki | Knowledge browsing | + compilation |
| Blocks + QA | RAG Q&A | + Q generation |
| All four | Full knowledge platform | Full pipeline |

Constraint: **if you have >1 form, sync via derivation from blocks, never ETL between views.**

### Data Model

See [data-model.md](data-model.md) for concrete schemas (YAML), cross-reference topology, and quality constraints.

## Anti-Patterns

| Anti-Pattern | Why It Fails |
|-------------|--------------|
| N independent stores + ETL | N×ETL maintenance; granularity drift; inconsistency |
| Graph as write-primary | Loses atomic traceability; blocks degrade to text chunks |
| Wiki as dynamic graph render | Auto-update destroys curation |
| QA from raw documents | Inherits noise; misses Wiki context |
| Entity granularity mismatch | Graph coarse, blocks fine → can't trace across forms |

## Red Flags

| Rationalization | Reality |
|----------------|---------|
| "Four databases synced via ETL" | Building N stores. One write target is the fix. |
| "The graph IS the knowledge" | Graph is the *relationship index*. Blocks are the knowledge. |
| "QA from raw docs is simpler" | Simpler to generate, worse quality. |
| "Wiki auto-updates from graph" | Auto-update = no curation. Compiled ≠ rendered. |
| "Views in different DBs = multi-store" | Different engines for READ are OK if write is unified. |
