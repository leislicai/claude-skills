# Claude Skills

Personal Claude Code skills collection.

## Skills

| Skill | Version | Description |
|-------|---------|-------------|
| [`architecting-knowledge-forms`](architecting-knowledge-forms/SKILL.md) | v2.0.0 | Design + execute multi-form knowledge systems — domain configs, prompt templates, schema contracts, 4-stage sub-agent pipeline |

## Pipeline

```
Document → [Block Extraction] → [Entity Extraction] → [Wiki Compilation] → [QA Generation]
              Stage 1               Stage 2               Stage 3              Stage 4
```

All stages dispatch as sub-agents. Data passes between stages via JSON files. Stage 3 (wiki) dispatches parallel agents — one per entity.

## Install

```bash
cp -r architecting-knowledge-forms ~/.claude/skills/
```
