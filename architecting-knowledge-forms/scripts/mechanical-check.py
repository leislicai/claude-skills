#!/usr/bin/env python3
"""
管线机械预检脚本 — 编排器在每个 Stage 完成后执行。

用法：
  python3 scripts/mechanical-check.py <stage> <output_dir> [--domain <config_path>]

  stage: 1|2|3|4
  output_dir: pipeline 输出根目录（如 /Users/xxx/res）
  --domain: 领域配置 .yaml 路径（可选，用于读取领域特定的阈值）

输出：JSON 格式的部分质量报告（机械检查结论 + 待语义检查项列表）

退出码：
  0 — 通过（可能含 warning）
  1 — 需重做（error 级别问题）
  2 — 脚本执行异常
"""

import json, sys, os, glob, re
from collections import Counter
from datetime import datetime

def check_stage_1(output_dir):
    """Stage 1: Block 质量预检"""
    checks = []
    blocks_dir = os.path.join(output_dir, "blocks")
    files = sorted(glob.glob(os.path.join(blocks_dir, "kb_*.json")))

    # 计数
    checks.append({
        "check_name": "计数",
        "layer": "mechanical",
        "severity": "error",
        "passed": len(files) > 0,
        "details": f"产出 {len(files)} 个 block" if files else "零输出",
        "affected_items": [] if files else [blocks_dir]
    })

    if not files:
        return checks, 0.0, 0.0

    # 读取所有 blocks
    blocks = []
    for f in files:
        try:
            with open(f) as fh:
                blocks.append(json.load(fh))
        except json.JSONDecodeError:
            checks.append({
                "check_name": "JSON 格式",
                "layer": "mechanical",
                "severity": "error",
                "passed": False,
                "details": f"文件 {os.path.basename(f)} JSON 解析失败",
                "affected_items": [os.path.basename(f)]
            })

    valid_blocks = len(blocks)
    all_blocks = len(files)

    # 置信度扫描
    confs = []
    for b in blocks:
        q = b.get("quality", {})
        c = q.get("confidence") if isinstance(q, dict) else None
        if c is not None:
            confs.append(c)
    avg_conf = sum(confs) / len(confs) if confs else 0
    below_05 = sum(1 for c in confs if c < 0.5)
    below_pct = 100 * below_05 / len(confs) if confs else 0

    checks.append({
        "check_name": "置信度扫描",
        "layer": "mechanical",
        "severity": "error" if below_pct > 20 else "info",
        "passed": below_pct <= 20,
        "details": f"均值 {avg_conf:.3f}, 低于0.5: {below_05}/{len(confs)} ({below_pct:.1f}%)",
        "threshold": {"actual": below_pct, "expected": 20.0}
    })

    # 实体格式
    str_ents = obj_ents = 0
    for b in blocks:
        for e in b.get("entities", []):
            if isinstance(e, str): str_ents += 1
            elif isinstance(e, dict): obj_ents += 1
    checks.append({
        "check_name": "实体格式一致性",
        "layer": "mechanical",
        "severity": "warning",
        "passed": True,
        "details": f"string 格式 {str_ents}, object 格式 {obj_ents}"
    })

    # 命名违规
    all_eids = set()
    for b in blocks:
        for e in b.get("entities", []):
            eid = e if isinstance(e, str) else e.get("id", "")
            if eid:
                all_eids.add(eid)
    non_chinese = [e for e in all_eids if e.replace("ent_","",1) and not ('一' <= e.replace("ent_","",1)[0] <= '鿿')]
    temporal = [e for e in all_eids if re.search(r'\d{4}年', e)]
    violation_pct = 100 * (len(non_chinese) + len(temporal)) / max(len(all_eids), 1)

    checks.append({
        "check_name": "实体命名合规",
        "layer": "semantic",
        "severity": "error" if violation_pct > 20 else "warning",
        "passed": violation_pct <= 20,
        "details": f"违规率 {violation_pct:.1f}% (非中文 {len(non_chinese)}, 时间前缀 {len(temporal)})",
        "threshold": {"actual": violation_pct, "expected": 20.0},
        "affected_items": non_chinese[:10] + temporal[:5]
    })

    return checks, avg_conf, valid_blocks / max(all_blocks, 1)


def check_stage_2(output_dir, domain_config=None):
    """Stage 2: Entity 质量预检"""
    checks = []
    entities_path = os.path.join(output_dir, "entities.json")

    # 读取领域特定的谓词容忍度
    pred_tolerances = {}
    if domain_config and os.path.exists(domain_config):
        try:
            # 简单 YAML 解析（避免引入 pyyaml 依赖）
            with open(domain_config) as f:
                yaml_text = f.read()
            import re as _re
            # 解析 谓词容忍度 段落（灵活缩进，处理注释）
            in_tolerance = False
            current_pred = None
            for line in yaml_text.split('\n'):
                # 去掉注释
                if '#' in line:
                    line = line.split('#')[0]
                stripped = line.strip()
                if '谓词容忍度' in stripped:
                    in_tolerance = True
                    continue
                if in_tolerance:
                    # 检查是否是同级或更高级的 key（离开容忍度段落）
                    if line and not line[0].isspace() and '谓词容忍度' not in stripped:
                        if stripped:  # 非空行说明是新的顶级 key
                            break
                    # 匹配谓词名（如 requires: 或 references:）
                    if stripped and stripped.endswith(':') and '上限' not in stripped and '原因' not in stripped:
                        current_pred = stripped.replace(':', '').strip()
                    elif '上限' in stripped and current_pred:
                        val = _re.search(r'([\d.]+)', stripped)
                        if val:
                            pred_tolerances[current_pred] = float(val.group(1))
        except Exception:
            pass  # 解析失败则用默认值

    # 默认阈值
    default_max_pct = 60.0

    if not os.path.exists(entities_path):
        checks.append({
            "check_name": "文件存在",
            "layer": "mechanical", "severity": "error", "passed": False,
            "details": "entities.json 不存在", "affected_items": [entities_path]
        })
        return checks, 0.0, 0.0

    with open(entities_path) as f:
        data = json.load(f)
    entities = data.get("entities", [])
    n = len(entities)

    checks.append({
        "check_name": "计数",
        "layer": "mechanical", "severity": "error",
        "passed": n > 0,
        "details": f"产出 {n} 个实体" if n else "零输出"
    })

    if not n:
        return checks, 0.0, 0.0

    # 孤立实体率
    orphans = [e for e in entities if not e.get("relations")]
    orphan_pct = 100 * len(orphans) / n
    checks.append({
        "check_name": "孤立实体率",
        "layer": "mechanical",
        "severity": "error" if orphan_pct > 15 else "info",
        "passed": orphan_pct <= 15,
        "details": f"{len(orphans)}/{n} ({orphan_pct:.1f}%), 阈值 15%",
        "threshold": {"actual": orphan_pct, "expected": 15.0},
        "affected_items": [e["id"] for e in orphans[:10]]
    })

    # 关系多样性
    preds = Counter()
    for e in entities:
        for r in e.get("relations", []):
            preds[r.get("predicate", "")] += 1
    total_rels = sum(preds.values())
    max_pred = max(preds.values()) if preds else 0
    max_pct = 100 * max_pred / total_rels if total_rels else 0
    max_name = preds.most_common(1)[0][0] if preds else "N/A"

    # 每个谓词使用自己的容忍上限（领域配置值为 0-1 比例，需转为百分比）
    pred_violations = []
    for pred_name, count in preds.items():
        pct = 100 * count / total_rels
        raw_limit = pred_tolerances.get(pred_name, default_max_pct / 100.0)
        # 如果 limit < 1，说明是比例，转为百分比
        limit = raw_limit * 100 if raw_limit < 1 else raw_limit
        if pct > limit:
            pred_violations.append(f"{pred_name}={pct:.1f}% (上限{limit:.0f}%)")
    diversity_passed = len(pred_violations) == 0

    checks.append({
        "check_name": "关系多样性",
        "layer": "mechanical",
        "severity": "error" if not diversity_passed else "info",
        "passed": diversity_passed,
        "details": f"谓词分布: {dict(preds)}. " + ("全部在领域容忍范围内" if diversity_passed else f"超标: {', '.join(pred_violations)}"),
        "threshold": {"actual": max_pct, "expected": default_max_pct}
    })

    # 关系密度
    avg_rels = total_rels / n if n else 0
    checks.append({
        "check_name": "关系密度",
        "layer": "mechanical",
        "severity": "warning" if (avg_rels > 10 or total_rels > n*5) else "info",
        "passed": avg_rels <= 10 and total_rels <= n*5,
        "details": f"均值 {avg_rels:.1f} 条/实体, 总计 {total_rels} 条"
    })

    # 命名合规
    non_chinese = [e for e in entities if e["id"].replace("ent_","",1) and not ('一' <= e["id"].replace("ent_","",1)[0] <= '鿿')]
    checks.append({
        "check_name": "实体命名合规",
        "layer": "semantic",
        "severity": "error" if non_chinese else "info",
        "passed": len(non_chinese) == 0,
        "details": f"非中文命名: {len(non_chinese)} 个" if non_chinese else "全部合规",
        "affected_items": non_chinese[:10]
    })

    # 置信度（防御性访问）
    confs = []
    for e in entities:
        q = e.get("quality", {})
        c = q.get("confidence") if isinstance(q, dict) else None
        if c is not None:
            confs.append(c)
    avg_c = sum(confs) / len(confs)
    below_05 = sum(1 for c in confs if c < 0.5)
    below_pct = 100 * below_05 / n
    checks.append({
        "check_name": "置信度扫描",
        "layer": "mechanical",
        "severity": "error" if below_pct > 20 else "info",
        "passed": below_pct <= 20,
        "details": f"均值 {avg_c:.3f}, 低于0.5: {below_05}/{n} ({below_pct:.1f}%)",
        "threshold": {"actual": below_pct, "expected": 20.0}
    })

    return checks, avg_c, 100 * (n - len(orphans)) / n


def check_stage_3(output_dir):
    """Stage 3: Wiki 质量预检"""
    checks = []
    wiki_dir = os.path.join(output_dir, "wiki")
    files = sorted(glob.glob(os.path.join(wiki_dir, "*.md")))

    checks.append({
        "check_name": "骨架完整性预检",
        "layer": "mechanical", "severity": "error",
        "passed": len(files) > 0,
        "details": f"产出 {len(files)} 个 Wiki 页面" if files else "零输出"
    })

    # 抽样 frontmatter 检查
    import random
    sample = random.sample(files, min(3, len(files)))
    fm_ok = 0
    for f in sample:
        with open(f) as fh:
            content = fh.read()
        has_eid = "entity_id:" in content
        has_ver = "version:" in content
        has_status = "status:" in content
        if has_eid and has_ver and has_status:
            fm_ok += 1

    checks.append({
        "check_name": "Frontmatter 完整性",
        "layer": "mechanical",
        "severity": "warning" if fm_ok < len(sample) else "info",
        "passed": fm_ok == len(sample),
        "details": f"抽样 {len(sample)} 个, {fm_ok} 个包含必要 frontmatter 字段"
    })

    return checks, 0.9, 1.0  # Wiki confidence is qualitative


def check_stage_4(output_dir):
    """Stage 4: QA 质量预检"""
    checks = []
    qa_path = os.path.join(output_dir, "qa_pairs.json")

    if not os.path.exists(qa_path):
        checks.append({
            "check_name": "文件存在",
            "layer": "mechanical", "severity": "error", "passed": False,
            "details": "qa_pairs.json 不存在"
        })
        return checks, 0.0, 0.0

    with open(qa_path) as f:
        data = json.load(f)
    qas = data if isinstance(data, list) else data.get("qa_pairs", data.get("items", []))
    n = len(qas)

    checks.append({
        "check_name": "计数",
        "layer": "mechanical", "severity": "error",
        "passed": n > 0,
        "details": f"产出 {n} 个 QA 对" if n else "零输出"
    })

    if not n:
        return checks, 0.0, 0.0

    # 置信度
    confs = []
    source_ok = 0
    for qa in qas:
        q = qa.get("quality", {})
        c = q.get("confidence") if isinstance(q, dict) else qa.get("confidence")
        if c is not None:
            confs.append(c)
        sbs = qa.get("source_block_ids", [])
        if sbs:
            source_ok += 1

    avg_c = sum(confs) / len(confs) if confs else 0
    below_05 = sum(1 for c in confs if c < 0.5)
    below_pct = 100 * below_05 / len(confs) if confs else 0

    checks.append({
        "check_name": "置信度扫描",
        "layer": "mechanical",
        "severity": "error" if below_pct > 20 else "info",
        "passed": below_pct <= 20,
        "details": f"均值 {avg_c:.3f}, 低于0.5: {below_05}/{len(confs)} ({below_pct:.1f}%)",
        "threshold": {"actual": below_pct, "expected": 20.0}
    })

    checks.append({
        "check_name": "追源率",
        "layer": "mechanical",
        "severity": "error" if source_ok < n * 0.5 else "warning" if source_ok < n * 0.8 else "info",
        "passed": source_ok >= n * 0.8,
        "details": f"{source_ok}/{n} ({100*source_ok/n:.1f}%) QA 有 source_block_ids"
    })

    return checks, avg_c, 100 * source_ok / n


def main():
    if len(sys.argv) < 3:
        print("用法: python3 scripts/mechanical-check.py <stage> <output_dir> [--domain <config_path>]", file=sys.stderr)
        sys.exit(2)

    stage = int(sys.argv[1])
    output_dir = sys.argv[2]

    # 解析 --domain 参数
    domain_config = None
    if '--domain' in sys.argv:
        idx = sys.argv.index('--domain')
        if idx + 1 < len(sys.argv):
            domain_config = sys.argv[idx + 1]

    check_fns = {1: check_stage_1, 2: check_stage_2, 3: check_stage_3, 4: check_stage_4}
    if stage not in check_fns:
        print(f"无效 stage: {stage}", file=sys.stderr)
        sys.exit(2)

    if stage == 2:
        checks, avg_confidence, health_score = check_stage_2(output_dir, domain_config)
    else:
        checks, avg_confidence, health_score = check_fns[stage](output_dir)

    errors = [c for c in checks if c["severity"] == "error" and not c["passed"]]
    warnings = [c for c in checks if c["severity"] == "warning" and not c["passed"]]

    report = {
        "report_id": f"stage{stage}-0-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "stage": stage,
        "status": "need_retry" if errors else "passed",
        "retry_count": 0,
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_count": len(checks),
            "passed_count": sum(1 for c in checks if c["passed"]),
            "failed_count": len(errors),
            "avg_confidence": round(avg_confidence, 3)
        },
        "checks": checks,
        "feedback": {
            "instruction_blocks": [
                {
                    "severity": "error",
                    "check": c["check_name"],
                    "affected": c.get("affected_items", []),
                    "instruction": c["details"]
                }
                for c in errors
            ] + [
                {
                    "severity": "warning",
                    "check": c["check_name"],
                    "affected": c.get("affected_items", []),
                    "instruction": c["details"]
                }
                for c in warnings
            ]
        } if (errors or warnings) else {"instruction_blocks": []},
        "output_path": output_dir
    }

    # 保存报告
    reports_dir = os.path.join(output_dir, "quality-reports")
    os.makedirs(reports_dir, exist_ok=True)
    report_path = os.path.join(reports_dir, f"{report['report_id']}.json")
    with open(report_path, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"Stage {stage} 机械预检: {report['status']}")
    print(f"  {len(errors)} errors, {len(warnings)} warnings")
    print(f"  报告: {report_path}")

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
