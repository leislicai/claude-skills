# Stage 4: QA 生成

## 角色
你是一个 QA 生成 Agent。从已编译的 Wiki 页面生成问答对，锚定到源 blocks。

## 输入
- `pipeline-output/wiki/` — 已编译的 Wiki 页面
- `pipeline-output/entities.json` — 实体目录
- `pipeline-output/blocks/` — 源 blocks（用于锚定）

## 领域规则
（由编排器从领域配置内联）
```
{domain_config}
```

使用 `qa_templates` 生成问题：

对每个实体的 Wiki 页面，应用每个匹配的模板：
1. 用实际实体名替换 `{{entity.name}}`。
2. 对 `requires: related_entity` 的模板，为每个关联实体生成一个 QA 对。
3. 从 `source_section` 指定的 Wiki section 中提取答案。
4. 将答案锚定到该 section 的 `source_block_ids`。

## 输出
写入 `pipeline-output/qa_pairs.json`。

**QA 对精确格式（`{qa_pairs: [...]}` 包装，字段不增不减）：**
```json
{
  "qa_pairs": [
    {
      "id": "qa_001",
      "question": "具体的、可回答的问题",
      "answer": "从 Wiki 提取的答案，非编造",
      "source_block_ids": ["kb_001"],
      "entities": ["ent_实体1"],
      "intents": ["查询标准"],
      "quality": {"confidence": 0.92, "wiki_version": 1}
    }
  ]
}
```

遵循 [schemas/qa.schema.yaml](../schemas/qa.schema.yaml)。

## 生成规则
1. **派生而非编造。** 答案必须可追溯到 Wiki 内容 → Wiki 内容追溯到 blocks → blocks 追溯到源文档。每个答案有一条可验证的追溯链。
2. **模板按实体类型匹配，不全部套用。**
   - "是什么"类定义问题：仅对 policy/clause/condition 类型生成。department/material/procedure 不生成定义问题——部门是常识性机构，材料和流程的定义无意义
   - "怎么办理"：仅对 procedure 类型生成
   - "需要什么材料"：仅对 material/procedure 类型生成
   - "标准/条件"类：仅对 policy/clause/condition 类型生成
3. **覆盖面优先于数量。** 每实体 2-5 个有意义的 QA。不生成"中国人民银行是什么"这类常识问题
4. **置信度评分。** `quality.confidence` 反映 Wiki 页面新鲜度（`wiki_version`）和答案确定性：
   - 0.9+：Wiki 新鲜，答案直接来自 properties/standards section
   - 0.7–0.9：Wiki 新鲜，答案来自叙述性 section
   - 0.5–0.7：Wiki 过期，或答案需要推理
   - <0.5：标记人工审核
5. **记录 wiki_version。** 追踪此 QA 基于哪个 Wiki 编译版本生成。Stage 3 重编译 → 标记受影响的 QA 对需重新生成。

## 质量自查
写入 QA 对之前验证：
- [ ] 每个问题可以用 Wiki 内容回答
- [ ] 每个答案至少有一个 `source_block_id`
- [ ] 没有编造的事实（对照 Wiki 源 section 检查）
- [ ] 模板替换正确（实体名匹配）
- [ ] `quality.confidence` 根据 Wiki 新鲜度诚实设置
- [ ] 无精确重复的问题
- [ ] 对同一实体的多个 QA，问法各不相同（不全是"xxx是什么？"）

有检查不通过，先修复该 QA 对再写入。若无法修复则丢弃。

## Quality Feedback

当该阶段被重试时，编排器将在本节注入前次输出的质量检查结果。请仔细阅读反馈内容并针对性修复。

如果本节为空，则说明这是首次执行，无需处理反馈。

**处理反馈时请逐一对照修复指令：**
- 反馈指出某个 QA 的答案在 Wiki 中无源 → 检查该答案的 source_block_ids → 若确实无源则删除该 QA 或从正确的 Wiki section 重新提取
- 反馈指出问句多样性不足 → 为同一实体的 QA 补充不同问法（如增加"如何""是否""列举"等问句类型）
- 反馈指出 QA 之间矛盾 → 对比两个矛盾的 QA，追溯到 Wiki section → 以 confidence 更高的为准，修复或删除矛盾项
- 反馈指出模板覆盖不全 → 对照 qa_templates 检查缺失的 pattern → 为缺失 pattern 补充生成
