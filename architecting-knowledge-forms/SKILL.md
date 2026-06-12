---
name: architecting-knowledge-forms
description: Designing and executing multi-form knowledge pipelines — blocks, graph, wiki, QA pairs. Domain configs, prompt templates, 4-stage sub-agent orchestration.
version: 2.4.0
tags: [knowledge-management, rag, architecture, data-modeling, pipeline]
author: leislicai
---

# Architecting Knowledge Forms

## Overview

**Knowledge blocks are the single write target; graph, wiki, and QA pairs are derived from them — each with different update characteristics.** This skill provides both the architecture to design such systems and the execution pipeline to process documents through all four stages.

## Platform Adaptation

This skill is platform-agnostic. All prompts, schemas, and domain configs work across any agent platform that supports sub-agent dispatch.

| Concept | Claude Code | Codex | Generic term used in this skill |
|---------|------------|-------|--------------------------------|
| Load skill | `Skill` tool | `skill` tool | "load this skill" |
| Dispatch sub-agent | `Agent` tool | `task` tool | "dispatch a sub-agent" |
| Read/write files | `Read` / `Write` | `read` / `write` | "read/write the file" |

**What's platform-agnostic (no changes needed):**
- `prompts/*.md` — sub-agent instructions ("You are a ... agent")
- `schemas/*.yaml` — output contracts
- `domains/*.yaml` — domain configuration
- Pipeline logic — READ→SUBSTITUTE→DISPATCH, Between-Stages validation, cascade updates, error handling, resumption

**What needs platform-specific translation:**
Only the `DISPATCH` step in each Stage — translate "dispatch a sub-agent" to your platform's sub-agent API. The rest of this skill reads identically across platforms.

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

Sub-agents run in isolated contexts — they cannot read files from the orchestrator's filesystem unless the platform explicitly supports it. To work across platforms safely, the orchestrator must **READ → SUBSTITUTE → DISPATCH**:

1. **READ** the prompt template and any input data files
2. **SUBSTITUTE** all `{variable}` placeholders with actual content (inlined, not referenced)
3. **DISPATCH** the fully-resolved prompt string as a sub-agent task

Never pass a file path to a sub-agent. Always inline the content.

### Step 0: Gather Context

Ask the user:

1. **What domain?** (e.g. 公积金, 医保, 法务, or "通用")
2. **What subset?** Default: all four forms. User can limit: "stop after graph" or "just blocks + QA".
3. **Where are the source documents?** A directory path or list of files.
4. **Where to write pipeline output?** Default: `./pipeline-output` in the current working directory. User can specify any path.

Then resolve the domain config:

```
1. ls domains/ to list available configs
2. For each .yaml file, read it and check domain.applies_to for a match
3. If match found → use that config
4. If no match → use domains/generic.yaml
5. Offer to save a new domain config for unrecognized domains
```

Create the output directory at the user-specified path:

```bash
mkdir -p {output_dir}/blocks {output_dir}/wiki
```

All subsequent pipeline references to `pipeline-output/` should use `{output_dir}/` instead.

### Step 1: Stage 1 — Block Extraction (per document, parallel, isolated)

Parallel agents writing to a shared directory causes ID collisions. Each agent writes to a temp subdirectory; the orchestrator normalizes after all complete.

```
1. LIST source files in the user's document directory
2. READ prompts/block-extraction.md
3. READ the matched domain config .yaml
4. For EACH source document:
   a. Assign a short doc_id (sanitized filename, e.g. "公积金管理条例")
   b. In the prompt template, replace:
      - {document_path} → the path to this single document
      - {output_dir} → {user_output_dir}/blocks/temp/{doc_id}/
      - {domain_config} → the full domain config YAML (inlined)
   c. DISPATCH 1 sub-agent for this document
5. Dispatch up to 8 agents in parallel. Wait for all.
6. After ALL agents complete:
   a. Gather all .json files from {output_dir}/blocks/temp/*/
   b. Renumber them as kb_001.json, kb_002.json, ... sequentially into {output_dir}/blocks/
   c. Delete temp directories
   d. Run Between-Stages validation
```

Each sub-agent writes to its OWN temp directory — no collisions. The orchestrator owns the final numbering, guaranteeing unique sequential IDs.

**Resumption check:** If `{output_dir}/blocks/` already contains .json files that pass Between-Stages validation, ask the user: "Existing blocks found. Re-extract all, or only re-extract changed documents?" For changed-documents-only, compare source file timestamps against block timestamps and only dispatch agents for new/modified files.

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

The sub-agent reads all blocks, normalizes entities (with old→new ID mapping), then extracts relations from entity co-occurrence patterns (≥3 shared blocks). Outputs `pipeline-output/entities.json` following [schemas/entities.schema.yaml](schemas/entities.schema.yaml).

**Relation quality gate:** Stage 2 output MUST have ≥50% of entities with at least one relation. If not, the Between-Stages check flags it and the orchestrator asks whether to re-extract or proceed with sparse relations.

The sub-agent reads `pipeline-output/blocks/` (the orchestrator tells it the files are there, with the block count inlined in the prompt). Outputs `pipeline-output/entities.json` following [schemas/entities.schema.yaml](schemas/entities.schema.yaml).

### Step 3: Stage 3 — Wiki Compilation (prioritized, parallel)

Large entity catalogs (50+ entities) are too expensive for full parallel compilation. Prioritize by importance:

```
1. Wait for Stage 2 to complete
2. READ pipeline-output/entities.json to extract the entity list
3. Rank entities by importance score:
   score = number_of_source_block_ids + number_of_relations + (1.5 if type is 'policy' else 0)
   Sort descending. Top entities are the most heavily referenced, most connected policies.
4. Ask the user: "N entities found. Top M by importance are [list]. Compile all N, or only top M?"
   Default: compile policy + clause types only (typically covers 80%+ of knowledge value).
5. READ prompts/wiki-compilation.md
6. READ the domain config .yaml
7. For each selected entity:
   a. Filter pipeline-output/blocks/ for blocks whose entities[] contain this entity_id
   a2. If total token count of filtered blocks exceeds 60,000:
       - Prioritize blocks with highest quality.confidence
       - Include blocks whose tags match wiki skeleton section keys first
       - Summarize omitted blocks as: "[N additional blocks omitted due to context limit]"
   b. In the prompt template, replace:
      - {entity_id} → the entity's id
      - {entity_data} → the entity's entry from entities.json (inlined)
      - {relevant_blocks} → the filtered blocks' content + summary (inlined, not file paths)
      - {domain_config} → the full domain config YAML (inlined)
   c. DISPATCH 1 sub-agent per entity (parallel dispatch — each writes a different file)
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

### Between Stages: Validate Output

After each stage completes, before dispatching the next stage:

1. **Count.** If output file count is 0, stop and report: "Stage N produced no output. Check input data."
2. **Sample.** Pick 3 output files at random. Check required fields are present and non-empty.
3. **Stage-specific checks:**
   - Stage 1: Verify entity IDs use descriptive names (reject hash-based UUIDs like `ent_ea6cc483bf7d` — stop and require re-extraction).
   - Stage 2: Verify ≥50% of entities have at least one relation. If <50%, flag as sparse graph — ask user whether to re-extract relations or proceed.
   - Stage 3: Verify wiki frontmatter has all required fields (`entity_id`, `title`, `compilation.version`, `compilation.status`). Check filenames match frontmatter `entity_id`.
4. **Confidence scan.** If >20% of outputs have `quality.confidence < 0.5`, pause and ask the user whether to continue or fix the low-confidence outputs first.
5. **If checks pass** → dispatch next stage.
6. **If checks fail** → stop. Report which stage, which file, which field, and the validation error. Do not dispatch downstream stages.

### Cascade Update (Incremental Re-run)

When re-running after source documents change, the orchestrator must detect what changed and only re-derive affected artifacts:

1. Compare source document timestamps against `pipeline-output/blocks/*.json` timestamps → re-extract only changed documents
2. Compare `pipeline-output/blocks/` timestamps against `pipeline-output/entities.json` timestamp → re-extract entities only if blocks changed
3. For each wiki page, compare its `compilation.compiled_at` against the timestamps of blocks referencing its entity → recompile only stale wikis
4. For each QA pair, compare its `quality.wiki_version` against the current wiki `compilation.version` → regenerate only stale QAs

**Important:** The orchestrator must inline the stale-detection instructions into each sub-agent's prompt. Sub-agents don't automatically know what's stale — the orchestrator tells them by only passing the changed data.

## Error Handling

| Scenario | Action |
|----------|--------|
| Stage produces 0 output files | Stop. Report: "Stage N produced no output. Check input data." |
| Sub-agent returns empty or malformed output | Retry once with the same prompt. If retry fails, stop and report stage + error. |
| Sub-agent times out or fails | If the stage supports per-entity dispatch (wiki), retry only the failed entity. Otherwise stop. |
| Domain config YAML fails to parse | Fall back to generic.yaml. Warn user. |
| quality.confidence < 0.5 on >20% of outputs | Pause pipeline. Show warning count. Ask user: continue, fix and retry, or stop. |
| Pipeline interrupted mid-run | Check pipeline-output/ for existing files. Resume from the last complete stage whose output passes Between-Stages validation. |
| No domain matches user's input | Fall back to generic.yaml. Offer to save session rules as a new domain config. |

## Pipeline Resumption

Every stage writes to a distinct location. A stage is "complete" if its output exists and passes Between-Stages validation. The pipeline can resume from any stage:

```
Before each stage, check:
  if output exists AND passes validation:
    skip → proceed to next stage
  else:
    run this stage (not from Stage 1 — just this stage)
```

Example: Stage 1 passes, Stage 2 fails. Fix the issue, re-run — the orchestrator skips Stage 1 (blocks exist + pass validation) and resumes at Stage 2.

**Per-stage resumption logic:**

| Stage | Output to check | Action if valid |
|-------|----------------|-----------------|
| 1 | `{output_dir}/blocks/*.json` exists, count > 0, passes Between-Stages | Skip block extraction |
| 2 | `{output_dir}/entities.json` exists, passes Between-Stages | Skip entity extraction |
| 3 | `{output_dir}/wiki/*.md` exists, count > 0, passes Between-Stages | Skip wiki compilation. For incremental, only compile stale entities. |
| 4 | `{output_dir}/qa_pairs.json` exists, passes Between-Stages | Skip QA generation |

**Resumption check is the FIRST thing the orchestrator does at each Step.** It must happen before reading prompt templates or domain configs.

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
