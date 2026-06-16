---
name: architecting-knowledge-forms
description: Designing and executing multi-form knowledge pipelines — blocks, graph, wiki, QA pairs. Domain configs, prompt templates, 4-stage sub-agent orchestration. 设计和执行多形态知识管线：知识块、图谱、Wiki、QA 对。含领域配置、prompt 模板、四阶段子 Agent 编排。
version: 2.7.0
tags: [knowledge-management, rag, architecture, data-modeling, pipeline]
author: leislicai
---

# Architecting Knowledge Forms — 知识形态架构

> 首次使用？请先阅读 [GETTING_STARTED.md](GETTING_STARTED.md) 快速上手指引。

## 概述

**知识块（Knowledge Block）是唯一写入目标；图（Graph）、Wiki、QA 对都是从它派生出来的——各自有不同的更新特性。** 本 Skill 既提供了设计此类系统的架构原则，也提供了将文档依次处理完四个阶段的执行管线。

## 平台适配

本 Skill 是**编排器无关的**（派发管线可在任何支持子 Agent 的平台上运行）。**语言说明：** 实体命名约定和领域配置假定源文档为中文。编排模式本身可复用到其他语言——创建一个翻译后的领域配置并更新 `prompts/block-extraction.md` 中的实体 ID 规则即可。

| 概念 | Claude Code | Codex | 本 Skill 通用术语 |
|---------|------------|-------|--------------------------------|
| 加载 skill | `Skill` 工具 | `skill` 工具 | "加载该 skill" |
| 派发子 Agent | `Agent` 工具 | `task` 工具 | "派发子 Agent" |
| 读写文件 | `Read` / `Write` | `read` / `write` | "读取/写入文件" |

**平台无关部分（无需修改）：**
- `prompts/*.md` — 子 Agent 指令（"你是一个……Agent"）
- `schemas/*.yaml` — 输出契约
- `domains/*.yaml` — 领域配置
- 管线逻辑 — READ→SUBSTITUTE→DISPATCH、质量检查、级联更新、错误处理、断点恢复

**需要平台特定适配的部分：**
只有每个阶段的 `DISPATCH` 步骤——将"派发子 Agent"翻译为你平台的子 Agent API。技能其余部分在所有平台上读取方式相同。

## 何时使用

**适用场景：**
- 设计知识系统的数据模型
- 将文档通过多阶段知识管线加工处理
- 决定分块（chunk）/ 图（graph）/ Wiki / QA 之间的关系
- 评估独立存储 vs 统一架构的取舍

**不适用场景：**
- 构建简单的 FAQ 机器人（只需 blocks + QA，跳过 graph 和 wiki）
- 纯文档搜索（blocks + 向量索引，不需要其他形态）
- 已有可用的单存储架构（不要过度设计）

## 核心模式

### 四种知识形态

| 形态 | 角色 | 更新方式 |
|------|------|--------|
| **知识块（Knowledge Block）** | 原子级、带源追溯的知识单元 | **写入目标**（不可变） |
| **知识图谱（Knowledge Graph）** | 实体-关系索引 | 从 blocks.entities[] 近实时派生 |
| **Wiki** | 策划型实体页面，编译产出 | 在 block 更新时触发（延迟构建步骤） |
| **QA 对** | 锚定源文档的问答对 | Wiki 完成后（两步派生） |

### 编译管线

```
文档 → [分块] → 知识块（唯一写入目标）
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
   Stage 2:        Stage 3:       Stage 4:
   实体提取         Wiki 编译      QA 生成
   (blocks.        (blocks GROUP  (从 Wiki
   entities[]      BY entity →    页面 →
   → entities      sections       问答对)
   + relations)    per entity)
```

### 核心规则

1. **一个写入目标。** Block 是唯一的写入目标。图、Wiki、QA 通过受控的管线步骤派生，不是独立的写路径。
2. **实体粒度一致。** Block 的实体标签、图节点、Wiki 页面共享一套实体粒度。
3. **Wiki 是编译的，不是渲染的。** 构建步骤由 block 更新触发——保留策划结构。增量编译；永远不要从图查询动态渲染。
4. **QA 对从 Wiki 派生。** Wiki 提供策划上下文——精度更高、噪声更少。没有 Wiki 时，从 blocks 派生并明确接受质量折衷。
5. **Block 质量门控下游视图。** 内容非空。源追溯有效。Entities[] 可解析。一个损坏的 block 会污染所有下游视图——在写入时验证。

### 部分形态组合

| 子集 | 用途 | 首次构建 |
|--------|----------|-------------|
| 仅 Blocks | 语义搜索 | 块提取 |
| Blocks + Graph | 搜索 + 关系导航 | + 实体提取 |
| Blocks + Wiki | 知识浏览 | + 编译 |
| Blocks + QA | RAG 问答 | + QA 生成 |
| 全部四种 | 完整知识平台 | 完整管线 |

约束：**如果有 >1 种形态，通过从 blocks 派生来同步，绝不要在各视图之间做 ETL。**

## 管线执行

### 编排工作原理

子 Agent 在隔离上下文中运行——除非平台明确支持，否则它们无法读取编排器文件系统中的文件。为了跨平台安全工作，编排器必须遵循 **READ → SUBSTITUTE → DISPATCH**：

1. **READ** — 读取 prompt 模板和任何输入数据文件
2. **SUBSTITUTE** — 将所有 `{variable}` 占位符替换为实际内容（内联，非引用）
3. **DISPATCH** — 将完全解析后的 prompt 字符串作为子 Agent 任务派发

绝不向子 Agent 传递文件路径。始终内联内容。

### 脚本使用策略

编排器和子 Agent 有不同的脚本使用规则：

| 角色 | 是否允许脚本？ | 原因 | 示例 |
|------|-----------------|--------|---------|
| **编排器** | ✅ 用于机械任务 | 确定性、可逆、不影响内容质量 | 文件重命名、计数、排序、字段校验、规范化 |
| **子 Agent** | ❌ 不可用于内容工作 | 质量自查必须逐 block 进行。脚本批量处理会跳过验证。 | 块提取、实体提取、Wiki 编译、QA 生成 |

**原因：** 编排器用一行 Python 重命名 259 个文件是可靠的。子 Agent 用一个 Python 脚本提取 200 个 block 会跳过逐 block 的质量自查——这是本 Skill 的主要质量门控。prompt 模板中的 "Do NOT write Python scripts" 规则针对的是内容提取，不是机械性的文件操作。

### 第 0 步：收集上下文

依次询问用户：

1. **领域是什么？**（例如"公积金"、"医保"、"法律"或"通用"）
2. **需要哪些形态？** 默认：全部四种。用户可限制范围："处理到 graph 就停"或"只要 blocks + QA"。
3. **源文档在哪里？** 一个目录路径或文件列表。
4. **管线输出写到哪里？** 默认：当前工作目录下的 `./pipeline-output`。用户可指定任意路径。

然后解析领域配置：

```
1. ls domains/ 列出可用配置
2. 逐一读取 .yaml 文件，检查 domain.applies_to 是否匹配
3. 匹配到 → 使用该配置
4. 未匹配到 → 使用 domains/generic.yaml
5. 对未识别的领域，询问是否保存为新领域配置
```

在用户指定的路径创建输出目录：

```bash
mkdir -p {output_dir}/blocks {output_dir}/wiki
```

所有后续管线步骤中的路径均使用 `{output_dir}` 变量，编排器在执行时将其替换为用户指定的输出目录。下文为便于阅读，展示的是以默认目录为例的路径——实际执行时一律替换为 `{output_dir}`。

### 第 1 步：Stage 1 — 块提取（按文档、并行、隔离）

多个并行 Agent 写入同一共享目录会导致 ID 冲突。每个 Agent 写入一个临时子目录；所有 Agent 完成后由编排器统一规范化。

```
1. LIST 用户文档目录中的源文件
2. READ prompts/block-extraction.md
3. READ 匹配的领域配置 .yaml
4. 对每份源文档：
   a. 分配简短 doc_id（文件名净化后，如"公积金管理条例"）
   b. 在 prompt 模板中替换：
      - {document_path} → 该文档的路径
      - {output_dir} → {user_output_dir}/blocks/temp/{doc_id}/
      - {domain_config} → 完整领域配置 YAML（内联）
   c. DISPATCH 1 个子 Agent 处理该文档
5. 同时派发最多 8 个 Agent。等待全部完成。
6. 所有 Agent 完成后，逐文档验证再合并：
   a. 对每个 temp/{doc_id}/ 子目录，逐一验证其中所有 .json 文件可被 json.load() 解析
   b. 验证通过的文件 → 重新编号为 kb_001.json……顺序写入 {output_dir}/blocks/
   c. 验证失败的文件 → 该文档的所有块都不合并，记录失败的 doc_id
   d. 如果有文档验证失败 → 不删除 temp 目录，进入部分重试
   e. 如果全部通过 → 删除 temp 目录，运行机械预检
```

#### 部分重试（仅重试失败的文档）

```
如果某文档产出了坏 JSON：
  1. 保留 temp/{失败doc_id}/ 目录（不删除）
  2. 将坏 JSON 的文件名列表注入 Quality Feedback
  3. 仅对该文档重新派发 Agent（prompt 末尾追加 Quality Feedback）
  4. 重新验证 → 通过则合并该文档的块（延续当前编号）→ 删除 temp
  5. 重试最多 3 次，仍失败则跳过该文档，记录到 human-review/
```

这确保一个文档的 JSON 格式问题不会导致整批重跑，也不会被静默丢弃。

**断点恢复检查：** 如果 `{output_dir}/blocks/` 中已存在通过质量检查的 .json 文件，询问用户："已发现已有 block。全部重新提取，还是只重新提取变更的文档？"如选择仅变更文档，对比源文件时间戳和 block 时间戳，只对新增/修改的文件派发 Agent。

### 第 2 步：Stage 2 — 实体提取

```
1. 等待 Stage 1 完成
2. READ prompts/entity-extraction.md
3. READ 领域配置 .yaml
4. LIST {output_dir}/blocks/ 确认 block 存在
5. 在 prompt 模板中替换：
   - {domain_config} → 完整领域配置 YAML（内联）
6. DISPATCH 1 个子 Agent 处理解析后的 prompt
```

子 Agent 读取所有 blocks（编排器在 prompt 中内联 block 数量），使用旧→新 ID 映射规范化实体，并从实体共现模式（≥3 个共享 block）中提取关系。输出 `{output_dir}/entities.json`，遵循 [schemas/entities.schema.yaml](schemas/entities.schema.yaml)。

**关系质量门控：** Stage 2 输出 MUST 有 ≥50% 的实体拥有至少一条关系。否则质量检查会标记该问题，编排器询问是重新提取还是接受稀疏关系继续。

### 第 3 步：Stage 3 — Wiki 编译（按优先级、并行）

大型实体目录（50+ 实体）全量并行编译成本过高。按重要度排序：

```
1. 等待 Stage 2 完成
2. READ {output_dir}/entities.json 提取实体列表
3. 按重要度评分排序：
   score = number_of_source_block_ids + number_of_relations + (1.5 if type is 'policy' else 0)
   降序排列。顶部实体是被引用最多、关联度最高的政策实体。
4. 询问用户："共 N 个实体。按重要度排名前 M 的是 [列表]。编译全部 N 个，还是仅前 M 个？"
   默认值：仅编译 policy + clause 类实体（通常覆盖 80%+ 的知识价值）。
5. READ prompts/wiki-compilation.md
6. READ 领域配置 .yaml
7. 对每个选中的实体：
   a. 在 {output_dir}/blocks/ 中筛选 entities[] 包含该 entity_id 的 blocks
   a2. 如筛选出的 blocks 的总 token 数超过 60,000：
       - 优先选择 quality.confidence 最高的 blocks
       - 优先包含 tags 匹配 Wiki 骨架章节键的 blocks
       - 对被省略的 block 汇总为："[因上下文限制，省略 N 个附加 block]"
   b. 在 prompt 模板中替换：
      - {entity_id} → 实体的 id
      - {entity_data} → 该实体在 entities.json 中的条目（内联）
      - {relevant_blocks} → 筛选后的 blocks 内容 + 汇总说明（内联，非文件路径）
      - {domain_config} → 完整领域配置 YAML（内联）
   c. DISPATCH 每个实体 1 个子 Agent（并行派发——各自写入不同文件）
8. 所有 Agent 完成后，逐实体验证再计为完成：
   a. 对每个 `{output_dir}/wiki/{entity_id}.md`，验证其 YAML frontmatter 可解析且含必填字段（entity_id/title/version/status/compiled_at）
   b. 验证通过 → 保留
   c. 验证失败 → 该实体的 .md 标记为失败，不删除
   d. 如果有实体失败 → 进入部分重试
   e. 全部通过 → 运行机械预检
```

#### 部分重试（仅重试失败的实体）

```
如果某实体的 Wiki 页面验证失败：
  1. 保留失败的 .md 文件路径
  2. 将 frontmatter 错误详情注入 Quality Feedback
  3. 仅对该实体重新派发 Agent
  4. 重新验证 → 通过则保留 → 运行机械预检
  5. 重试最多 3 次，仍失败则标记 human-review/ 并继续下游
```

每个子 Agent 写入 `{output_dir}/wiki/{entity_id}.md`，遵循 [schemas/wiki.schema.yaml](schemas/wiki.schema.yaml)。

### 第 4 步：Stage 4 — QA 生成

```
1. 等待所有 Stage 3 的 Agent 完成
2. READ prompts/qa-generation.md
3. READ 领域配置 .yaml
4. 在 prompt 模板中替换：
   - {domain_config} → 完整领域配置 YAML（内联，尤其是 qa_templates）
5. DISPATCH 1 个子 Agent 处理解析后的 prompt
```

子 Agent 读取 `{output_dir}/wiki/` 和 `{output_dir}/entities.json`，输出 `{output_dir}/qa_pairs.json`，遵循 [schemas/qa.schema.yaml](schemas/qa.schema.yaml)。

### 阶段间质量检查与反馈回环

> **硬约束：质量检查不可跳过。** 每个 Stage 完成后必须依次执行机械预检和语义评估，质量报告 status=passed 是进入下一阶段的唯一通行条件。缺少质量报告 = 编排器执行违规。

**各阶段兜底机制速查：**

| 阶段 | 并行粒度 | 失败范围 | 兜底策略 |
|------|---------|---------|---------|
| Stage 1 | 按文档 | 某文档的 JSON 损坏 | 只重试该文档，最多 3 次；仍失败则跳过并记录 human-review/ |
| Stage 2 | 单 Agent | 整体输出有问题 | 追加 Quality Feedback 重跑，最多 3 次 |
| Stage 3 | 按实体 | 某实体的 Wiki 验证失败 | 只重试该实体，最多 3 次；仍失败则标记 human-review/ 继续下游 |
| Stage 4 | 单 Agent | 整体输出有问题 | 追加 Quality Feedback 重跑，最多 3 次 |

每阶段输出后，编排器执行以下流程：

#### 第 1 步：机械预检（必须先执行）

编排器运行可执行脚本，不允许手动替代：

```bash
python3 scripts/mechanical-check.py <stage> {output_dir} --domain domains/gov-services.yaml
```

该脚本自动执行：
- 计数验证、置信度扫描（全部 Stage）
- Stage 1: 实体格式一致性、实体命名合规
- Stage 2: 孤立实体率、关系多样性、关系密度、命名合规
- Stage 3: 骨架完整性、Frontmatter 字段检查
- Stage 4: 追源率

脚本输出 JSON 质量报告到 `{output_dir}/quality-reports/`，退出码 0=通过、1=需重做。

**编排器读取脚本输出的报告后：**
- 报告含 error → 进入反馈回环（第 3 步）
- 报告无 error → 进入语义检查（第 2 步）

#### 第 2 步：语义质量检查（必须派发）

**此步不可跳过。** 即使机械预检全部通过，仍需派发子 Agent 进行语义评估。

编排器读取 `prompts/quality-checks.md`，将 `{domain_config}` 内联，派发子 Agent。子 Agent 读取阶段输出，按质量检查标准逐项评估，输出完整质量报告（含语义检查结论）。

合并机械预检报告 + 语义检查结论 → 最终质量报告。

#### 第 3 步：判断与路由

编排器读取最终质量报告的 `status` 字段：

- **`"passed"`** → 进入下一阶段
- **`"need_retry"`** → 进入反馈回环
- **`"human_review_required"`** → 写入 `{output_dir}/human-review/`，继续下游

**门控规则：** `{output_dir}/quality-reports/` 中不存在对应阶段且 status=passed 的报告时，编排器不得进入下一阶段。

#### DB 导出

质量报告 `status=passed` 后，编排器立即运行机械性 DB 格式导出脚本：

```bash
python3 scripts/export-db-formats.py <N> {output_dir}
```

`<N>` 为当前阶段编号（1/2/3/4），产出的 DB 文件写入 `{output_dir}/db/`：

| 阶段 | 产物 |
|------|------|
| Stage 1 | `blocks.jsonl`、`blocks.csv`、`blocks.sql` |
| Stage 2 | `entities.jsonl`、`entities.csv`、`relations.csv`、`entities.cypher` |
| Stage 3 | `wiki.jsonl`、`wiki.csv` |
| Stage 4 | `qa_pairs.jsonl`、`qa_pairs.csv`、`qa_pairs.sql` |

**格式说明：** JSONL 用于 NoSQL / 数据湖；CSV 用于通用导入（Excel / pandas / PostgreSQL COPY）；SQL 为 PostgreSQL DDL + INSERT；Cypher 为 Neo4j 图数据库脚本。导出为纯机械转换，不涉及子 Agent，不改变管线数据模型。

#### 反馈回环

```
retry_count 从 0 开始
检查不通过（need_retry）→
  retry_count += 1
  if retry_count > 3:
    标记 human_review_required
    输出写入 {output_dir}/human-review/
    继续下一阶段
  else:
    从质量报告提取 feedback.instruction_blocks
    追加为子 Agent prompt 的 "## Quality Feedback" 章节
    用该 prompt 重新派发同一阶段
    重做完成后 → 再次进行质量检查（从第 1 步重新开始）
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
  ent_policy_notice_46 → ent_123号通知（以实际名称为准）

### error: 时间修饰语降级

- 影响项：ent_2020年度, ent_2021年度
- 修复指令：这两个实体是其他实体的时间属性，不应独立存在。
  将其从实体列表移除，改为对应实体的 properties（如 effective_year）

### warning: 孤立实体率 21.8%（阈值 15%）

- 修复指令：审查无关系的 31 个实体，对低频且无关联的实体进行合并或过滤。
```

#### 第 4 步：质量报告留存

每阶段每次执行（含重试）均生成一份完整质量报告，写入：
`{output_dir}/quality-reports/{stage}-{retry_count}-{timestamp}.json`

#### 关于 human_review_required

两种触发路径：1) 质量检查 Agent 判定问题需要人类判断才能解决（判断标准见 `prompts/quality-checks.md`）；2) 同一阶段连续 3 次 need_retry 后仍未通过。

不论哪种路径，标记为 human_review_required 的输出不阻塞管线。管线将该输出写入 `{output_dir}/human-review/` 目录并继续下游执行。标记的输出供人工后续集中审阅。

#### 与断点恢复的关系

质量检查 + 反馈回环不改变断点恢复逻辑。若某阶段输出存在且最后一份质量报告 status 为 "passed"，则视为有效，跳过该阶段。若输出存在但最后一份质量报告 status 为 "human_review_required"，则在恢复时需用户确认是否重新执行。

### 级联更新（增量重跑）

当源文档变更后重新运行管线时，编排器必须检测变更内容，只重新派生受影响的产物：

1. 对比源文档时间戳与 `{output_dir}/blocks/*.json` 时间戳 → 只重新提取变更的文档
2. 对比 `{output_dir}/blocks/` 时间戳与 `{output_dir}/entities.json` 时间戳 → 仅当 blocks 变更时才重新提取实体
3. 对每个 Wiki 页面，对比其 `compilation.compiled_at` 时间戳与引用其实体的 blocks 的时间戳 → 只重新编译过期 Wiki
4. 对每个 QA 对，对比其 `quality.wiki_version` 与当前 Wiki 的 `compilation.version` → 只重新生成过期 QA

**重要：** 编排器必须将过期检测指令内联到各子 Agent 的 prompt 中。子 Agent 不会自动知道哪些数据已过期——编排器通过只传入变更数据来告知它们。

## 错误处理

| 场景 | 处理方式 |
|----------|--------|
| 阶段产生 0 个输出文件 | 停止。报告："阶段 N 未产生任何输出。请检查输入数据。" |
| Stage 1 某文档产出坏 JSON | 部分重试：仅对该文档追加 Quality Feedback 重派 Agent，最多 3 次。仍失败则跳过该文档，记录到 human-review/ |
| 子 Agent 返回空或格式异常的输出 | 用相同 prompt 重试一次。重试仍失败则停止并报告阶段 + 错误详情。 |
| Stage 3 某实体 Wiki 验证失败 | 部分重试：仅对该实体追加 Quality Feedback 重派 Agent，最多 3 次。仍失败则标记 human-review/，继续下游 |
| 子 Agent 超时或失败 | Stage 3 按实体重试失败的实体；Stage 1 按文档重试失败的文档；其他阶段整体重试。最多 3 次。 |
| 领域配置 YAML 解析失败 | 回退到 generic.yaml。警告用户。 |
| >20% 的输出 quality.confidence < 0.5 | 暂停管线。显示警告计数。询问用户：继续、修复后重试、或停止。 |
| 管线中途中断 | 检查 {output_dir}/ 中已有文件。从最后一个完整的、输出通过质量检查的阶段恢复。 |
| 无领域配置匹配用户输入 | 回退到 generic.yaml。询问是否将本次对话规则保存为新领域配置。 |

## 管线断点恢复

每个阶段写入不同的位置。一个阶段如果在"完成"后其输出存在且通过质量检查，则可跳过。管线可以从任意阶段恢复：

```
在每个阶段前检查：
  如果输出存在 且 质量报告 status=passed：
    跳过 → 进入下一阶段
  否则：
    运行本阶段（不是从头重跑——只跑本阶段）
```

示例：Stage 1 通过，Stage 2 失败。修复问题后重新运行——编排器跳过 Stage 1（blocks 存在 + 质量报告 status=passed），从 Stage 2 恢复。

**各阶段恢复逻辑：**

| 阶段 | 检查的输出 | 有效时的行为 |
|-------|----------------|-----------------|
| 1 | `{output_dir}/blocks/*.json` 存在、计数 > 0、且质量报告 status=passed | 跳过块提取 |
| 2 | `{output_dir}/entities.json` 存在、且质量报告 status=passed | 跳过实体提取 |
| 3 | `{output_dir}/wiki/*.md` 存在、计数 > 0、且质量报告 status=passed | 跳过 Wiki 编译。增量模式只编译过期实体。 |
| 4 | `{output_dir}/qa_pairs.json` 存在、且质量报告 status=passed | 跳过 QA 生成 |

**恢复检查是编排器在每个步骤的第一件事。** 必须在读取 prompt 模板或领域配置之前进行。

**Stage 1 特殊处理：** 如果 `{output_dir}/blocks/temp/` 中仍有未清理的子目录，说明上次 Stage 1 有文档失败。恢复时优先对这些文档单独重试（用 Quality Feedback），通过后再合并。

若 Stage 1 某文档重试 3 次仍失败，编排器跳过该文档并记录到 `{output_dir}/human-review/skipped-docs.json`，然后继续合并已通过文档的 blocks 并进入 Stage 2。

## 领域配置

参见 [domains/gov-services.yaml](domains/gov-services.yaml) 了解 gov-services 领域模板。每个领域配置提供：分块策略、实体类型、关系谓词、Wiki 骨架、QA 模板、质量规则。

**动态谓词：** 5 个谓词由领域配置定义，而非硬编码。不同领域可能需要不同的谓词集。Stage 2 会将不符合现有谓词的关系在质量警告中标记为 `new_predicate_suggested`。每次运行后，编排器收集这些建议并询问是否将其加入领域配置——使系统可以跨领域自我改进。

## 数据模型

- [data-model.md](data-model.md) — 四种形态的 schema、交叉引用拓扑、级联模型
- [schemas/](schemas/) — 各阶段输出 schema（子 Agent 必须遵循的契约）

## 反模式

| 反模式 | 失败原因 |
|-------------|--------------|
| N 个独立存储 + ETL | N 倍 ETL 维护成本；粒度漂移；不一致 |
| 图作为主写入目标 | 丢失原子可追溯性；block 退化为纯文本块 |
| Wiki 作为动态图渲染 | 自动更新破坏策划质量 |
| QA 从原始文档生成 | 继承噪声；缺失 Wiki 上下文 |
| 实体粒度不一致 | 图粗块细 → 无法跨形态追溯 |

## 红旗警示

| 常见合理化理由 | 事实 | 应对 |
|----------------|---------|--------|
|"四个数据库通过 ETL 同步就行" | 你是在建 N 个独立存储。 | 指出规则 1（一个写入目标）。要求先重构。 |
|"图就是知识本身" | 图是*关系索引*。 | 指向 data-model.md：block 是写入目标，图是派生视图。 |
|"从原始文档直接生成 QA 更简单" | 生成更简单，质量更差。 | 建议先走 Wiki 派生。如果没建 Wiki，明确接受这个质量折衷。 |
|"Wiki 从图自动更新就行" | 自动更新 = 没有策划。 | 解释编译型 vs 渲染型的区别。提出增量编译作为折衷方案。 |
|"不同数据库中的视图 = 多存储" | 不同的读取引擎是可以的。 | 确认：写路径是否是统一的？如果是，不同引擎没问题。 |
