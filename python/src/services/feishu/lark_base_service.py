"""
飞书多维表格服务 — 基于 lark-cli 本地命令行工具封装。

自动管理「竞品情报数据库」多维表格应用，
提供 6 张数据表的通用 CRUD 操作。

前置条件：
  - 已安装 lark-cli: pip install lark-cli
  - 已配置飞书凭证: lark-cli auth login
"""

from __future__ import annotations

import json
import logging
import subprocess
from typing import Any

logger = logging.getLogger(__name__)

# 6 张数据表定义
TABLES: dict[str, list[dict]] = {
    "Competitor": [
        {"field_name": "竞品名称", "type": "text", "required": True},
        {"field_name": "官网URL", "type": "url"},
        {"field_name": "所属行业", "type": "text"},
        {"field_name": "监控URL列表", "type": "text"},
        {"field_name": "状态", "type": "select", "options": ["活跃", "已归档"]},
        {"field_name": "最近分析时间", "type": "datetime"},
    ],
    "Product": [
        {"field_name": "产品名称", "type": "text", "required": True},
        {"field_name": "所属竞品", "type": "text"},
        {"field_name": "产品类型", "type": "select", "options": ["核心产品", "新产品", "已下线"]},
        {"field_name": "定价模式", "type": "text"},
        {"field_name": "核心功能清单", "type": "text"},
        {"field_name": "目标用户群", "type": "text"},
    ],
    "MarketEvent": [
        {"field_name": "事件标题", "type": "text", "required": True},
        {"field_name": "关联竞品", "type": "text"},
        {"field_name": "事件类型", "type": "select", "options": ["融资", "收购", "产品发布", "人事变动", "合作", "监管", "其他"]},
        {"field_name": "严重级别", "type": "select", "options": ["低", "中", "高", "严重"]},
        {"field_name": "事件摘要", "type": "text"},
        {"field_name": "来源URL", "type": "url"},
        {"field_name": "发生时间", "type": "datetime"},
    ],
    "ComparisonReport": [
        {"field_name": "报告标题", "type": "text", "required": True},
        {"field_name": "分析竞品", "type": "text"},
        {"field_name": "质量评分", "type": "number"},
        {"field_name": "综合评估", "type": "text"},
        {"field_name": "我方综合评分", "type": "number"},
        {"field_name": "竞品综合评分", "type": "number"},
        {"field_name": "引用来源数", "type": "number"},
        {"field_name": "生成时间", "type": "datetime"},
    ],
    "Alert": [
        {"field_name": "告警标题", "type": "text", "required": True},
        {"field_name": "关联竞品", "type": "text"},
        {"field_name": "严重级别", "type": "select", "options": ["低", "中", "高", "严重"]},
        {"field_name": "告警摘要", "type": "text"},
        {"field_name": "推送渠道", "type": "select", "options": ["飞书", "Slack", "钉钉", "邮件"]},
        {"field_name": "推送状态", "type": "select", "options": ["待推送", "已推送", "推送失败"]},
        {"field_name": "创建时间", "type": "datetime"},
    ],
    "MonitorTask": [
        {"field_name": "任务名称", "type": "text", "required": True},
        {"field_name": "目标竞品", "type": "text"},
        {"field_name": "监控类型", "type": "select", "options": ["官网变更", "搜索洞察", "社交媒体", "专利跟踪"]},
        {"field_name": "执行状态", "type": "select", "options": ["待执行", "执行中", "已完成", "失败"]},
        {"field_name": "执行结果摘要", "type": "text"},
        {"field_name": "上次执行时间", "type": "datetime"},
    ],
}


class LarkBaseService:
    """飞书多维表格服务 — 基于 lark-cli base 子命令封装。

    使用示例:
        svc = LarkBaseService()
        await svc.create_competitor_record({
            "竞品名称": "快手电商",
            "官网URL": "https://www.kuaishou.com",
            "所属行业": "直播电商",
            "状态": "活跃",
        })
    """

    def __init__(self, base_token: str = "", table_id: str = ""):
        self._base_token = base_token
        self._table_id = table_id

    # ── 通用 CRUD ──────────────────────────────────────────

    async def create_record(self, table_name: str, record: dict) -> dict:
        """新增一条记录到指定数据表。"""
        return await self._run_cli(
            "base", "+records-create",
            "--table", table_name,
            "--data", json.dumps(record, ensure_ascii=False),
        )

    async def batch_create_records(self, table_name: str, records: list[dict]) -> dict:
        """批量新增多条记录。"""
        return await self._run_cli(
            "base", "+records-batch-create",
            "--table", table_name,
            "--data", json.dumps(records, ensure_ascii=False),
        )

    async def query_records(self, table_name: str, view: str = "", max_results: int = 100) -> list[dict]:
        """查询指定数据表的记录。"""
        args = ["--table", table_name, "--max-results", str(max_results)]
        if view:
            args += ["--view", view]
        result = await self._run_cli("base", "+records-list", *args)
        return result.get("records", []) if isinstance(result, dict) else []

    # ── 便捷方法 ──────────────────────────────────────────

    async def create_competitor_record(self, competitor_data: dict) -> dict:
        """调用 lark-cli base +records-create 新增竞品记录。"""
        return await self.create_record("Competitor", competitor_data)

    async def log_comparison_report(self, report_data: dict) -> dict:
        """将分析报告写入 ComparisonReport 表。"""
        return await self.create_record("ComparisonReport", {
            "报告标题": f"{report_data.get('competitor', '未知')} 竞品分析",
            "分析竞品": report_data.get("competitor", ""),
            "质量评分": report_data.get("quality_score", 0),
            "综合评估": report_data.get("comparison_summary", "")[:500],
            "我方综合评分": report_data.get("our_score", 0),
            "竞品综合评分": report_data.get("competitor_score", 0),
            "引用来源数": report_data.get("total_sources", 0),
            "生成时间": report_data.get("generated_at", ""),
        })

    async def log_alert(self, alert_data: dict) -> dict:
        """将告警写入 Alert 表。"""
        return await self.create_record("Alert", {
            "告警标题": alert_data.get("title", ""),
            "关联竞品": alert_data.get("competitor", ""),
            "严重级别": alert_data.get("severity", "中"),
            "告警摘要": alert_data.get("summary", "")[:300],
            "推送渠道": alert_data.get("channel", "飞书"),
            "推送状态": "已推送" if alert_data.get("sent") else "待推送",
        })

    # ── 内部 cli 调用 ─────────────────────────────────────

    async def _run_cli(self, *args: str) -> dict:
        """执行 lark-cli 命令行并返回 JSON 解析结果。"""
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
                logger.warning(
                    "lark-cli 返回非零: cmd=%s stderr=%s", " ".join(cmd), result.stderr[:200]
                )
            if stdout:
                try:
                    return json.loads(stdout)
                except json.JSONDecodeError:
                    logger.debug("lark-cli 输出非JSON: %s", stdout[:200])
                    return {"raw": stdout}
            return {}
        except subprocess.TimeoutExpired:
            logger.warning("lark-cli 超时: %s", " ".join(cmd))
            return {}
        except FileNotFoundError:
            logger.warning(
                "lark-cli 未安装或不在 PATH 中。请运行: pip install lark-cli && lark-cli auth login"
            )
            return {}
        except Exception as e:
            logger.exception("lark-cli 调用失败")
            return {}
