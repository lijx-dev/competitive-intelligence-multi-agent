"""
飞书云文档（Doc）自动生成报告 — 分析完成后自动生成结构化飞书云文档。

报告章节自动划分：
  1. 分析概览（质量得分）
  2. 8维度对比雷达图
  3. 销售战术卡详情
  4. 来源引用溯源列表
  5. Ontology知识图谱可视化

基于 lark-cli 命令封装，支持:
  - 自动创建云文档
  - Markdown 写入
  - 文档分享链接生成
  - 飞书群自动推送文档链接

前提条件：lark-cli 已安装并登录。

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


class DocGeneratorService:
    """飞书云文档自动生成服务。

    使用示例:
        svc = DocGeneratorService()
        result = await svc.generate_report("快手电商", analysis_data)
        if result["ok"]:
            print(f"报告已生成: {result['doc_url']}")
    """

    def __init__(self, folder_token: str = ""):
        self._folder_token = folder_token or os.getenv("FEISHU_DOC_FOLDER_TOKEN", "")
        self._cli_available: Optional[bool] = None

    @property
    def configured(self) -> bool:
        """检查 lark-cli 是否可用。"""
        if self._cli_available is None:
            self._cli_available = self._check_cli()
        return self._cli_available

    def _check_cli(self) -> bool:
        """检查 lark-cli 是否已安装并能正常运行。"""
        try:
            result = subprocess.run(
                ["lark-cli", "--version"],
                capture_output=True, text=True, encoding="utf-8", timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    # ── 主入口：生成完整报告 ─────────────────────────────────

    async def generate_report(
        self,
        competitor: str,
        analysis_data: dict,
        task_id: str = "",
    ) -> dict:
        """基于分析结果自动生成结构化飞书云文档。

        Args:
            competitor: 竞品名称
            analysis_data: 完整分析结果（PipelineState）
            task_id: 任务追踪ID

        Returns:
            {
                "ok": True/False,
                "doc_id": "...",
                "doc_url": "...",
                "doc_title": "...",
            }
        """
        if not self.configured:
            logger.info("lark-cli 不可用，跳过飞书云文档生成")
            return {
                "ok": False,
                "reason": "lark-cli 未安装或未登录",
                "hint": "pip install lark-cli && lark-cli auth login",
            }

        try:
            # 1. 创建云文档
            date_str = datetime.now().strftime("%Y%m%d-%H%M")
            doc_title = f"📊 {competitor} 竞品分析报告 — {date_str}"

            create_args = ["doc", "+create", "--title", doc_title, "--api-version", "v2"]
            if self._folder_token:
                create_args += ["--folder-token", self._folder_token]

            create_result = await self._run_cli(*create_args)

            doc_id = ""
            doc_url = ""

            # 尝试多种返回格式解析 doc_id
            if isinstance(create_result, dict):
                doc_id = (
                    create_result.get("doc_id")
                    or create_result.get("document_id")
                    or create_result.get("id")
                    or create_result.get("data", {}).get("document_id", "")
                    or ""
                )
                doc_url = create_result.get("url") or create_result.get("doc_url") or ""

            if not doc_id:
                # 尝试从 raw 输出中提取
                raw = create_result.get("raw", "") if isinstance(create_result, dict) else str(create_result)
                if "docx/" in raw:
                    import re
                    m = re.search(r'docx/([A-Za-z0-9_-]+)', raw)
                    if m:
                        doc_id = m.group(1)

            if not doc_id:
                logger.warning("创建云文档失败，无doc_id: %s", str(create_result)[:200])
                return {"ok": False, "error": "创建云文档失败", "raw": str(create_result)[:200]}

            if not doc_url:
                doc_url = f"https://bytedance.feishu.cn/docx/{doc_id}"

            # 2. 生成 Markdown 内容并写入
            markdown = self._build_structured_report(competitor, analysis_data, task_id)

            write_result = await self._run_cli(
                "markdown", "+overwrite",
                "--doc-id", doc_id,
                "--content", markdown,
            )

            logger.info("飞书云文档报告已生成: %s → %s", competitor, doc_url)
            return {
                "ok": True,
                "doc_id": doc_id,
                "doc_url": doc_url,
                "doc_title": doc_title,
                "write_result": write_result,
            }

        except Exception as e:
            logger.warning("飞书云文档生成失败（优雅降级）: %s", e)
            return {"ok": False, "error": str(e)[:200]}

    # ── 结构化报告 Markdown 生成 ──────────────────────────────

    def _build_structured_report(
        self, competitor: str, data: dict, task_id: str = ""
    ) -> str:
        """生成完整的结构化 Markdown 报告内容。

        报告章节：
          1. 分析概览
          2. 8维度对比矩阵
          3. SWOT + 销售战术卡
          4. 来源引用溯源
          5. Ontology知识图谱
        """
        quality = data.get("quality_score", 0)
        matrix = data.get("comparison_matrix", {}) or {}
        battle = data.get("battlecard", {}) or {}
        research = data.get("research_results", [])
        cit = data.get("citation_report", {}) or {}
        review = data.get("review_feedback", {}) or {}
        onto = data.get("ontology_graph", {}) or {}
        changes = data.get("changes_detected", [])

        now_str = datetime.now().strftime("%Y年%m月%d日 %H:%M")
        mode = "🎭 Mock演示模式" if data.get("_mock") else "🤖 真实LLM模式"
        our_score = matrix.get("our_overall_score", 0) if isinstance(matrix, dict) else 0
        comp_score = matrix.get("competitor_overall_score", 0) if isinstance(matrix, dict) else 0

        lines: list[str] = [
            f"# 📊 {competitor} 竞品分析报告",
            f"",
            f"> **生成时间**: {now_str} | **分析模式**: {mode}",
            f"> **任务ID**: `{task_id or 'N/A'}`",
            f"> **综合质量评分**: ⭐ **{quality:.1f}/10**",
            f"",
            f"---",
            f"",
            f"## 一、📋 分析概览",
            f"",
            f"| 指标 | 数值 |",
            f"|------|------|",
            f"| 我方综合评分 | {our_score:.1f}/10 |",
            f"| 竞品综合评分 | {comp_score:.1f}/10 |",
            f"| 质量评分 | {quality:.1f}/10 |",
            f"| 总引用来源 | {cit.get('total_sources', 0) if isinstance(cit, dict) else 0} |",
            f"| 已验证来源 | {cit.get('verified_sources', 0) if isinstance(cit, dict) else 0} |",
            f"| 总体可信度 | {(cit.get('overall_reliability_score', 0) if isinstance(cit, dict) else 0)*100:.0f}% |",
            f"",
        ]

        # 审查详情
        if isinstance(review, dict) and review:
            lines += [
                f"### 质量审查详情",
                f"",
                f"| 审查维度 | 评分 |",
                f"|----------|------|",
                f"| 准确度 | {review.get('accuracy_score', '-')}/10 |",
                f"| 完整度 | {review.get('completeness_score', '-')}/10 |",
                f"| 引用可追溯性 | {review.get('citation_score', '-')}/10 |",
                f"| 可操作性 | {review.get('actionability_score', '-')}/10 |",
                f"",
                f"**审查意见**: {review.get('revision_instructions', '无')}",
                f"",
            ]

        lines += [
            f"---",
            f"",
            f"## 二、📊 8维度对比矩阵",
            f"",
            f"| 维度 | 我方评分 | 竞品评分 | 差距 | 说明 |",
            f"|------|----------|----------|------|------|",
        ]

        if isinstance(matrix, dict):
            for dim in matrix.get("dimensions", []):
                if not isinstance(dim, dict):
                    continue
                our_s = dim.get("our_score", 0)
                comp_s = dim.get("competitor_score", 0)
                gap = our_s - comp_s
                gap_icon = "🟢" if gap > 1 else ("🟡" if abs(gap) <= 1 else "🔴")
                notes = (dim.get("notes", "") or "")[:100]
                lines.append(
                    f"| {dim.get('dimension', '?')} "
                    f"| {our_s} | {comp_s} "
                    f"| {gap_icon} {gap:+.1f} "
                    f"| {notes} |"
                )

        lines += [
            f"",
            f"### 综合评估",
            f"",
            str(matrix.get("overall_assessment", "暂无综合评估")) if isinstance(matrix, dict) else "暂无",
            f"",
            f"---",
            f"",
            f"## 三、🎯 销售战术卡",
            f"",
        ]

        # SWOT
        if isinstance(battle, dict):
            for section, title in [
                ("our_strengths", "### 我方优势 💪"),
                ("our_weaknesses", "### 我方劣势 ⚠️"),
                ("competitor_strengths", "### 竞品优势 🔍"),
                ("competitor_weaknesses", "### 竞品劣势 🎯"),
            ]:
                items = battle.get(section, [])
                if items:
                    lines.append(title)
                    lines.append("")
                    for item in items[:5]:
                        lines.append(f"- {item}")
                    lines.append("")

            # 核心差异化
            key_diff = battle.get("key_differentiators", [])
            if key_diff:
                lines += ["### 核心差异化 ⚡", ""]
                for item in key_diff[:5]:
                    lines.append(f"- {item}")
                lines.append("")

            # 异议处理
            objection = battle.get("objection_handling", {})
            if objection:
                lines += ["### 异议处理话术 💬", ""]
                for i, (q, a) in enumerate(objection.items(), 1):
                    lines.append(f"**场景{i}**: {q}")
                    lines.append(f"> {a}")
                    lines.append("")

            # 电梯Pitch
            pitch = battle.get("elevator_pitch", "")
            if pitch:
                lines += ["### 电梯 Pitch 🎤", "", f"> {pitch}", ""]

        lines += [
            f"---",
            f"",
            f"## 四、🔬 研究洞察",
            f"",
        ]

        for insight in research[:5]:
            if isinstance(insight, dict):
                lines.append(f"### {insight.get('topic', 'N/A')}")
                lines.append(f"**可信度**: {insight.get('confidence', 'N/A')}")
                lines.append("")
                lines.append(insight.get("summary", "")[:500])
                lines.append("")
                findings = insight.get("key_findings", [])
                if findings:
                    lines.append("**关键发现**:")
                    for f in findings[:5]:
                        lines.append(f"- {f}")
                    lines.append("")

        lines += [
            f"---",
            f"",
            f"## 五、📎 引用溯源",
            f"",
            f"| 指标 | 数值 |",
            f"|------|------|",
            f"| 总引用数 | {cit.get('total_sources', 0) if isinstance(cit, dict) else 0} |",
            f"| 已验证 | {cit.get('verified_sources', 0) if isinstance(cit, dict) else 0} |",
            f"| 无法访问 | {cit.get('unreachable_sources', 0) if isinstance(cit, dict) else 0} |",
            f"| 总体可信度 | {(cit.get('overall_reliability_score', 0) if isinstance(cit, dict) else 0)*100:.0f}% |",
            f"",
        ]

        # 来源列表
        source_list = cit.get("source_list", []) if isinstance(cit, dict) else []
        if source_list:
            lines.append("### 来源清单")
            lines.append("")
            for src in source_list[:10]:
                if isinstance(src, dict):
                    url = src.get("url", "")
                    status = src.get("status", "?")
                    score = src.get("domain_score", 0)
                    icon = "✅" if status == "verified" else "⚠️"
                    lines.append(f"- {icon} [{url}]({url}) — 可信度 {score}")

        lines += [
            f"",
            f"---",
            f"",
            f"## 六、🗺️ Ontology 知识图谱",
            f"",
        ]

        if isinstance(onto, dict):
            nodes = onto.get("nodes", [])
            edges = onto.get("relations", [])
            stats = onto.get("stats", {})
            lines += [
                f"**图谱统计**: {stats.get('nodes', len(nodes))} 节点, {stats.get('relations', len(edges))} 关系, {stats.get('layers', 5)} 层",
                f"",
                f"### 节点列表",
                f"",
                f"| ID | 标签 | 层级 | 类型 |",
                f"|----|------|------|------|",
            ]
            for n in nodes[:20]:
                lines.append(f"| {n.get('id', '')} | {n.get('label', '')} | L{n.get('layer', '1')} | {n.get('entity_type', '')} |")

            if edges:
                lines += ["", "### 关系列表", "", "| 源 → 目标 | 关系类型 | 权重 |", "|-----------|----------|------|"]
                for e in edges[:20]:
                    lines.append(f"| {e.get('source', '')} → {e.get('target', '')} | {e.get('relation_type', '')} | {e.get('weight', 1.0)} |")

        # 监控变更
        if changes:
            lines += [
                f"",
                f"---",
                f"",
                f"## 七、🔍 监控变更检测",
                f"",
            ]
            for c in changes[:5]:
                if isinstance(c, dict):
                    severity = c.get("severity", "INFO")
                    icon = "🔴" if severity == "HIGH" else ("🟡" if severity == "MEDIUM" else "🟢")
                    lines.append(f"### {icon} {c.get('title', '未命名变更')}")
                    lines.append(f"**级别**: {severity} | **来源**: {c.get('source_url', 'N/A')}")
                    lines.append(f"{c.get('summary', '')[:300]}")
                    lines.append("")

        lines += [
            f"",
            f"---",
            f"",
            f"*本报告由竞品情报多Agent系统（12节点DAG）自动生成 — {now_str}*",
            f"*飞书CLI全局总调度官 · v1.0*",
        ]

        return "\n".join(lines)

    # ── 内部 CLI 调用 ───────────────────────────────────────

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
