# 知识管线质量检查与反馈回环设计

## 概述

当前管线执行方式是"线性推进"：Stage N → 验证 → Stage N+1。验证通过则继续，不通过则停止。本设计将其升级为**"检查→反馈→修改→再检"的闭环**，覆盖全部四个阶段，引入可执行的修复指令和最大重试边界，将质量门控从"校验器"升级为"迭代优化器"。

## 设计原则

1. **反馈必须可执行。** 质量报告不只说"质量差"，而是说"哪几个文件、什么字段、为什么、怎么改"。
2. **每个阶段输出均可独立审查和重做。** 不因某阶段质量问题阻塞整个管线或清空已通过的输出。
3. **有退出条件，无无限循环。** 重试最多3次→标记人工审核→继续下游。
4. **质量检查分两个层面：** 关系层（实体间连接正确性）和语义层（实体本身质量）。

---

## 四阶段质量检查标准

### Stage 1: Block 质量检查

| 检查项 | 层面 | 检测方式 | 不通过触发行为 |
|--------|------|---------|--------------|
| **内容自包含** | 语义 | 检查 block.content 是否在缺失上下文的情况下仍可独立理解（对照源文档原文，评估是否需要前文/后文才能理解） | 标记该块分割点错误，反馈"请在 [block_id] 附近重新调整分割，使每个 block 自包含" |
| **分块粒度** | 语义 | 一个 block 是否包含多个独立主题或条款；内容量是否超过预期范围（如 min_tokens ~ max_tokens 区间） | 要求在该 block 位置重新分割，按主题拆分 |
| **内容完整性** | 语义 | 一个完整表述是否在不该断的位置被截断（如句中截断、条件与结论分离） | 要求与相邻 block 合并 |
| **实体存在性** | 关系 | block.entities[] 中的每个 entity_id 是否确实出现在 block.content 中（逐条校验） | 移除多余的实体 ID；如有缺失则补充 |
| **标签可信度** | 关系 | block.tags[] 是否准确反映 content 的真实主题，与 entity_types 是否协调 | 与实体类型明显冲突的，关联 stage1 重调标注 |
| **源追溯** | 语义 | block.source_trace（文档位置、段落号）是否能精确对应到源文档 | 无法定位的标记，反馈并要求补充精确追溯 |
| **摘要准确性** | 语义 | block.summary 是否准确地概括 block.content 且无额外信息（不增不减） | 提取 summary 含 content 没有的信息时，要求重写；summary 遗漏关键点时，补充 |
| **跨块重叠** | 关系 | 连续的两个 block 之间是否存在大段内容重复（超过一定比例阈值）或核心信息重复 | 去重并调整分界点 |

### Stage 2: 实体质量检查

| 检查项 | 层面 | 检测方式 | 不通过触发行为 |
|--------|------|---------|--------------|
| **孤立实体率** | 关系 | 统计没有任何关系的实体占全部实体的比例 | 若 >15%，返回列表，要求过滤低相关实体或合并到父实体 |
| **关系对称性** | 关系 | 对于 `part_of` / `contains` 等成对谓词，A→B 存在时 B→A（inverse）是否存在 | 提取不对称关系子集，要求补充 inverse 关系 |
| **关系多样性** | 关系 | 统计各谓词类型的占比，是否某一种占比过多（如 references > 60%） | 要求补充其他谓词类型使用频次，使最高占比 ≤50% |
| **关系三角验证** | 关系 | A→B 和 B→C 存在时，A→C 是否也有合理关系？ | 缺失传递关系的标记为 `quality.warnings` |
| **实体类型争议** | 语义 | 同一实体在多个 block 中被标注为不同 entity_type | 标记为冲突，降低 confidence，要求审阅后统一 |
| **实体定义模糊** | 语义 | context_snippet 中没有准确定义实体含义，仅有"被提及"的上下文 | confidence < 0.5，要求补充准确定义片段 |
| **同义合并** | 语义 | 两个实体名称不同但 context_snippet 高度相似的（可能为同一概念的不同表述） | 标记为 `possible_merge`，要求去重，保留规范名称 |
| **跨界实体** | 语义 | 实体类型与关系模式不匹配（如 type=material 但所有关系都是 part_of policy） | 类型可能错误，标记审核 |
| **命名合规** | 语义 | 实体 ID 的 ent_ 前缀后首个词是否为中文，不含英文缩写或纯数字 | 要求重命名，confidence 降低 0.15 |
| **时间/属性降级** | 语义 | 时间修饰语、纯数值、单次出现名词是否被错误提取为独立实体 | 降级为所属实体的 properties，或直接过滤 |
| **粒度一致性** | 语义 | 同类型实体是否分布在相同抽象层级（如是否把条款中的示例场景独立为实体） | 合并细碎实体，场景降级为父实体的属性/子节点 |

### Stage 3: Wiki 质量检查

| 检查项 | 层面 | 检测方式 | 不通过触发行为 |
|--------|------|---------|--------------|
| **骨架完整性** | 语义 | domain 配置的 wiki_skeleton.sections 中定义的各组（概述、标准、条件、材料等），是否存在内容为空或过于简略 | 补充缺失 section 后 redo |
| **源可追溯** | 语义 | 每个核心论点/数值是否能定位到具体某个 block | 无源段落标记并要求补充引用链 |
| **实体一致性** | 关系 | Wiki 的 entity_id 是否在 entities.json 中存在并且类型匹配 | 中断，提示 Stage 2 输出不一致 |
| **内部链接** | 关系 | Wiki 体文中是否使用 `[[ent_xxx]]` 引用了其他实体，该实体是否存在 | 断开链接标记待修复 |
| **信息退化** | 语义 | Wiki 内容是否比其源的 block content 显著减少了信息量 | 补充退化段落 |
| **知识时效** | 语义 | 级联更新标记该实体 stale 时，Wiki 是否已过期 | 重新编译 stale Wiki |
| **篇幅合理** | 语义 | 同类实体间 wiki 长度偏差是否过大（>3σ） | 过简短的标记为低质量，建议根据引用情况丰富 |
| **不自相矛盾** | 语义 | Wiki 不同 section 之间是否存在相互矛盾的说法 | 标记矛盾位置，提供相关 block 定位 |

### Stage 4: QA 质量检查

| 检查项 | 层面 | 检测方式 | 不通过触发行为 |
|--------|------|---------|--------------|
| **追源验证** | 语义 | 每个 QA 的 answer 是否能在其源 Wiki 中找到对应的 section 内容 | 无源 QA 标记为"幻觉"，要求重做 |
| **模板覆盖率** | 关系 | domain 配置的 qa_templates 中每种 pattern 是否至少有一组 QA | 补充缺失的 pattern |
| **问句多样性** | 语义 | 同一实体关联的多个 QA 在问法上是否过于重复（如 n 个问题全部为"xxx是什么？"） | 要求补充不同问法（如何、是否、列举等） |
| **自洽性** | 语义 | 同一实体在不同 QA 间是否存在答案矛盾（如 A 问答"基数上限为 17124"，B 问答"基数上限为 20000"） | 矛盾对标记人工审核，连同矛盾定位 |
| **置信度分布** | 关系 | QA 的 quality.confidence 均值 < 0.6？ | 整体低于阈值时，反向要求补充更确切的 Wiki 内容 |
| **往返测试** | 语义 | 用 QA 的 answer 反推出 question，与原 question 语义对比是否一致 | 语义漂移标记重做 |

---

## 反馈回环机制

### 数据流

```
Stage N 输出
    ↓
┌─ 质量检查器 ────────────────────────────────────────────────────┐
│  1. 基本统计（计数、置信度分布、长度分布）                       │
│  2. 关系层检查（孤立率、多样性、对称性、三角验证）               │
│  3. 语义层检查（类型争议、同义合并、准确性、自包含）             │
│  4. 阶段特定检查（实体命名合规 / Wiki 骨架完整性 / QA 追源验证） │
│  5. 生成：质量报告 + 修复指令                                   │
└─────────────────────────────────────────────────────────────────┘
    ↓
通过？──→ 全部通过 → 下一阶段
    ↓ 不通过
修复指令注入子 Agent Prompt
    ↓
子 Agent 重做（保留原始输入 + 附加修指令）
    ↓
再次检查（递归）
    ↓
(最多 count=3 递归)
    ↓
仍不通过 → 标记 `human_review_required` → 继续下游
```

### 修复指令格式

每次反馈回环的指令必须结构化，格式如下：

```yaml
quality_feedback:
  stage: 2                                          # 当前阶段编号
  retry_count: 1                                    # 第几次重试
  summary: "实体抽取质量检查发现问题，需修复以下 4 项"  # 概览
  issues:
    - severity: error
      check: "命名合规"
      affected: ["ent_clause_article_1", "ent_policy_notice_46", "ent_condition_multiple_marriage"]
      instruction: "将上述实体的 ID 从英文/数字前缀改为中文描述名。ent_clause_article_1 → ent_规范改进提取政策"
    
    - severity: error
      check: "时间修饰语降级"
      affected: ["ent_2020年度", "ent_2021年度"]
      instruction: "这两个实体是其他实体的时间属性，不应独立存在。将其从实体列表移除，改为以下实体的 properties：缴存基数上限，增加 effective_year: '2020'"

    - severity: warning
      check: "孤立实体"
      count: 31
      threshold: 15
      percentage: "21.8%"
      instruction: "孤立实体超过 15% 阈值。审查无关系的实体，进行合并或过滤。提示：单次出现、无关系的实体建议丢弃。"
    
    - severity: warning
      check: "关系多样性"
      detail: "references 占比 72%，阈值 60%"
      instruction: "将至少 40% 的 references 关系替换为更具体的谓词（requires, part_of 等）。两个实体之间的关系不要使用 references 当兜底。"
  output_path: "pipeline-output/entities.json"
```

### 重试边界条件

| 条件 | 行为 |
|------|------|
| 第 1 次不通过 | 生成质量报告 + 结构化修复指令 → 同 Agent 重做 |
| 第 2 次不通过 | 生成报告 → 换另一个子 Agent（新视角）→ 重做 |
| 第 3 次不通过 | 跳过当前阶段有问题的输出，标记 `human_review_required: true`，继续下游管线 |
| 严重问题 >5 项（error 级别） | 同一次重试中先解决 error 级别问题，warning 级别延后 |
| 置信度 < 0.3 且连续两次重试无改善 | 直接丢弃该问题输出，不阻塞后续操作 |

---

## 质量报告生成器

每次检查完成后生成一份报告，汇报给编排器（用户可查看）。报告格式：

```json
{
  "report_id": "20260615-stage2-v1",
  "stage": 2,
  "status": "need_retry",
  "retry_count": 1,
  "max_retries": 3,
  "timestamp": "2026-06-15T10:30:00Z",
  "summary": {
    "total_entities": 142,
    "isolated_entities": 31,
    "isolated_percentage": "21.8%",
    "avg_relations_per_entity": 1.8,
    "relation_predicate_distribution": {
      "references": "72%",
      "part_of": "18%",
      "requires": "10%"
    },
    "avg_confidence": 0.39,
    "below_0.5_percentage": "76%"
  },
  "error_issues": [
    { "check": "命名合规", "count": 12, "severity": "error" },
    { "check": "时间修饰语降级", "count": 3, "severity": "error" }
  ],
  "warning_issues": [
    { "check": "孤立实体率", "value": "21.8%", "threshold": "15%", "severity": "warning" },
    { "check": "关系多样性", "value": "references=72%", "threshold": "<60%", "severity": "warning" }
  ],
  "passed_checks": ["关系对称性", "实体类型争议"],
  "human_review_required": false,
  "feedback_commands": { "…": "…" }
}
```

## 编排器改动要点

为支持反馈回环，当前编排器的线性执行需要在以下位置增加改动：

1. **Stage 完成后调用质量检查器** — 现有 Between-Stages 验证升级为全面的质量检查
2. **检查通过/不通过路由** — 通过时继续下一阶段；不通过时进入反馈回环
3. **修复指令注入** — 将结构化的指令注入子 Agent 的 prompt 上下文（保持原始输入不变，附加修复指令）
4. **重试计数器** — 为每个阶段维护独立的 retry_count，达到 max_retries=3 时标记 human_review_required
5. **质量报告留存** — 每次检查的报告写入 `pipeline-output/quality-reports/{stage}-{timestamp}.json`

## 与现有逻辑的关系

| 现有逻辑 | 本设计 | 关系 |
|---------|--------|------|
| Between-Stages 验证（计数、抽样、阶段特定检查） | 质量检查器 | **增强：** 保留现有规则作为基础，新增关系层和语义层检查 |
| Confidence scan（>20% < 0.5 暂停） | 反馈回环 | **替换：** 暂停→询问行为改为自动反馈→重做，仅在 3 次失败后转人工 |
| 子 Agent 单次执行 | 子 Agent 可接收反馈重做 | **扩展：** 不改 prompt 模板的基础结构，附加 quality_feedback 块 |
| Pipeline Resumption（按阶段检查输出存在） | 保留不变 | **兼容：** 反馈回环不影响断点恢复逻辑，重做后写入原有路径即可 |

---

## 决策记录

以下为设计评审确认的决策：

1. **质量报告频率：** 每阶段每次执行（含重试）均生成完整报告，写入 `pipeline-output/quality-reports/{stage}-{retry_count}-{timestamp}.json`
2. **重试 prompt 注入：** 在子 Agent prompt 末尾追加 `## Quality Feedback` 章节，携带结构化的 `quality_feedback` 块。原始 prompt 不变。
3. **human_review_required：** 经过 3 次重试仍不通过的输出，写入 `pipeline-output/human-review/` 目录，管线继续执行下游阶段。标记为人工审查留档。
