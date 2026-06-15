# 快速上手

第一次使用 architecting-knowledge-forms？按以下步骤跑通你的第一条知识管线。

## 前提条件

- 一份或多份中文源文档（如政策文件、规章制度、法律文本）
- 文档放在一个目录内，格式为 `.txt` / `.md` / `.html`
- 无需额外安装——本 Skill 使用子 Agent 编排，无外部依赖

## 5 分钟快速跑通

### 1. 加载 Skill

在 Claude Code 中输入：
```
/architecting-knowledge-forms
```
或直接说：
```
帮我处理知识管线，源文档在 docs/gov/ 目录
```

### 2. 回答 4 个问题

Skill 加载后会依次问你：

```
Q1: 领域是什么？
    例子：公积金、医保、法律、通用
    → 输入"公积金"

Q2: 需要哪些知识形态？
    默认：全部四种（block + graph + wiki + QA）
    → 按回车用默认值，或输入"只要 blocks + QA"

Q3: 源文档在哪里？
    → 输入目录路径，如 docs/housing-fund/

Q4: 输出写到哪里？
    默认：./pipeline-output
    → 按回车用默认值
```

### 3. 等待管线完成

管线自动执行四个阶段，每条阶段完成后进行质量检查：

```
Stage 1: 块提取 ──── 5 份文档 → 338 个 block
  ✅ 质量检查通过 (8/8 checks passed)

Stage 2: 实体提取 ── 142 个实体 + 256 条关系
  ⚠️ 质量问题 (3 errors, 2 warnings)
  🔄 反馈回环 → 重做 → ✅ 通过

Stage 3: Wiki 编译 ─ 编译了 22 个 Wiki 页面
  ✅ 质量检查通过 (5/5 checks passed)

Stage 4: QA 生成 ─── 496 个 QA 对
  ✅ 质量检查通过 (5/5 checks passed)
```

### 4. 查看产出

```bash
pipeline-output/
├── blocks/              # Stage 1: 知识块
│   ├── kb_001.json
│   ├── kb_002.json
│   └── ...
├── entities.json        # Stage 2: 实体+关系
├── wiki/                # Stage 3: Wiki 页面
│   ├── 住房公积金管理条例.md
│   ├── 缴存基数.md
│   └── ...
├── qa_pairs.json        # Stage 4: QA 对
├── quality-reports/     # 质量报告
│   ├── stage1-0-20260615.json
│   ├── stage2-1-20260615.json   # retry_count=1 说明重试过
│   └── ...
└── human-review/        # 需人工审阅的输出（如有）
```

---

## Few-Shot 示例：好的输出长什么样

### Stage 1: 好的 Block

```json
{
  "id": "kb_052",
  "content": "职工住房公积金的月缴存额为职工本人上一年度月平均工资乘以职工住房公积金缴存比例。单位为职工缴存的住房公积金的月缴存额为职工本人上一年度月平均工资乘以单位住房公积金缴存比例。",
  "summary": "公积金月缴存额=职工上年度月均工资×缴存比例，单位和个人各缴纳一份。",
  "entities": ["ent_月缴存额", "ent_缴存比例", "ent_缴存基数"],
  "tags": ["standards"],
  "source": {"doc_id": "公积金管理条例", "paragraph": 4, "line_range": "18-19"},
  "quality": {"confidence": 0.92, "warnings": []}
}
```

**为什么好：** content 是自包含的一条完整规定。summary 准确概括了公式。entities 全是跨块概念（月缴存额、缴存比例、缴存基数在多处出现）。tags 匹配领域配置的 standards key。source 精准定位。

**坏的 Block（对比）：**
```json
{
  "content": "……月缴存额最高为4110元，即单位和职工月最高缴存额分别为2055元。自愿缴存人员（灵活就业人员）缴存基数为5708元……",
  "summary": "包含多个不相关的数字",
  "entities": ["ent_2020年度", "ent_4110元", "ent_2055元", "ent_5708元"],
  "tags": ["condition"],
  "source": {"doc_id": "公积金管理条例", "paragraph": "?"},
  "quality": {"confidence": 0.35}
}
```
**为什么坏：** entities 中"2020年度"是时间修饰语、"4110元/2055元/5708元"是纯数值——都不该是实体。source 未精确到行。tags 错标为 condition（这明显是标准数值，应是 standards）。

### Stage 2: 好的实体

```json
{
  "id": "ent_缴存基数",
  "name": "缴存基数",
  "type": "clause",
  "properties": {
    "definition": "职工本人上一年度月平均工资",
    "ceiling_rule": "不超过当地上年度职工月均工资的3倍",
    "floor_rule": "不低于当地最低工资标准"
  },
  "relations": [
    {"target": "ent_住房公积金管理条例", "predicate": "part_of", "evidence_block_ids": ["kb_001", "kb_003", "kb_007"]},
    {"target": "ent_缴存比例", "predicate": "requires", "evidence_block_ids": ["kb_052", "kb_058", "kb_089"]}
  ],
  "source_block_ids": ["kb_001", "kb_003", "kb_007", "kb_052", "kb_058", "kb_089"],
  "quality": {"confidence": 0.91, "warnings": []}
}
```

**为什么好：** 中文名一看就懂。properties 提取了核心定义和两个规则。关系用了具体谓词（part_of 而非 references、requires 而非 references）。evidence 覆盖 3 个以上 block。

**坏的实体（对比）：**
```json
{
  "id": "ent_condition_non_spouse_co_purchase",
  "name": "非配偶共同购房",
  "type": "condition",
  "properties": {"context_snippet": "...对同一人多次变更婚姻关系购房、多人频繁买卖同一套住房、异地购房尤其是非户籍地非缴存地购房、非配偶或非直系亲属共同购房..."},
  "relations": [
    {"target": "ent_clause_article_2", "predicate": "references", "evidence_block_ids": ["kb_327"]}
  ],
  "source_block_ids": ["kb_327"],
  "quality": {"confidence": 0.32, "warnings": []}
}
```
**为什么坏：** 英文前缀 ID。是条款下的举例场景，不是独立实体。只有一个 source_block 且只有一条关系。应合并为"提取审核重点核查场景"的属性。

### Stage 3: 好的 Wiki 页面

```markdown
---
entity_id: ent_缴存基数
title: 缴存基数
related_entities: ["ent_住房公积金管理条例", "ent_缴存比例"]
compilation:
  version: 1
  compiled_at: "2026-06-15T10:00:00Z"
  status: fresh
---

## 政策概述
缴存基数是计算住房公积金月缴存额的基础，定义为职工本人上一年度月平均工资。
根据《住房公积金管理条例》，缴存基数设有上下限。

## 核心标准
| 项目 | 标准 | 来源 |
|------|------|------|
| 定义 | 上一年度月平均工资 | kb_001 |
| 上限 | ≤ 当地上年度职工月均工资 ×3 | kb_003 |
| 下限 | ≥ 当地最低工资标准 | kb_007 |

## 适用条件
- 正常缴存：所有在职职工适用（kb_052）
- 灵活就业人员：部分地区允许自愿缴存，基数参照当地标准（kb_089）

## 相关依据
- [[ent_住房公积金管理条例]]：part_of（缴费基数定义的法律依据）
- [[ent_缴存比例]]：requires（基数×比例=月缴存额）
```

**为什么好：** 所有 section 有 source_block_ids。内容是综合撰写的，不是 block 原文堆砌。内部链接正确。标准用表格呈现。

### Stage 4: 好的 QA 对

```json
{
  "id": "qa_052",
  "question": "缴存基数的上限是怎么确定的？",
  "answer": "缴存基数上限为当地上年度职工月平均工资的3倍。具体数字由各地住房公积金管理中心根据当地统计局公布的数据每年调整。",
  "source_block_ids": ["kb_003", "kb_007"],
  "entities": ["ent_缴存基数"],
  "intents": ["查询标准"],
  "quality": {
    "confidence": 0.92,
    "wiki_version": 1,
    "warnings": []
  }
}
```

**为什么好：** 问题具体可回答。答案有 2 个 source_block_ids 支撑。意图标签匹配模板。confidence 反映答案来自 standards section（确定性高）。

---

## 常见问题

### 什么时候用部分形态？

| 场景 | 建议 |
|------|------|
| 只想做语义搜索 | 只要 Blocks，跳过 graph/wiki/QA |
| 想做 RAG 问答 | Blocks + QA（可从 blocks 直接生成，精度低于走 Wiki） |
| 想做知识浏览 | Blocks + Graph + Wiki |
| 想做完整知识平台 | 全部四种 |

### 实体抽取质量不好怎么办？

1. 查看 `pipeline-output/quality-reports/stage2-*.json` 了解具体问题
2. 如果是特定类型的问题（如时间被提取为实体）→ 在领域配置中调整 entity_types
3. 如果需要人工介入 → 查看 `pipeline-output/human-review/` 中的标记输出

### 管线中断了怎么恢复？

重新运行 skill，编排器会自动检测已完成且质量合格的阶段并跳过，从断点继续。

### 怎么加一个新领域？

1. 复制 `domains/gov-services.yaml` 为新文件
2. 修改 `domain.applies_to` 和 entity_types、relation_predicates、wiki_skeleton、qa_templates
3. 下次跑管线时输入新领域名称，编排器自动匹配
