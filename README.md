# Claude Skills

Personal Claude Code skills collection.

## Skills

| Skill | Version | Description |
|-------|---------|-------------|
| [`architecting-knowledge-forms`](architecting-knowledge-forms/SKILL.md) | v2.5.0 | Design + execute multi-form knowledge pipelines — domain configs, prompt templates, schema contracts, 4-stage sub-agent orchestration |

**Language note:** This skill's entity-naming conventions and domain configs assume Chinese-language source documents. The orchestration pattern (temp isolation, resumption, Between-Stages validation, dynamic predicates) is language-agnostic and reusable.

## Pipeline

```
Document → [Block Extraction] → [Entity Extraction] → [Wiki Compilation] → [QA Generation]
              Stage 1               Stage 2               Stage 3              Stage 4
```

All stages dispatch as sub-agents. Data passes between stages via JSON files. Stage 3 dispatches parallel agents — one per entity.

## Partial Modes

| Mode | Builds | Good for |
|------|--------|----------|
| Blocks only | Stage 1 | Semantic search |
| Blocks + Graph | Stage 1-2 | Search + relationship navigation |
| Blocks + Wiki | Stage 1-3 | Knowledge browsing |
| Blocks + QA | Stage 1-2 + QA | RAG Q&A without wiki |
| All four | Full pipeline | Complete knowledge platform |

## Domain Configuration

Domain configs live in `architecting-knowledge-forms/domains/`. To add a new domain:

1. Copy `domains/generic.yaml` to `domains/your-domain.yaml`
2. Set `domain.applies_to` to match your document type keywords
3. Customize entity types, relation predicates, wiki skeleton, and QA templates

The orchestrator auto-detects the domain by matching user input against `domain.applies_to`.

## Output Structure

```
pipeline-output/
├── blocks/              # Stage 1 — one .json per knowledge block
├── entities.json        # Stage 2 — entity catalog with relations
├── wiki/                # Stage 3 — one .md per entity
└── qa_pairs.json        # Stage 4 — Q+A pairs
```

## Example

See [architecting-knowledge-forms/examples/](architecting-knowledge-forms/examples/) for a worked example using real Tianshui housing fund policy documents.

## Install

```bash
cp -r architecting-knowledge-forms ~/.claude/skills/
```
