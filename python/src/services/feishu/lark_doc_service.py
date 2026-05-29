"""
飞书云文档服务 — 基于 lark-cli 自动生成结构化竞品分析报告。

前置条件：
  - 已安装 lark-cli: pip install lark-cli
  - 已配置飞书凭证: lark-cli auth login
"""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime

logger = logging.getLogger(__name__)


class LarkDocService:
    """飞书云文档报告生成服务 — lark-cli doc/markdown 子命令封装。

    使用示例:
        svc = LarkDocService()
        result = await svc.create_report("快手电商", analysis_result)
        print(result.get("doc_url"))
    """

    async def create_report(self, competitor: str, analysis_result: dict) -> dict:
        """基于分析结果生成飞书云文档。

        步骤：创建文档 → 写入 Markdown 内容 → 返回文档 URL。
        """
        # 1. 创建云文档
        doc_title = f"{competitor} 竞品分析报告 — {datetime.now().strftime('%Y%m%d')}"
        doc_result = await self._run_cli(
            "doc", "+create",
            "--title", doc_title,
        )
        doc_id = doc_result.get("doc_id") or doc_result.get("id") or ""

        if not doc_id:
            return {"ok": False, "error": "创建云文档失败", "raw": doc_result}

        # 2. 生成 Markdown 内容
        markdown = self._build_report_markdown(competitor, analysis_result)

        # 3. 写入 Markdown
        write_result = await self._run_cli(
            "markdown", "+overwrite",
            "--doc-id", doc_id,
            "--content", markdown,
        )

        doc_url = f"https://bytedance.feishu.cn/docx/{doc_id}"
        return {
            "ok": True,
            "doc_id": doc_id,
            "doc_url": doc_url,
            "write_result": write_result,
        }

    # ── Markdown 报告生成 ──────────────────────────────────

    def _build_report_markdown(self, competitor: str, result: dict) -> str:
        quality = result.get("quality_score", 0)
        matrix = result.get("comparison_matrix", {})
        battle = result.get("battlecard", {})
        research = result.get("research_results", [])
        cit = result.get("citation_report", {})
        review = result.get("review_feedback", {})

        md: list[str] = [
            f"# {competitor} 竞品分析报告",
            f"",
            f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"> 质量评分：{quality}/10",
            f"",
            "---",
            "",
            "## 一、执行摘要",
            "",
            matrix.get("overall_assessment", "暂无综合评估") if isinstance(matrix, dict) else "暂无",
            "",
            "---",
            "",
            "## 二、8 维度对比矩阵",
            "",
            "| 维度 | 我方评分 | 竞品评分 | 说明 |",
            "|------|---------|----------|------|",
        ]

        if isinstance(matrix, dict):
            for dim in matrix.get("dimensions", []):
                md.append(
                    f"| {dim.get('dimension', '?')} "
                    f"| {dim.get('our_score', '-')} "
                    f"| {dim.get('competitor_score', '-')} "
                    f"| {str(dim.get('notes', ''))[:80]} |"
                )

        md += [
            "",
            "---",
            "",
            "## 三、SWOT 分析",
            "",
            "### 我方优势",
        ]
        if isinstance(battle, dict):
            for item in battle.get("our_strengths", [])[:5]:
                md.append(f"- {item}")
            md += ["", "### 我方劣势"]
            for item in battle.get("our_weaknesses", [])[:5]:
                md.append(f"- {item}")
            md += ["", "### 竞品优势"]
            for item in battle.get("competitor_strengths", [])[:5]:
                md.append(f"- {item}")
            md += ["", "### 竞品劣势"]
            for item in battle.get("competitor_weaknesses", [])[:5]:
                md.append(f"- {item}")

            key_diff = battle.get("key_differentiators", [])
            if key_diff:
                md += ["", "## 四、核心差异化"]
                for item in key_diff[:5]:
                    md.append(f"- {item}")

            pitch = battle.get("elevator_pitch", "")
            if pitch:
                md += ["", "## 五、电梯 Pitch", "", f"> {pitch}"]

        md += [
            "",
            "---",
            "",
            "## 六、研究洞察",
        ]
        for insight in research[:5]:
            if isinstance(insight, dict):
                md.append(f"### {insight.get('topic', 'N/A')}")
                md.append(insight.get("summary", "")[:300])
                for f in insight.get("key_findings", [])[:3]:
                    md.append(f"- {f}")
                md.append("")

        md += [
            "---",
            "",
            "## 七、引用溯源",
            "",
            f"- 总引用数：{cit.get('total_sources', 0) if isinstance(cit, dict) else 0}",
            f"- 已验证：{cit.get('verified_sources', 0) if isinstance(cit, dict) else 0}",
            f"- 总体可信度：{(cit.get('overall_reliability_score', 0) if isinstance(cit, dict) else 0)*100:.0f}%",
            "",
            "---",
            "",
            "## 八、质量审查",
            "",
            f"- 综合评分：{review.get('overall_score', 0) if isinstance(review, dict) else quality}/10",
            f"- 审查状态：{'通过' if (review.get('approved', False) if isinstance(review, dict) else False) else '需修复'}",
            "",
            f"*本报告由多 Agent 竞品情报分析系统自动生成*",
        ]

        return "\n".join(md)

    # ── 内部 CLI 调用 ─────────────────────────────────────

    async def _run_cli(self, *args: str) -> dict:
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
                    "lark-cli 非零退出: cmd=%s stderr=%s", " ".join(cmd), result.stderr[:200]
                )
            if stdout:
                try:
                    return json.loads(stdout)
                except json.JSONDecodeError:
                    logger.debug("lark-cli 非JSON输出: %s", stdout[:200])
                    return {"raw": stdout}
            return {}
        except subprocess.TimeoutExpired:
            logger.warning("lark-cli 超时: %s", " ".join(cmd))
            return {}
        except FileNotFoundError:
            logger.warning("lark-cli 未安装或不在 PATH 中")
            return {}
        except Exception as e:
            logger.exception("lark-cli 调用失败")
            return {}
