# 管线示例输出（v2.8）

3 份天水市住房公积金政策文档经四阶段管线处理的全量产出，含 DB 导出格式。

**源文档：**
- 住房公积金管理条例（国家法规，7章47条）
- 全市住房公积金各服务大厅实行"周六不打烊"工作日延时预约上门等服务（服务公告）
- 天水市住房公积金管理中心关于调整部分政策的说明（政策调整通知）

## 产出总览

| 阶段 | 产出 | 质量 |
|------|------|------|
| Stage 1 — 块提取 | **37 blocks** | 机械预检 0 errors |
| Stage 2 — 实体提取 | **8 entities + 18 relations** | 70% related, 5/5 谓词激活 |
| Stage 3 — Wiki 编译 | **8 wiki pages** | 机械预检 0 errors |
| Stage 4 — QA 生成 | **23 QA pairs** | 8 实体覆盖 |

## DB 导出（v2.8 新增）

| 格式 | Stage 1 Block | Stage 2 Entity | Stage 3 Wiki | Stage 4 QA |
|------|:---:|:---:|:---:|:---:|
| JSONL | blocks.jsonl | entities.jsonl | wiki.jsonl | qa_pairs.jsonl |
| CSV | blocks.csv | entities.csv + relations.csv | wiki.csv | qa_pairs.csv |
| SQL | blocks.sql | — | — | qa_pairs.sql |
| Cypher | — | entities.cypher | — | — |

### 使用示例

**Neo4j 图数据库导入：**
```bash
cypher-shell -u neo4j -p password < db/entities.cypher
```

**PostgreSQL 导入：**
```sql
\i db/blocks.sql
\i db/qa_pairs.sql
```

**CSV 通用导入（pandas / Excel）：**
```python
import pandas as pd
blocks = pd.read_csv('db/blocks.csv')
entities = pd.read_csv('db/entities.csv')
relations = pd.read_csv('db/relations.csv')
```

## 目录结构

```
pipeline-output/
├── blocks/              # Stage 1: JSON 格式（37 个文件）
├── entities.json        # Stage 2: 实体 + 关系
├── wiki/                # Stage 3: Markdown 页面（8 个）
├── qa_pairs.json        # Stage 4: QA 对
├── db/                  # DB 可加载格式（12 个文件）
├── quality-reports/     # 质量报告
└── human-review/        # 人工审阅
```
