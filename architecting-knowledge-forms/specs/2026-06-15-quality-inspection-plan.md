# 知识管线质量检查与反馈回环 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为四阶段知识管线（Block → Entity → Wiki → QA）增加系统性质量检查与反馈回环，将"线性验证"升级为"检查→反馈→重做→再检"的闭环。

**Architecture:** 编排器在每阶段执行后调用质量检查器（机械检查用脚本、语义检查派发子 Agent），输出结构化质量报告。不通过时生成 `## Quality Feedback` 指令追加到子 Agent prompt 并触发重试（最多 3 次）。3 次仍不通过则标记 `human_review_required`，写入隔离目录，管线继续。

**Tech Stack:** Markdown prompt 模板, YAML schema, Shell/Python 编排器脚本

---

## 文件改动清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `schemas/quality-report.schema.yaml` | 创建 | 质量报告输出契约 |
| `prompts/quality-checks.md` | 创建 | 语义质量检查子 Agent prompt |
| `SKILL.md` | 修改 | 替换"Between Stages: Validate Output"为完整质量检查+反馈回环 |
| `prompts/block-extraction.md` | 修改 | 追加 `## Quality Feedback` 重试接收块 |
| `prompts/entity-extraction.md` | 修改 | 追加 `## Quality Feedback` 重试接收块 |
| `prompts/wiki-compilation.md` | 修改 | 追加 `## Quality Feedback` 重试接收块 |
| `prompts/qa-generation.md` | 修改 | 追加 `## Quality Feedback` 重试接收块 |

---

### Task 1: 创建质量报告 Schema

**Files:**
- Create: `schemas/quality-report.schema.yaml`

- [ ] **Step 1: 写 schema 文件**

```yaml
# 质量报告 — 输出契约
# 由质量检查器生成，用于向编排器报告阶段输出质量

quality_report:
  description: "单阶段质量检查的完整报告"
  type: object
  required:
    - report_id
    - stage
    - status
    - retry_count
    - timestamp
    - summary
    - checks
  properties:
    report_id:
      type: string
      description: "格式：{stage}-{retry_count}-{YYYYMMDDHHmmss}"
    stage:
      type: integer
      enum: [1, 2, 3, 4]
    status:
      type: string
      enum: ["passed", "need_retry", "human_review_required"]
    retry_count:
      type: integer
      minimum: 0
      maximum: 3
    timestamp:
      type: string
      format: date-time
    summary:
      type: object
      required: [total_count, passed_count, failed_count, avg_confidence]
      properties:
        total_count:
          type: integer
          description: "该阶段输出总数"
        passed_count:
          type: integer
          description: "通过检查项数"
        failed_count:
          type: integer
          description: "未通过检查项数"
        avg_confidence:
          type: number
          minimum: 0
          maximum: 1
    checks:
      type: array
      description: "逐项检查结果"
      items:
        type: object
        required:
          - check_name
          - layer
          - severity
          - passed
        properties:
          check_name:
            type: string
            description: "对应质量检查标准中的检查项名称"
          layer:
            type: string
            enum: ["relation", "semantic"]
          severity:
            type: string
            enum: ["error", "warning", "info"]
          passed:
            type: boolean
          details:
            type: string
            description: "检查结论描述"
          affected_items:
            type: array
            items:
              type: string
            description: "受影响的文件/实体/QA 列表"
          threshold:
            type: object
            description: "阈值信息（仅数值类检查）"
            properties:
              actual:
                type: number
              expected:
                type: number
    feedback:
      type: object
      description: "仅在 need_retry 时存在：可注入的修复指令"
      required: [instruction_blocks]
      properties:
        instruction_blocks:
          type: array
          items:
            type: object
            properties:
              severity:
                type: string
                enum: ["error", "warning"]
              check:
                type: string
                description: "对应的 check_name"
              affected:
                type: array
                items:
                  type: string
                description: "受影响的项列表"
              instruction:
                type: string
                description: "可执行的具体修复指令"
    output_path:
      type: string
      description: "被检查的输出文件路径"
    human_review_path:
      type: string
      description: "仅在 human_review_required 时存在：输出隔离路径"
```

- [ ] **Step 2: 确认文件写入**

```bash
cat schemas/quality-report.schema.yaml | head -5
# 预期输出：YAML schema 头部
```

- [ ] **Step 3: Commit**

```bash
git add schemas/quality-report.schema.yaml
git commit -m "feat(schema): add quality report schema for pipeline quality inspection
- 定义报告结构：summary、checks、feedback 块
- 支持 passed / need_retry / human_review_required 三种状态
- 为每个 check 提供层（relation/semantic）、严重级别、影响项

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: 创建语义质量检查 prompt

**Files:**
- Create: `prompts/quality-checks.md`

- [ ] **Step 1: 写质量检查 prompt 模板**

```markdown
# Quality Check: Semantic Evaluation

## Role
You are a quality evaluation agent. Read the output of a pipeline stage and evaluate it against a set of quality criteria. Produce a structured quality report.

## Input
Orchestrator provides:
1. **Stage number** — which stage this is (1=block, 2=entity, 3=wiki, 4=QA)
2. **Output directory** — where the stage output files are
3. **Domain config** — entity types, relation predicates, wiki skeleton, QA templates
4. **Pre-check results** — results from mechanical checks already performed by the orchestrator (counting, naming validation, relation density stats)

## Evaluation Criteria Per Stage

### Stage 1: Block Evaluation

| Check | Layer | What to Look For |
|-------|-------|------------------|
| 内容自包含 | semantic | Pick 5-10 random blocks. Does each block make sense without reading adjacent blocks? |
| 分块粒度 | semantic | Does any block contain two distinctly different topics? Is any block extremely short (<80 tokens) or extremely long (>2000 tokens)? |
| 摘要准确性 | semantic | For each sampled block, does summary accurately reflect content without adding/omitting key info? |
| 标签可信度 | relation | Do the tags[] match what the content is actually about? |

### Stage 2: Entity Evaluation

| Check | Layer | What to Look For |
|-------|-------|------------------|
| 实体类型争议 | semantic | Do any entities with the same ID have conflicting types across different blocks? |
| 实体定义模糊 | semantic | Review entities with low confidence (<0.5). Does their context_snippet actually define the entity? |
| 同义合并 | semantic | Do any two entities appear to be the same concept with different names? |
| 跨界实体 | semantic | Do any entities have a type that contradicts their relation patterns? (e.g. type=material but all relations are part_of policy) |
| 命名合规 | relation | Do all entities IDs in entities.json follow the ent_ChineseDescriptiveName rule? |
| 时间/属性降级 | semantic | Are any temporal modifiers, pure numeric values, or single-mention nouns being treated as independent entities? |
| 粒度一致性 | semantic | Are all entities at roughly the same abstraction level? Check if scenario-level examples are extracted as sibling entities of their parent clause. |

### Stage 3: Wiki Evaluation

| Check | Layer | What to Look For |
|-------|-------|------------------|
| 骨架完整性 | semantic | For 5 random wiki pages, check if domain config's wiki_skeleton sections all have substantive content |
| 源可追溯 | semantic | For 3 random claims in each sampled wiki page, trace to the source block |
| 内部链接 | relation | Check that all `[[ent_xxx]]` links reference entities that exist in entities.json |
| 信息退化 | semantic | Compare wiki content against source blocks — has important information been lost? |
| 不自相矛盾 | semantic | Do different sections of the same wiki page contradict each other? |

### Stage 4: QA Evaluation

| Check | Layer | What to Look For |
|-------|-------|------------------|
| 追源验证 | semantic | For each QA pair, can the answer be traced to a specific section in the source wiki? |
| 模板覆盖率 | relation | Check against domain config qa_templates — are all patterns covered? |
| 问句多样性 | semantic | For entities with 3+ QA pairs, are the questions phrased differently? |
| 自洽性 | semantic | For the same entity, do different QA pairs give consistent answers? |
| 往返测试 | semantic | Pick 5 QA pairs: cover the answer and ask "what question does this answer?" Does the result match the original question? |

## Output

Write a quality report matching `schemas/quality-report.schema.yaml` to the specified output path.

**Key rules:**
- Every check must have a `severity`: error (blocks pipeline), warning (recommend improvement), info (observation only)
- `affected_items` must list concrete file/entity names, never generic descriptions
- `feedback.instruction_blocks` must contain actionable instructions, not vague requests
- Be strict on semantic checks: if uncertain, set `confidence: 0.5` on the check and flag it
- If all checks pass, set `status: "passed"`
- If any error-level check fails, set `status: "need_retry"` and include `feedback.instruction_blocks`
```

- [ ] **Step 2: Confirm file written**

```bash
head -20 prompts/quality-checks.md
```

- [ ] **Step 3: Commit**

```bash
git add prompts/quality-checks.md
git commit -m "feat(prompt): add semantic quality check prompt for pipeline stages
- 四阶段语义检查标准（自包含、实体粒度、Wiki 骨架、QA 追源等）
- 每个 check 明确层（relation/semantic）和严重级别
- 输出对接 quality-report.schema.yaml

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: 修改 SKILL.md — 替换阶段间验证为完整质量检查 + 反馈回环

**Files:**
- Modify: `SKILL.md`

- [ ] **Step 1: 定位现有 "Between Stages: Validate Output" 章节**

```markdown
当前从 "### Between Stages: Validate Output" 到 "### Cascade Update" 的部分需要替换。
```

- [ ] **Step 2: 替换为质量检查 + 反馈回环描述**

保留以下现有逻辑并整合升级：
- 计数检查 → 保留为快速预检
- 抽样 → 升级为语义检查派发
- Confidence scan → 整合到重试逻辑
- 关系密度检查 → 保留为机械预检

```markdown
### 阶段间质量检查与反馈回环

本管线采用"检查→反馈→重做→再检"的闭环质量机制。每阶段输出后，编排器执行以下流程：

#### 第 1 步：机械预检（编排器直接执行）

编排器用脚本/命令行对输出执行机械性质检：

1. **计数。** 输出文件数是否为 0？是则停止并报错。
2. **实体 ID 命名合规（仅 Stage 2）。** 扫描所有 entity ID，`ent_` 后首个词是否为中文？若 >20% 不合规，标记并重做。
3. **孤立实体率（仅 Stage 2）。** 无关系的实体占比 >15%？标记并重做。
4. **关系多样性（仅 Stage 2）。** 某类谓词占比 >60%（如 references）？标记并重做。
5. **关系密度（仅 Stage 2）。** 平均关系数 >10 或总数 > 实体数 ×5？标记并询问是否提高共现阈值。
6. **置信度扫描。** 若 >20% 输出 confidence < 0.5，标记低质。
7. **骨架完整性预检（仅 Stage 3）。** Wiki 文件数是否为 0？

预检生成部分填写的质量报告（机械检查项目有结论，语义检查项目待填充）。

#### 第 2 步：语义质量检查（派发子 Agent）

若机械预检无致命问题，编排器派发 1 个子 Agent 运行 `prompts/quality-checks.md`，对该阶段输出进行语义层面评估。

子 Agent 读取阶段输出 + 领域配置，按质量检查标准逐项评估，输出完整质量报告到 `pipeline-output/quality-reports/{stage}-{retry_count}-{timestamp}.json`。

#### 第 3 步：判断与路由

编排器读取质量报告：

- **`status: "passed"`** → 进入下一阶段
- **`status: "need_retry"`** → 进入反馈回环
- **`status: "human_review_required"`** → 写入隔离目录，继续下游

#### 反馈回环

```
retry_count = 0
检查不通过（need_retry）→
  retry_count += 1
  if retry_count > 3:
    标记 human_review_required
    输出写入 pipeline-output/human-review/
    继续下一阶段
  else:
    从质量报告提取 feedback.instruction_blocks
    追加为子 Agent prompt 的 "## Quality Feedback" 章节
    用该 prompt 重新派发同一阶段
    重做完成后 → 再次进行质量检查
```

**反馈注入示例：**

在子 Agent 的 prompt 末尾追加：

```markdown
## Quality Feedback

该阶段的前一次输出经质量检查发现以下问题，请修复：

### error: 实体命名不合规

- 影响项：ent_clause_article_1, ent_policy_notice_46
- 修复指令：将上述实体 ID 从英文/数字前缀改为中文描述名。
  ent_clause_article_1 → ent_规范改进提取政策
  ent_policy_notice_46 → ent_123号通知（使用实际文件名称）

### error: 时间修饰语降级

- 影响项：ent_2020年度, ent_2021年度
- 修复指令：这两个实体是其他实体的时间属性，不应独立存在。
  将其从实体列表移除，改为对应实体的 properties（如 effective_year）

### warning: 孤立实体率 21.8%（阈值 15%）

- 修复指令：审查无关系的 31 个实体，对低频且无关联的实体进行合并或过滤。
```

#### 第 4 步：质量报告留存

每阶段每次执行（含重试）均生成一份完整质量报告，写入：
`pipeline-output/quality-reports/{stage}-{retry_count}-{timestamp}.json`

#### 关于 human_review_required

经过 3 次重试仍不通过的输出，不会阻塞管线。管线将该输出写入 `pipeline-output/human-review/` 目录并继续下游执行。标记的输出供人工后续集中审阅。此举确保不因某实体的质量问题阻塞整个知识库的生产。

#### 与断点恢复的关系

质量检查 + 反馈回环不改变断点恢复逻辑。若某阶段输出存在且质量报告标记为 "passed"，则视为有效，跳过该阶段。若输出存在但质量报告标记为 "need_retry" 或 "human_review_required"，则在恢复时重新执行该阶段。
```

- [ ] **Step 3: 从 SKILL.md 删除旧的 "Between Stages: Validate Output" 章节**

替换范围：从 `### Between Stages: Validate Output` 到 `### Cascade Update` 之间，插入新的质量检查 + 级联更新章节。

保持 "### Cascade Update (Incremental Re-run)" 不变。

- [ ] **Step 4: 在 SKILL.md "Pipeline Resumption" 表格中增加质量报告检查**

在 Per-stage resumption logic 表格中：

| Stage | Output to check | Action if valid |
|-------|----------------|-----------------|
| 各阶段 | `pipeline-output/quality-reports/{stage}-*.json` 存在且 status=passed | 跳过该阶段 |

- [ ] **Step 5: Commit**

```bash
git add SKILL.md
git commit -m "feat(skill): replace linear validation with quality inspection + feedback loop
- 引入机械预检 + 语义检查双层次质量评估
- 实现 feedback redo loop（最多 3 次重试，之后 human_review_required）
- 增加 human_review_required 隔离输出机制
- 质量报告留存至 pipeline-output/quality-reports/

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: 修改各阶段 prompt — 追加 `## Quality Feedback` 接收块

**Files:**
- Modify: `prompts/block-extraction.md`
- Modify: `prompts/entity-extraction.md`
- Modify: `prompts/wiki-compilation.md`
- Modify: `prompts/qa-generation.md`

- [ ] **Step 1: 在 `prompts/block-extraction.md` 末尾追加**

```markdown
## Quality Feedback

当该阶段被重试时，编排器将在本节注入前次输出的质量检查结果。请仔细阅读反馈内容并针对性修复。

如果本节为空，则说明这是首次执行，无需处理反馈。
```

- [ ] **Step 2: 在 `prompts/entity-extraction.md` 末尾追加**

```markdown
## Quality Feedback

当该阶段被重试时，编排器将在本节注入前次输出的质量检查结果。请仔细阅读反馈内容并针对性修复。

如果本节为空，则说明这是首次执行，无需处理反馈。

**处理反馈时请遵循以下原则：**
1. 保持原始输入不变（blocks 不重新提取）
2. 仅根据反馈指令修改输出
3. 如果反馈指令要求合并实体，确保所有引用该实体的关系也同步更新
4. 如果有矛盾指令（如同一条目同时要求合并和降级），优先处理 error 级别，再处理 warning 级别
```

- [ ] **Step 3: 在 `prompts/wiki-compilation.md` 末尾追加**

```markdown
## Quality Feedback

当该阶段被重试时，编排器将在本节注入前次输出的质量检查结果。请仔细阅读反馈内容并针对性修复。

如果本节为空，则说明这是首次执行，无需处理反馈。
```

- [ ] **Step 4: 在 `prompts/qa-generation.md` 末尾追加**

```markdown
## Quality Feedback

当该阶段被重试时，编排器将在本节注入前次输出的质量检查结果。请仔细阅读反馈内容并针对性修复。

如果本节为空，则说明这是首次执行，无需处理反馈。
```

- [ ] **Step 5: Commit**

```bash
git add prompts/block-extraction.md prompts/entity-extraction.md prompts/wiki-compilation.md prompts/qa-generation.md
git commit -m "feat(prompt): add Quality Feedback retry section to all stage prompts
- 每个 stage prompt 末尾追加 ## Quality Feedback 接收块
- 实体抽取 prompt 增加反馈处理原则（合并时同步关系、优先级排序）
- 首次执行时 feedback 块为空，不影响正常流程

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: 自我审查

- [ ] **Step 1: 逐项核对 spec 覆盖**

对照 `specs/quality-inspection-feedback-loop.md`：

| Spec 要求 | 对应 Task | 覆盖？ |
|-----------|-----------|--------|
| 四阶段检查标准（Block） | Task 2 (prompts/quality-checks.md) | ✅ |
| 四阶段检查标准（Entity） | Task 2 + Task 4 | ✅ |
| 四阶段检查标准（Wiki） | Task 2 | ✅ |
| 四阶段检查标准（QA） | Task 2 | ✅ |
| 机械检查 | Task 3 (SKILL.md 编排器描述) | ✅ |
| 语义检查 | Task 2 (子 Agent prompt) | ✅ |
| 修复指令格式 | Task 1 (schema) | ✅ |
| 反馈注入方式 | Task 4 + Task 3 | ✅ |
| 重试边界（3 次→human_review） | Task 3 | ✅ |
| 质量报告留存 | Task 3 | ✅ |
| 报告频率（每次） | Task 3 | ✅ |
| human_review_required 隔离路径 | Task 3 | ✅ |

- [ ] **Step 2: 占位符扫描**

搜索：TBD、TODO、"implement later"、"add appropriate" → 应无发现。

- [ ] **Step 3: 命名一致性检查**

- `quality_report.schema.yaml` — Task 1 创建
- `quality-checks.md` — Task 2 创建
- `pipeline-output/quality-reports/` — Task 3 中引用
- `pipeline-output/human-review/` — Task 3 中引用
- `## Quality Feedback` — Task 4 中各 prompt 追加
- 所有引用一致 ✅
