# Claude Skills / Claude 技能集

Personal Claude Code skills collection. 个人 Claude Code 技能集合。

## Skills / 技能

| Skill | Version | Description / 描述 |
|-------|---------|-------------|
| [`architecting-knowledge-forms`](architecting-knowledge-forms/SKILL.md) | v2.7.0 | 多形态知识管线编排——Block → Entity → Wiki → QA。含领域配置、prompt 模板、schema 契约、质量检查反馈回环。Design + execute multi-form knowledge pipelines with hard-gate quality inspection and feedback loops. |

**语言说明 / Language:** 实体命名和领域配置假定中文源文档。编排模式（临时目录隔离、断点恢复、质量检查、动态谓词）是语言无关的。Entity naming and domain configs assume Chinese-language source documents. The orchestration pattern is language-agnostic.

## Pipeline / 管线

```
Document → [Stage 1: 块提取] → [Stage 2: 实体提取] → [Stage 3: Wiki 编译] → [Stage 4: QA 生成]
                Block                  Entity                  Wiki                   QA
              Extraction             Extraction             Compilation            Generation
```

每阶段完成后强制执行质量检查（机械预检 + 语义评估），不合格则进入反馈回环（最多 3 次重试）。

Each stage is followed by mandatory quality inspection (mechanical pre-check + semantic evaluation). Failed stages enter a feedback loop (max 3 retries).

## Output Structure / 产出结构

```
pipeline-output/
├── blocks/              # Stage 1 — kb_NNN.json
├── entities.json        # Stage 2 — 实体目录 + 关系
├── wiki/                # Stage 3 — ent_xxx.md
├── qa_pairs.json        # Stage 4 — QA 对
├── quality-reports/     # 质量报告（每阶段必生成）
└── human-review/        # 3 次重试后仍不通过，人工审阅
```

## Example Run / 运行示例

天水市住房公积金 3 份核心政策文档，v2.7 管线产出 / 3 core Tianshui housing fund docs, v2.7 pipeline：

| Stage | Output / 产出 | Quality / 质量 |
|-------|------|------|
| 1 — 块提取 | 43 blocks | 全阶段机械检查 passed |
| 2 — 实体提取 | 14 entities + 25 relations | 100% related, 0 英文违规 |
| 3 — Wiki 编译 | 14 wiki pages | 全阶段机械检查 passed |
| 4 — QA 生成 | 28 QA pairs（12 场景，0 常识问题） | 全阶段机械检查 passed |

See [architecting-knowledge-forms/examples/pipeline-output/](architecting-knowledge-forms/examples/pipeline-output/) for full output.

## Quick Start / 快速上手

Read [GETTING_STARTED.md](architecting-knowledge-forms/GETTING_STARTED.md) for a 5-minute walkthrough with good/bad output examples.

阅读 [GETTING_STARTED.md](architecting-knowledge-forms/GETTING_STARTED.md) 获取 5 分钟快速上手指引和好/坏输出对比示例。

## Install / 安装

```bash
cp -r architecting-knowledge-forms ~/.claude/skills/
```
