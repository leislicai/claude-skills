#!/usr/bin/env python3
"""
将管线阶段输出转换为数据库可加载格式（JSONL + CSV + SQL + Neo4j Cypher）。

用法：
  python3 scripts/export-db-formats.py <stage:1|2|3|4> <output_dir>

  stage:      1=blocks, 2=entities, 3=wiki, 4=qa_pairs
  output_dir: pipeline 输出根目录（含 blocks/ entities.json wiki/ qa_pairs.json）

输出目录：
  {output_dir}/db/  — 所有 DB 格式文件

  每阶段产出：
  - Stage 1: blocks.jsonl  blocks.csv  blocks.sql
  - Stage 2: entities.jsonl  entities.csv  relations.csv  entities.cypher
  - Stage 3: wiki.jsonl  wiki.csv
  - Stage 4: qa_pairs.jsonl  qa_pairs.csv  qa_pairs.sql

退出码：0=成功 1=源文件缺失 2=脚本异常
"""

import json
import sys
import os
import glob
import csv
import io
import textwrap
from collections import OrderedDict

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def flatten_list(val, sep=", "):
    """将数组展平为分隔符字符串，CSV 友好。"""
    if isinstance(val, list):
        return sep.join(str(v) for v in val)
    if isinstance(val, str):
        return val
    return json.dumps(val, ensure_ascii=False) if val is not None else ""


def flatten_dict(d, parent_key=""):
    """将嵌套 dict 展平为 flat 列名。例如 source.file → source_file。"""
    if not isinstance(d, dict):
        return {parent_key: flatten_list(d) if isinstance(d, list) else (d or "")}
    items = {}
    for k, v in d.items():
        new_key = f"{parent_key}_{k}" if parent_key else k
        if isinstance(v, dict):
            items.update(flatten_dict(v, new_key))
        elif isinstance(v, list):
            items[new_key] = flatten_list(v)
        else:
            items[new_key] = v if v is not None else ""
    return items


def sql_escape(val):
    """转义 SQL 字符串值。"""
    if val is None:
        return "NULL"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    s = str(val).replace("'", "''")
    return f"'{s}'"


def cypher_escape(val):
    """转义 Cypher 字符串值。"""
    if val is None:
        return "null"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, bool):
        return "true" if val else "false"
    s = str(val).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{s}'"


def cypher_props(d, indent=4):
    """将 dict 转为 Cypher 属性字面量。"""
    if not d:
        return "{}"
    pairs = []
    for k, v in d.items():
        if isinstance(v, (int, float)):
            pairs.append(f"{k}: {v}")
        elif isinstance(v, bool):
            pairs.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, list):
            arr = ", ".join(cypher_escape(x) for x in v)
            pairs.append(f"{k}: [{arr}]")
        else:
            pairs.append(f"{k}: {cypher_escape(v)}")
    prefix = " " * indent
    return "{\n" + ",\n".join(f"{prefix}  {p}" for p in pairs) + f"\n{prefix}}}"


def read_json_safe(path):
    """安全读取 JSON 文件，失败返回 None。"""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"  ⚠ 跳过 {os.path.basename(path)}: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Stage 1: Blocks → JSONL / CSV / SQL
# ---------------------------------------------------------------------------

BLOCKS_SQL_DDL = """\
CREATE TABLE IF NOT EXISTS knowledge_blocks (
    id          TEXT PRIMARY KEY,
    content     TEXT NOT NULL,
    summary     TEXT NOT NULL,
    entities    TEXT[],        -- PostgreSQL array: ARRAY['ent_xxx','ent_yyy']
    tags        TEXT[],
    source_file         TEXT,
    source_title        TEXT,
    source_section      TEXT,
    source_line_range   TEXT,
    quality_confidence  REAL,
    quality_warnings    TEXT
);

COMMENT ON TABLE knowledge_blocks IS 'Stage 1: 知识块';
"""


def export_blocks(output_dir, db_dir):
    """Stage 1: blocks/kb_*.json → JSONL + CSV + SQL"""
    blocks_dir = os.path.join(output_dir, "blocks")
    files = sorted(glob.glob(os.path.join(blocks_dir, "kb_*.json")))
    if not files:
        print("  ⚠ blocks/ 中无 kb_*.json 文件，跳过 Stage 1 导出")
        return

    records = []
    for f in files:
        data = read_json_safe(f)
        if data is None:
            continue
        flat = flatten_dict(data)
        records.append(flat)
        # JSONL — write as we go
        with open(os.path.join(db_dir, "blocks.jsonl"), "a", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
            fh.write("\n")

    if not records:
        return

    # CSV
    csv_path = os.path.join(db_dir, "blocks.csv")
    fieldnames = [
        "id", "content", "summary", "entities", "tags",
        "source_file", "source_title", "source_section", "source_line_range",
        "quality_confidence", "quality_warnings",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in records:
            # Flatten arrays for CSV
            row = dict(r)
            for k in ("entities", "tags", "quality_warnings"):
                if k in row and isinstance(row[k], list):
                    row[k] = "|".join(str(v) for v in row[k])
            writer.writerow(row)

    # SQL (PostgreSQL dialect)
    sql_path = os.path.join(db_dir, "blocks.sql")
    with open(sql_path, "w", encoding="utf-8") as fh:
        fh.write("-- Stage 1: Knowledge Blocks SQL\n")
        fh.write("-- Generated by export-db-formats.py\n\n")
        fh.write(BLOCKS_SQL_DDL)
        fh.write("\n")
        for r in records:
            entities_arr = f"ARRAY[{', '.join(sql_escape(e) for e in r.get('entities', []))}]" if r.get('entities') else "ARRAY[]::TEXT[]"
            tags_arr = f"ARRAY[{', '.join(sql_escape(t) for t in r.get('tags', []))}]" if r.get('tags') else "ARRAY[]::TEXT[]"
            fh.write(
                f"INSERT INTO knowledge_blocks (id, content, summary, entities, tags, "
                f"source_file, source_title, source_section, source_line_range, "
                f"quality_confidence, quality_warnings) VALUES (\n"
                f"  {sql_escape(r.get('id'))},\n"
                f"  {sql_escape(r.get('content'))},\n"
                f"  {sql_escape(r.get('summary'))},\n"
                f"  {entities_arr},\n"
                f"  {tags_arr},\n"
                f"  {sql_escape(r.get('source_file'))},\n"
                f"  {sql_escape(r.get('source_title'))},\n"
                f"  {sql_escape(r.get('source_section'))},\n"
                f"  {sql_escape(r.get('source_line_range'))},\n"
                f"  {r.get('quality_confidence') or 'NULL'},\n"
                f"  {sql_escape(flatten_list(r.get('quality_warnings', []), '; '))}\n"
                f");\n"
            )

    print(f"  ✅ Stage 1 导出: {len(records)} 块")


# ---------------------------------------------------------------------------
# Stage 2: Entities → JSONL / CSV / Cypher
# ---------------------------------------------------------------------------

ENTITIES_CYPHER_HEADER = """\
// ============================================================
// Stage 2: Entity Graph — Neo4j Cypher Script
// Generated by export-db-formats.py
// ============================================================
//
// 使用方式:
//   cypher-shell -u neo4j -p password < entities.cypher
//   或 Neo4j Browser 中逐段执行
//
// 脚本分三部分:
//   1. 节点索引 (提升 MATCH 性能)
//   2. 节点创建 (CREATE :Entity)
//   3. 关系创建 (CREATE (:Entity)-[:REL]->(:Entity))
// ============================================================

// --- Part 1: Indexes ---
CREATE INDEX entity_id IF NOT EXISTS FOR (e:Entity) ON (e.id);
CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.type);

// --- Part 2: Nodes ---
"""


def export_entities(output_dir, db_dir):
    """Stage 2: entities.json → JSONL + CSV(nodes) + CSV(edges) + Cypher"""
    entities_path = os.path.join(output_dir, "entities.json")
    data = read_json_safe(entities_path)
    if data is None:
        print("  ⚠ entities.json 不存在或无法解析，跳过 Stage 2 导出")
        return

    entities = data.get("entities", [])
    if not entities:
        return

    # JSONL — one entity per line (flattened, relations as array)
    jsonl_path = os.path.join(db_dir, "entities.jsonl")
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for e in entities:
            json.dump(e, f, ensure_ascii=False)
            f.write("\n")

    # CSV — nodes
    nodes_csv_path = os.path.join(db_dir, "entities.csv")
    node_fields = ["id", "name", "type", "properties", "source_block_ids", "confidence", "warnings", "relation_count"]
    with open(nodes_csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=node_fields, extrasaction="ignore")
        writer.writeheader()
        for e in entities:
            row = {
                "id": e.get("id", ""),
                "name": e.get("name", ""),
                "type": e.get("type", ""),
                "properties": json.dumps(e.get("properties", {}), ensure_ascii=False),
                "source_block_ids": flatten_list(e.get("source_block_ids", []), "|"),
                "confidence": e.get("quality", {}).get("confidence", ""),
                "warnings": flatten_list(e.get("quality", {}).get("warnings", []), "|"),
                "relation_count": len(e.get("relations", [])),
            }
            writer.writerow(row)

    # CSV — edges (relations)
    edges_csv_path = os.path.join(db_dir, "relations.csv")
    edge_fields = ["source_id", "target_id", "predicate", "evidence_block_ids"]
    edge_count = 0
    with open(edges_csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=edge_fields, extrasaction="ignore")
        writer.writeheader()
        for e in entities:
            src_id = e.get("id", "")
            for rel in e.get("relations", []):
                writer.writerow({
                    "source_id": src_id,
                    "target_id": rel.get("target", ""),
                    "predicate": rel.get("predicate", ""),
                    "evidence_block_ids": flatten_list(rel.get("evidence_block_ids", []), "|"),
                })
                edge_count += 1

    # Cypher script
    cypher_path = os.path.join(db_dir, "entities.cypher")
    with open(cypher_path, "w", encoding="utf-8") as fh:
        fh.write(ENTITIES_CYPHER_HEADER)
        # Nodes
        for e in entities:
            props = {}
            if e.get("name"):
                props["name"] = e["name"]
            if e.get("type"):
                props["type"] = e["type"]
            entity_props = e.get("properties", {}) or {}
            props.update(entity_props)
            if e.get("source_block_ids"):
                props["source_block_ids"] = e["source_block_ids"]
            if e.get("quality", {}).get("confidence") is not None:
                props["confidence"] = e["quality"]["confidence"]

            fh.write(f"CREATE (e:Entity {{\n")
            fh.write(f"  id: {cypher_escape(e.get('id', ''))},\n")
            for k, v in props.items():
                if isinstance(v, (int, float)):
                    fh.write(f"  {k}: {v},\n")
                elif isinstance(v, list):
                    arr = ", ".join(cypher_escape(x) for x in v)
                    fh.write(f"  {k}: [{arr}],\n")
                else:
                    fh.write(f"  {k}: {cypher_escape(v)},\n")
            fh.write("});\n\n")

        # Relationships (part 3)
        fh.write("\n// --- Part 3: Relationships ---\n")
        for e in entities:
            src_id = e.get("id", "")
            for rel in e.get("relations", []):
                target = rel.get("target", "")
                predicate = rel.get("predicate", "").upper()
                evidence = rel.get("evidence_block_ids", [])
                fh.write(f"MATCH (a:Entity {{id: {cypher_escape(src_id)}}})\n")
                fh.write(f"MATCH (b:Entity {{id: {cypher_escape(target)}}})\n")
                evidence_arr = ", ".join(cypher_escape(x) for x in evidence)
                fh.write(f"CREATE (a)-[:{predicate} {{evidence: [{evidence_arr}]}}]->(b);\n\n")

        # Stats comment
        fh.write(f"// --- Stats ---\n")
        fh.write(f"// Nodes: {len(entities)}\n")
        fh.write(f"// Edges: {edge_count}\n")

    print(f"  ✅ Stage 2 导出: {len(entities)} 节点, {edge_count} 边")


# ---------------------------------------------------------------------------
# Stage 3: Wiki → JSONL / CSV
# ---------------------------------------------------------------------------

def export_wiki(output_dir, db_dir):
    """Stage 3: wiki/*.md → JSONL + CSV"""
    wiki_dir = os.path.join(output_dir, "wiki")
    files = sorted(glob.glob(os.path.join(wiki_dir, "*.md")))
    if not files:
        print("  ⚠ wiki/ 中无 .md 文件，跳过 Stage 3 导出")
        return

    records = []
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                text = fh.read()
        except Exception as e:
            print(f"  ⚠ 跳过 {os.path.basename(f)}: {e}", file=sys.stderr)
            continue

        # Parse YAML frontmatter
        frontmatter = {}
        body = text
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                try:
                    import yaml
                    frontmatter = yaml.safe_load(parts[1]) or {}
                except Exception:
                    frontmatter = {}
                body = parts[2].strip()

        record = dict(frontmatter)
        record["content_md"] = body
        record["_filename"] = os.path.basename(f)
        records.append(record)

        # JSONL
        with open(os.path.join(db_dir, "wiki.jsonl"), "a", encoding="utf-8") as fh:
            json.dump(record, fh, ensure_ascii=False)
            fh.write("\n")

    if not records:
        return

    # CSV
    csv_path = os.path.join(db_dir, "wiki.csv")
    fieldnames = [
        "entity_id", "title", "entity_type", "version", "status", "compiled_at",
        "source_block_ids", "related_entities", "content_md",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in records:
            row = {}
            for fn in fieldnames:
                val = r.get(fn, "")
                if isinstance(val, list):
                    val = "|".join(str(v) for v in val)
                row[fn] = val
            writer.writerow(row)

    print(f"  ✅ Stage 3 导出: {len(records)} Wiki 页面")


# ---------------------------------------------------------------------------
# Stage 4: QA Pairs → JSONL / CSV / SQL
# ---------------------------------------------------------------------------

QA_SQL_DDL = """\
CREATE TABLE IF NOT EXISTS qa_pairs (
    id                  TEXT PRIMARY KEY,
    question            TEXT NOT NULL,
    answer              TEXT NOT NULL,
    source_block_ids    TEXT[],        -- PostgreSQL array
    entities            TEXT[],        -- PostgreSQL array
    intents             TEXT[],        -- PostgreSQL array
    scenario            TEXT,
    quality_confidence  REAL,
    wiki_version        INTEGER
);

COMMENT ON TABLE qa_pairs IS 'Stage 4: QA 对';
"""


def export_qa_pairs(output_dir, db_dir):
    """Stage 4: qa_pairs.json → JSONL + CSV + SQL"""
    qa_path = os.path.join(output_dir, "qa_pairs.json")
    data = read_json_safe(qa_path)
    if data is None:
        print("  ⚠ qa_pairs.json 不存在或无法解析，跳过 Stage 4 导出")
        return

    pairs = data.get("qa_pairs", [])
    if not pairs:
        return

    # JSONL
    jsonl_path = os.path.join(db_dir, "qa_pairs.jsonl")
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for qa in pairs:
            json.dump(qa, f, ensure_ascii=False)
            f.write("\n")

    # CSV
    csv_path = os.path.join(db_dir, "qa_pairs.csv")
    fieldnames = [
        "id", "question", "answer", "source_block_ids", "entities",
        "intents", "scenario", "quality_confidence", "wiki_version",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for qa in pairs:
            row = {
                "id": qa.get("id", ""),
                "question": qa.get("question", ""),
                "answer": qa.get("answer", ""),
                "source_block_ids": flatten_list(qa.get("source_block_ids", []), "|"),
                "entities": flatten_list(qa.get("entities", []), "|"),
                "intents": flatten_list(qa.get("intents", []), "|"),
                "scenario": qa.get("scenario", ""),
                "quality_confidence": qa.get("quality", {}).get("confidence", ""),
                "wiki_version": qa.get("quality", {}).get("wiki_version", ""),
            }
            writer.writerow(row)

    # SQL
    sql_path = os.path.join(db_dir, "qa_pairs.sql")
    with open(sql_path, "w", encoding="utf-8") as fh:
        fh.write("-- Stage 4: QA Pairs SQL\n")
        fh.write("-- Generated by export-db-formats.py\n\n")
        fh.write(QA_SQL_DDL)
        fh.write("\n")
        for qa in pairs:
            sb_arr = f"ARRAY[{', '.join(sql_escape(b) for b in qa.get('source_block_ids', []))}]" if qa.get('source_block_ids') else "ARRAY[]::TEXT[]"
            ent_arr = f"ARRAY[{', '.join(sql_escape(b) for b in qa.get('entities', []))}]" if qa.get('entities') else "ARRAY[]::TEXT[]"
            int_arr = f"ARRAY[{', '.join(sql_escape(b) for b in qa.get('intents', []))}]" if qa.get('intents') else "ARRAY[]::TEXT[]"
            fh.write(
                f"INSERT INTO qa_pairs (id, question, answer, source_block_ids, entities, "
                f"intents, scenario, quality_confidence, wiki_version) VALUES (\n"
                f"  {sql_escape(qa.get('id'))},\n"
                f"  {sql_escape(qa.get('question'))},\n"
                f"  {sql_escape(qa.get('answer'))},\n"
                f"  {sb_arr},\n"
                f"  {ent_arr},\n"
                f"  {int_arr},\n"
                f"  {sql_escape(qa.get('scenario'))},\n"
                f"  {qa.get('quality', {}).get('confidence', 'NULL')},\n"
                f"  {qa.get('quality', {}).get('wiki_version', 'NULL')}\n"
                f");\n"
            )

    print(f"  ✅ Stage 4 导出: {len(pairs)} QA 对")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

STAGE_EXPORTERS = {
    1: export_blocks,
    2: export_entities,
    3: export_wiki,
    4: export_qa_pairs,
}

STAGE_LABELS = {
    1: ("知识块", "blocks.jsonl, blocks.csv, blocks.sql"),
    2: ("实体图", "entities.jsonl, entities.csv, relations.csv, entities.cypher"),
    3: ("Wiki 页面", "wiki.jsonl, wiki.csv"),
    4: ("QA 对", "qa_pairs.jsonl, qa_pairs.csv, qa_pairs.sql"),
}


def main():
    if len(sys.argv) < 3:
        print(f"用法: {sys.argv[0]} <stage:1|2|3|4> <output_dir>", file=sys.stderr)
        sys.exit(2)

    try:
        stage = int(sys.argv[1])
    except ValueError:
        print(f"错误: stage 必须是 1-4，收到 '{sys.argv[1]}'", file=sys.stderr)
        sys.exit(2)

    if stage not in STAGE_EXPORTERS:
        print(f"错误: stage 必须为 1-4", file=sys.stderr)
        sys.exit(2)

    output_dir = sys.argv[2]
    db_dir = os.path.join(output_dir, "db")
    os.makedirs(db_dir, exist_ok=True)

    label, files_desc = STAGE_LABELS[stage]
    print(f"Stage {stage} ({label}) → {output_dir}/db/")
    print(f"  产物: {files_desc}")

    try:
        STAGE_EXPORTERS[stage](output_dir, db_dir)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n  ❌ 导出失败: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
