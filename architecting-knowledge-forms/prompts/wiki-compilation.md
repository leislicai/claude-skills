# Stage 3: Wiki Compilation

## Role
You are a wiki compilation agent. Compile a curated wiki page for a single entity.

## Target Entity
**Entity ID:** `{entity_id}`
**Entity data:** (inlined from entities.json)
```
{entity_data}
```

## Input Data
Knowledge blocks that reference this entity:
```
{relevant_blocks}
```

## Domain Rules
(Inlined from domain config by the orchestrator)
```
{domain_config}
```

Build the wiki page using `wiki_skeleton.sections`. For each section in the skeleton, use the `source` field to determine where content comes from:

- **overview** (source=summary): Aggregate `summary` fields from relevant blocks. Write a concise narrative.
- **standards** (source=properties): Render entity properties as structured data.
- **conditions / materials / procedure** (source=blocks_tagged_with): Filter relevant blocks by `tag` matching the section key. Group by scenario or entity.
- **faq** (source=derived_from_qa): Leave a placeholder — Stage 4 populates this.
- **references** (source=relations): List related entities and their predicates.

## Output
Write a single file: `pipeline-output/wiki/{entity_id}.md`.

Format: Markdown with YAML frontmatter containing `entity_id`, `title`, `related_entities`, `compilation.version`, `compilation.compiled_at`. Body uses the skeleton section names as Markdown headings with compiled content underneath.

Follow the output schema at [schemas/wiki.schema.yaml](../schemas/wiki.schema.yaml).

## Context Budget

If the orchestrator includes a note `[N additional blocks omitted due to context limit]` in {relevant_blocks}:
- Use the inlined blocks as primary sources
- Add `quality.warnings: ["partial_compilation: N blocks omitted"]` to the output
- Prioritize completeness of `standards` and `conditions` sections over `faq`
- The omitted blocks remain at `pipeline-output/blocks/` for future full recompilation

## Compilation Rules
1. **Curate, don't concatenate.** Synthesize narrative from blocks — don't paste raw block content.
2. **Preserve source traces.** Every section carries `source_block_ids` — never lose the link back.
3. **Version tracking.** Set `compilation.version` (increment from previous if recompiling). Set `compilation.status` to `fresh`.
4. **Skip if fresh.** If the entity's source blocks haven't changed since the last `compilation.compiled_at`, write a file with `compilation.status: fresh` (unchanged) and the previous content. This enables incremental updates.

## Quality Self-Check
- [ ] Every section has at least one `source_block_id`
- [ ] Content is synthesized (not raw block concatenation)
- [ ] Entity id matches `{entity_id}`
- [ ] `related_entities` are valid entity ids
- [ ] No empty sections (omit or note "暂无相关信息")

If any check fails, fix before writing.

## Quality Feedback

当该阶段被重试时，编排器将在本节注入前次输出的质量检查结果。请仔细阅读反馈内容并针对性修复。

如果本节为空，则说明这是首次执行，无需处理反馈。
