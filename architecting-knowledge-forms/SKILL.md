---
name: architecting-knowledge-forms
description: Designing and executing multi-form knowledge pipelines — blocks, graph, wiki, QA pairs. Domain configs, prompt templates, 4-stage sub-agent orchestration.
version: 2.1.0
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

### How Orchestration Works

Sub-agents are independent Claude instances — they cannot read files from the orchestrator's filesystem. The orchestrator must **READ → SUBSTITUTE → DISPATCH**:

1. **READ** the prompt template and any input data files
2. **SUBSTITUTE** all `{variable}` placeholders with actual content (inlined, not referenced)
3. **DISPATCH** the fully-resolved prompt string to the sub-agent via the Agent tool

Never pass a file path to a sub-agent. Always inline the content.

### Step 0: Gather Context

Ask the user:

1. **What domain?** (e.g. 公积金, 医保, 法务, or "通用")
2. **What subset?** Default: all four forms. User can limit: "stop after graph" or "just blocks + QA".
3. **Where are the source documents?** A directory path or list of files.

Then resolve the domain config:

```
1. ls domains/ to list available configs
2. For each .yaml file, read it and check domain.applies_to for a match
3. If match found → use that config
4. If no match → use domains/generic.yaml
5. Offer to save a new domain config for unrecognized domains
```

Create the output directory:

```bash
mkdir -p pipeline-output/blocks pipeline-output/wiki
```

### Step 1: Stage 1 — Block Extraction

```
1. READ prompts/block-extraction.md
2. READ the matched domain config .yaml
3. In the prompt template, replace:
   - {input_dir} → the user's source document path
   - {domain_config} → the full domain config YAML (inlined)
4. DISPATCH 1 sub-agent with the resolved prompt
```

The sub-agent writes `pipeline-output/blocks/*.json` following [schemas/blocks.schema.yaml](schemas/blocks.schema.yaml).

### Step 2: Stage 2 — Entity Extraction

```
1. Wait for Stage 1 to complete
2. READ prompts/entity-extraction.md
3. READ the domain config .yaml
4. LIST pipeline-output/blocks/ to confirm blocks exist
5. In the prompt template, replace:
   - {domain_config} → the full domain config YAML (inlined)
6. DISPATCH 1 sub-agent with the resolved prompt
```

The sub-agent reads `pipeline-output/blocks/` (the orchestrator tells it the files are there, with the block count inlined in the prompt). Outputs `pipeline-output/entities.json` following [schemas/entities.schema.yaml](schemas/entities.schema.yaml).

### Step 3: Stage 3 — Wiki Compilation

```
1. Wait for Stage 2 to complete
2. READ pipeline-output/entities.json to extract the entity list
3. READ prompts/wiki-compilation.md
4. READ the domain config .yaml
5. For each entity in entities.json:
   a. Filter pipeline-output/blocks/ for blocks whose entities[] contain this entity_id
   b. In the prompt template, replace:
      - {entity_id} → the entity's id
      - {entity_data} → the entity's entry from entities.json (inlined)
      - {relevant_blocks} → the filtered blocks' content + summary (inlined, not file paths)
      - {domain_config} → the full domain config YAML (inlined)
   c. DISPATCH 1 sub-agent per entity (parallel dispatch is safe — each writes a different file)
```

Each sub-agent writes `pipeline-output/wiki/{entity_id}.md` following [schemas/wiki.schema.yaml](schemas/wiki.schema.yaml).

### Step 4: Stage 4 — QA Generation

```
1. Wait for all Stage 3 agents to complete
2. READ prompts/qa-generation.md
3. READ the domain config .yaml
4. In the prompt template, replace:
   - {domain_config} → the full domain config YAML (inlined, especially qa_templates)
5. DISPATCH 1 sub-agent with the resolved prompt
```

The sub-agent reads `pipeline-output/wiki/` and `pipeline-output/entities.json`, outputs `pipeline-output/qa_pairs.json` following [schemas/qa.schema.yaml](schemas/qa.schema.yaml).

### Cascade Update (Incremental Re-run)

When re-running after source documents change, the orchestrator must detect what changed and only re-derive affected artifacts:

1. Compare source document timestamps against `pipeline-output/blocks/*.json` timestamps → re-extract only changed documents
2. Compare `pipeline-output/blocks/` timestamps against `pipeline-output/entities.json` timestamp → re-extract entities only if blocks changed
3. For each wiki page, compare its `compilation.compiled_at` against the timestamps of blocks referencing its entity → recompile only stale wikis
4. For each QA pair, compare its `quality.wiki_version` against the current wiki `compilation.version` → regenerate only stale QAs

**Important:** The orchestrator must inline the stale-detection instructions into each sub-agent's prompt. Sub-agents don't automatically know what's stale — the orchestrator tells them by only passing the changed data.

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
