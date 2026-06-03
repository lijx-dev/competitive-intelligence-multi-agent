"""
飞书多维表格（Bitable）Ontology自动同步服务。

功能：
  1. 读取 .env 里的 FEISHU_BITABLE_APP_TOKEN 配置
  2. 自动创建6个预置数据表
  3. 分析完成后自动把结构化数据全量写入飞书多维表格

6张数据表：
  1. 竞品表（competitor）              — 竞品基础信息
  2. 8维度对比矩阵表（comparison）     — 8维度评分详情
  3. 销售战术卡表（battlecard）        — SWOT + 异议处理
  4. Ontology知识图谱节点表（onto_nodes） — 图谱节点
  5. Ontology关系边表（onto_edges）     — 图谱关系
  6. 分析历史记录表（analysis_log）     — 分析元数据

前置条件：
  - 已安装 lark-cli: pip install lark-cli
  - 已配置 FEISHU_BITABLE_APP_TOKEN 环境变量
  - lark-cli已登录: lark-cli auth login

架构：100%增量新增，零修改原有代码。
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── 6张预置数据表Schema定义 ──────────────────────────────────

BITABLE_SCHEMA: dict[str, list[dict]] = {
    "competitor": [
        {"field_name": "竞品名称", "type": "text", "required": True},
        {"field_name": "所属行业", "type": "text"},
        {"field_name": "状态", "type": "select", "options": ["活跃", "已归档"]},
        {"field_name": "综合评分", "type": "number"},
        {"field_name": "我方综合评分", "type": "number"},
        {"field_name": "关键差异化", "type": "text"},
        {"field_name": "最近分析时间", "type": "datetime"},
    ],
    "comparison": [
        {"field_name": "竞品名称", "type": "text", "required": True},
        {"field_name": "分析维度", "type": "text", "required": True},
        {"field_name": "我方评分", "type": "number"},
        {"field_name": "竞品评分", "type": "number"},
        {"field_name": "差距", "type": "number"},
        {"field_name": "分析说明", "type": "text"},
        {"field_name": "数据来源", "type": "text"},
        {"field_name": "生成时间", "type": "datetime"},
    ],
    "battlecard": [
        {"field_name": "竞品名称", "type": "text", "required": True},
        {"field_name": "卡片类型", "type": "select", "options": ["我方优势", "我方劣势", "竞品优势", "竞品劣势", "核心差异化", "异议处理", "电梯Pitch"]},
        {"field_name": "内容", "type": "text", "required": True},
        {"field_name": "优先级", "type": "select", "options": ["高", "中", "低"]},
        {"field_name": "生成时间", "type": "datetime"},
    ],
    "onto_nodes": [
        {"field_name": "节点ID", "type": "text", "required": True},
        {"field_name": "节点标签", "type": "text", "required": True},
        {"field_name": "所属层级", "type": "select", "options": ["L1-核心实体", "L2-功能/架构", "L3-市场事件", "L4-分析洞察", "L5-执行动作"]},
        {"field_name": "实体类型", "type": "text"},
        {"field_name": "属性JSON", "type": "text"},
        {"field_name": "生成时间", "type": "datetime"},
    ],
    "onto_edges": [
        {"field_name": "关系ID", "type": "text", "required": True},
        {"field_name": "源节点", "type": "text", "required": True},
        {"field_name": "目标节点", "type": "text", "required": True},
        {"field_name": "关系类型", "type": "text"},
        {"field_name": "权重", "type": "number"},
        {"field_name": "生成时间", "type": "datetime"},
    ],
    "analysis_log": [
        {"field_name": "任务ID", "type": "text", "required": True},
        {"field_name": "竞品名称", "type": "text", "required": True},
        {"field_name": "分析模式", "type": "select", "options": ["mock", "real"]},
        {"field_name": "质量评分", "type": "number"},
        {"field_name": "总引用数", "type": "number"},
        {"field_name": "已验证引用数", "type": "number"},
        {"field_name": "可信度", "type": "number"},
        {"field_name": "节点完成数", "type": "number"},
        {"field_name": "执行状态", "type": "select", "options": ["执行中", "已完成", "失败", "部分完成"]},
        {"field_name": "开始时间", "type": "datetime"},
        {"field_name": "完成时间", "type": "datetime"},
    ],
}


class BitableSyncService:
    """飞书多维表格自动同步服务。

    使用示例:
        svc = BitableSyncService()
        await svc.sync_analysis_result(task_id, competitor, analysis_data)
    """

    def __init__(self, app_token: str = ""):
        self._app_token = app_token or os.getenv("FEISHU_BITABLE_APP_TOKEN", "")
        self._initialized = False

    @property
    def configured(self) -> bool:
        return bool(self._app_token)

    # ── 初始化：自动创建6张数据表 ────────────────────────────

    async def ensure_tables(self) -> dict:
        """确保6张预置数据表存在，不存在则自动创建。"""
        if not self.configured:
            logger.info("FEISHU_BITABLE_APP_TOKEN 未配置，跳过Bitable同步")
            return {"ok": False, "reason": "未配置"}

        results = {}
        for table_name, fields in BITABLE_SCHEMA.items():
            try:
                # 先尝试查询表是否存在
                check = await self._run_cli(
                    "base", "+table-list",
                    "--base-token", self._app_token,
                )
                existing = _extract_table_names(check)
                if table_name in existing:
                    results[table_name] = "exists"
                    continue

                # 不存在则创建
                for field in fields:
                    field_def = f"{field['field_name']}:{field['type']}"
                    if field.get("required"):
                        field_def += ":required"
                    if field.get("options"):
                        field_def += f":options={','.join(field['options'])}"

                create_result = await self._run_cli(
                    "base", "+table-create",
                    "--base-token", self._app_token,
                    "--name", table_name,
                    "--fields", json.dumps([{
                        "field_name": f["field_name"],
                        "type": f["type"],
                    } for f in fields], ensure_ascii=False),
                )
                results[table_name] = "created"
                logger.info("Bitable数据表已创建: %s", table_name)
            except Exception as e:
                logger.warning("Bitable数据表 %s 创建失败（优雅降级）: %s", table_name, e)
                results[table_name] = f"error: {str(e)[:100]}"

        self._initialized = True
        return {"ok": True, "tables": results}

    # ── 全量同步分析结果 ─────────────────────────────────────

    async def sync_analysis_result(
        self,
        task_id: str,
        competitor: str,
        analysis_data: dict,
        mode: str = "mock",
    ) -> dict:
        """分析完成后，自动把结构化数据全量写入飞书多维表格。

        Args:
            task_id: 任务ID
            competitor: 竞品名称
            analysis_data: 完整分析结果（PipelineState 字典）
            mode: 分析模式

        Returns:
            {"ok": True/False, "synced": {...}}
        """
        if not self.configured:
            return {"ok": False, "reason": "FEISHU_BITABLE_APP_TOKEN 未配置"}

        if not self._initialized:
            await self.ensure_tables()

        synced: dict[str, int] = {}
        now = datetime.utcnow().isoformat()

        try:
            # 1. 同步竞品表
            matrix = analysis_data.get("comparison_matrix", {}) or {}
            battle = analysis_data.get("battlecard", {}) or {}
            cit = analysis_data.get("citation_report", {}) or {}
            onto = analysis_data.get("ontology_graph", {}) or {}
            review = analysis_data.get("review_feedback", {}) or {}

            our_score = matrix.get("our_overall_score", 0) if isinstance(matrix, dict) else 0
            comp_score = matrix.get("competitor_overall_score", 0) if isinstance(matrix, dict) else 0
            key_diff = battle.get("key_differentiators", []) if isinstance(battle, dict) else []
            quality = analysis_data.get("quality_score", review.get("overall_score", 0) if isinstance(review, dict) else 0)

            await self._create_record("competitor", {
                "竞品名称": competitor,
                "所属行业": "电商",
                "状态": "活跃",
                "综合评分": comp_score,
                "我方综合评分": our_score,
                "关键差异化": "; ".join(str(x)[:100] for x in key_diff[:3]) if key_diff else "",
                "最近分析时间": now,
            })
            synced["competitor"] = 1

            # 2. 同步8维度对比矩阵表
            dimensions = matrix.get("dimensions", []) if isinstance(matrix, dict) else []
            dim_records = []
            for dim in dimensions:
                if not isinstance(dim, dict):
                    continue
                our_s = dim.get("our_score", 0)
                comp_s = dim.get("competitor_score", 0)
                evidence_list = dim.get("evidence", [])
                sources = "; ".join(
                    e.get("source", "") if isinstance(e, dict) else str(e)
                    for e in evidence_list[:3]
                )
                dim_records.append({
                    "竞品名称": competitor,
                    "分析维度": dim.get("dimension", "未知"),
                    "我方评分": our_s,
                    "竞品评分": comp_s,
                    "差距": round(our_s - comp_s, 1),
                    "分析说明": (dim.get("notes", "") or "")[:500],
                    "数据来源": sources[:200],
                    "生成时间": now,
                })
            if dim_records:
                await self._batch_create("comparison", dim_records)
            synced["comparison"] = len(dim_records)

            # 3. 同步战术卡表
            bc_items = []
            if isinstance(battle, dict):
                for item in battle.get("our_strengths", [])[:5]:
                    bc_items.append({"竞品名称": competitor, "卡片类型": "我方优势", "内容": str(item)[:500], "优先级": "高", "生成时间": now})
                for item in battle.get("our_weaknesses", [])[:5]:
                    bc_items.append({"竞品名称": competitor, "卡片类型": "我方劣势", "内容": str(item)[:500], "优先级": "高", "生成时间": now})
                for item in battle.get("competitor_strengths", [])[:5]:
                    bc_items.append({"竞品名称": competitor, "卡片类型": "竞品优势", "内容": str(item)[:500], "优先级": "中", "生成时间": now})
                for item in battle.get("competitor_weaknesses", [])[:5]:
                    bc_items.append({"竞品名称": competitor, "卡片类型": "竞品劣势", "内容": str(item)[:500], "优先级": "中", "生成时间": now})
                for item in battle.get("key_differentiators", [])[:5]:
                    bc_items.append({"竞品名称": competitor, "卡片类型": "核心差异化", "内容": str(item)[:500], "优先级": "高", "生成时间": now})
                for q, a in battle.get("objection_handling", {}).items():
                    bc_items.append({"竞品名称": competitor, "卡片类型": "异议处理", "内容": f"Q: {q}\nA: {str(a)[:400]}", "优先级": "中", "生成时间": now})
                pitch = battle.get("elevator_pitch", "")
                if pitch:
                    bc_items.append({"竞品名称": competitor, "卡片类型": "电梯Pitch", "内容": str(pitch)[:500], "优先级": "高", "生成时间": now})
            if bc_items:
                await self._batch_create("battlecard", bc_items)
            synced["battlecard"] = len(bc_items)

            # 4. 同步Ontology节点表
            if isinstance(onto, dict):
                nodes = onto.get("nodes", [])
                node_records = []
                for n in nodes[:50]:
                    node_records.append({
                        "节点ID": n.get("id", ""),
                        "节点标签": n.get("label", ""),
                        "所属层级": f"L{n.get('layer', '1')}-{n.get('entity_type', '')}",
                        "实体类型": n.get("entity_type", ""),
                        "属性JSON": json.dumps(n.get("properties", {}), ensure_ascii=False)[:500],
                        "生成时间": now,
                    })
                if node_records:
                    await self._batch_create("onto_nodes", node_records)
                synced["onto_nodes"] = len(node_records)

                # 5. 同步Ontology关系表
                edges = onto.get("relations", [])
                edge_records = []
                for e in edges[:50]:
                    edge_records.append({
                        "关系ID": e.get("id", ""),
                        "源节点": e.get("source", ""),
                        "目标节点": e.get("target", ""),
                        "关系类型": e.get("relation_type", ""),
                        "权重": e.get("weight", 1.0),
                        "生成时间": now,
                    })
                if edge_records:
                    await self._batch_create("onto_edges", edge_records)
                synced["onto_edges"] = len(edge_records)

            # 6. 同步分析历史记录表
            await self._create_record("analysis_log", {
                "任务ID": task_id,
                "竞品名称": competitor,
                "分析模式": mode,
                "质量评分": quality,
                "总引用数": cit.get("total_sources", 0) if isinstance(cit, dict) else 0,
                "已验证引用数": cit.get("verified_sources", 0) if isinstance(cit, dict) else 0,
                "可信度": cit.get("overall_reliability_score", 0) if isinstance(cit, dict) else 0,
                "节点完成数": sum(1 for v in synced.values() if isinstance(v, int) and v > 0),
                "执行状态": "已完成",
                "开始时间": now,
                "完成时间": now,
            })
            synced["analysis_log"] = 1

            total = sum(v for v in synced.values() if isinstance(v, int))
            logger.info("Bitable同步完成: %s → %d 条记录", competitor, total)
            return {"ok": True, "synced": synced, "total_records": total}

        except Exception as e:
            logger.warning("Bitable同步异常（优雅降级，不阻塞主流程）: %s", e)
            return {"ok": False, "error": str(e)[:200], "synced": synced}

    # ── 快速查询：检查某竞品是否已同步 ─────────────────────────

    async def check_competitor_exists(self, competitor: str) -> bool:
        """检查竞品是否已存在于多维表格中。"""
        if not self.configured:
            return False
        try:
            result = await self._run_cli(
                "base", "+records-list",
                "--base-token", self._app_token,
                "--table", "competitor",
            )
            records = result.get("records", []) if isinstance(result, dict) else []
            for r in records:
                fields = r.get("fields", {}) if isinstance(r, dict) else {}
                if fields.get("竞品名称") == competitor:
                    return True
            return False
        except Exception:
            return False

    # ── 内部 helpers ─────────────────────────────────────────

    async def _create_record(self, table: str, data: dict) -> dict:
        """新增一条记录。"""
        return await self._run_cli(
            "base", "+records-create",
            "--base-token", self._app_token,
            "--table", table,
            "--data", json.dumps(data, ensure_ascii=False),
        )

    async def _batch_create(self, table: str, records: list[dict]) -> dict:
        """批量新增记录（每次最多100条）。"""
        # 分批发送，每次最多50条
        results = []
        for i in range(0, len(records), 50):
            batch = records[i:i+50]
            try:
                r = await self._run_cli(
                    "base", "+records-batch-create",
                    "--base-token", self._app_token,
                    "--table", table,
                    "--data", json.dumps(batch, ensure_ascii=False),
                )
                results.append(r)
            except Exception as e:
                logger.warning("Bitable批量写入 %s[%d:%d] 失败: %s", table, i, i+50, e)
        return results[0] if results else {}

    async def _run_cli(self, *args: str) -> dict:
        """执行 lark-cli 命令并返回 JSON 结果。"""
        cmd = ["lark-cli"] + list(args)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
            )
            stdout = result.stdout.strip()
            if result.returncode != 0:
                logger.debug("lark-cli 非零退出: cmd=%s stderr=%s", " ".join(cmd)[:100], result.stderr[:200])
            if stdout:
                try:
                    return json.loads(stdout)
                except json.JSONDecodeError:
                    logger.debug("lark-cli 非JSON输出: %s", stdout[:200])
                    return {"raw": stdout}
            return {}
        except subprocess.TimeoutExpired:
            logger.debug("lark-cli 超时: %s", " ".join(cmd)[:100])
            return {}
        except FileNotFoundError:
            logger.debug("lark-cli 未安装或不在PATH中")
            return {}
        except Exception as e:
            logger.debug("lark-cli 调用失败: %s", e)
            return {}


def _extract_table_names(result: dict) -> list[str]:
    """从 lark-cli base +table-list 的输出中提取表名列表。"""
    if not isinstance(result, dict):
        return []
    items = result.get("items") or result.get("tables") or result.get("data") or []
    names = []
    for item in items:
        if isinstance(item, dict):
            name = item.get("name") or item.get("table_name") or item.get("title") or ""
            if name:
                names.append(name)
    return names
