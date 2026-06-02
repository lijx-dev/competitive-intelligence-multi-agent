"""Agent 协作协议 — 结构化打回消息 + 下游依赖声明 + 增量重生成触发器。

实现比赛要求的「信息采集打回重执行」回路内核：
- AgentRefusalNotice: 上游Agent发现关键维度缺失时，向Research Agent发送标准打回消息
- DownstreamDependencyMap: 声明每个Agent的输出被哪些下游消费，用于增量重生成
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── 打回消息类型 ──
class RefusalIssueType(str, Enum):
    DATA_MISSING = "data_missing"        # 关键维度数据缺失
    DATA_CONFLICT = "data_conflict"      # 多源数据冲突
    SOURCE_INVALID = "source_invalid"    # 来源不可信


class AgentRefusalNotice(BaseModel):
    """标准结构化打回消息 — 上游Agent要求Research Agent重新采集。

    由 FactCheck / SchemaValidation / Reviewer 节点发出，
    LangGraph conditional edge 路由回 Research Agent。
    """
    target_agent: Literal["research_agent"] = "research_agent"
    issue_type: RefusalIssueType
    missing_dimensions: list[str] = Field(
        default_factory=list,
        description="明确列出缺少的维度名称，如 ['pricing_tier', 'user_persona', 'feature_tree']",
    )
    correction_suggestion: str = Field(
        default="",
        description="给 Research Agent 的修正建议，告诉它具体需要补充什么数据",
    )
    severity: Literal["low", "medium", "high", "critical"] = "medium"

    # ── 来源追踪（供可观测性） ──
    source_agent: str = Field(default="", description="发出打回的Agent名称")
    source_node: str = Field(default="", description="发出打回的具体节点")


# ── 下游依赖映射（支持增量重生成） ──
class DownstreamDependencyMap:
    """声明每个 Agent 节点的输出被哪些下游节点消费。

    当用户在 Web 界面编辑某个字段后，系统据此识别受影响的下游节点，
    只重执行相关节点而非全 DAG，实现秒级增量更新。
    """

    # agent_output_field → list of downstream agent names
    DEPENDENCIES: dict[str, list[str]] = {
        "changes_detected":      ["research", "fact_check"],
        "research_results":      ["fact_check", "compare", "battlecard", "reviewer"],
        "comparison_matrix":     ["battlecard", "reviewer"],
        "battlecard":            ["reviewer", "citation", "feishu_push"],
        "review_feedback":       ["targeted_fix"],
        "fact_check_result":     ["compare", "reviewer"],
        "citation_report":       ["feishu_push"],
    }

    @classmethod
    def get_downstream_agents(cls, field_name: str) -> list[str]:
        """返回消费指定字段的所有下游 Agent 名称列表。"""
        return cls.DEPENDENCIES.get(field_name, [])

    @classmethod
    def get_full_downstream_chain(cls, field_name: str) -> list[str]:
        """递归获取完整下游链（含二级/三级依赖）。"""
        visited: set[str] = set()
        result: list[str] = []
        queue = [field_name]
        while queue:
            current = queue.pop(0)
            for dep in cls.get_downstream_agents(current):
                if dep not in visited:
                    visited.add(dep)
                    result.append(dep)
                    queue.append(dep)
        return result


# ── 增量重生成触发请求 ──
class IncrementalRegenRequest(BaseModel):
    """用户编辑报告后触发的增量重生成请求。

    Frontend → POST /api/v1/pipeline/regen → 只重跑受影响的下游节点。
    """
    pipeline_run_id: str = Field(description="原始分析任务ID")
    edited_field: str = Field(description="用户编辑的字段路径，如 'battlecard.our_strengths'")
    new_value: str = Field(description="用户修改后的新值")
    upstream_agent: str = Field(default="", description="该字段所属的Agent名称")

    @property
    def affected_agents(self) -> list[str]:
        """自动计算需要重执行的下游Agent列表。"""
        field_root = self.edited_field.split(".")[0]
        return DownstreamDependencyMap.get_full_downstream_chain(field_root)
