# Claude Skills

Personal Claude Code skills collection.

## Skills

| Skill | Description |
|-------|-------------|
| [`architecting-knowledge-forms`](architecting-knowledge-forms/SKILL.md) | Design multi-form knowledge systems — blocks, graph, wiki, QA pairs |
| `knowledge-block-extraction` | Stage 1: Extract atomic knowledge blocks from documents |
| `entity-extraction` | Stage 2: Extract entities and relations from blocks |
| `wiki-compilation` | Stage 3: Compile curated wiki pages from entity blocks |
| `qa-generation` | Stage 4: Generate QA pairs from wiki pages |

## Pipeline

```
Document → [Block Extraction] → [Entity Extraction] → [Wiki Compilation] → [QA Generation]
```

Each skill implements one stage. Start with `architecting-knowledge-forms` for architecture decisions, then chain the pipeline skills for implementation.

## Install

```bash
cp -r architecting-knowledge-forms ~/.claude/skills/
cp -r knowledge-block-extraction ~/.claude/skills/
cp -r entity-extraction ~/.claude/skills/
cp -r wiki-compilation ~/.claude/skills/
cp -r qa-generation ~/.claude/skills/
```
