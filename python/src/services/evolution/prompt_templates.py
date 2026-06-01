"""
多模板策略 — 每个 Agent 3 个候选 Prompt 模板，根据历史反馈动态调整权重。

模板评分机制：
  - 初始 performance_score = 0.5
  - 确认正确 → +0.1（上限 1.0）
  - 标记错误 → -0.2（下限 0.0）
  - 选模板时按 score 加权随机，评分越高被选中概率越大
"""

from __future__ import annotations

import random
from typing import Optional

# ── 模板注册表 ──────────────────────────────────────────────────

TEMPLATE_REGISTRY: dict[str, list[dict]] = {
    "research": [
        {
            "id": "research_default",
            "desc": "标准研究 — 5维度均衡覆盖，适合通用竞品分析",
            "performance_score": 0.5,
            "style": "balanced",
        },
        {
            "id": "research_deep",
            "desc": "深度研究 — 侧重技术专利与战略动向，适合技术型竞品",
            "performance_score": 0.5,
            "style": "deep_tech",
        },
        {
            "id": "research_broad",
            "desc": "广度研究 — 侧重市场财务与开源社区，适合商业型竞品",
            "performance_score": 0.5,
            "style": "broad_business",
        },
    ],
    "compare": [
        {
            "id": "compare_default",
            "desc": "标准对比 — 8维度均衡评分，通用性强",
            "performance_score": 0.5,
            "style": "balanced",
        },
        {
            "id": "compare_aggressive",
            "desc": "激进对比 — 放大差异，突出我方优势，适合销售场景",
            "performance_score": 0.5,
            "style": "aggressive",
        },
        {
            "id": "compare_conservative",
            "desc": "保守对比 — 缩小估计区间，强调不确定性，适合内部决策",
            "performance_score": 0.5,
            "style": "conservative",
        },
    ],
    "battlecard": [
        {
            "id": "battlecard_default",
            "desc": "标准战术卡 — 5+3标准结构，适合通用销售场景",
            "performance_score": 0.5,
            "style": "balanced",
        },
        {
            "id": "battlecard_aggressive",
            "desc": "进攻战术卡 — 强调竞品弱点和异议反击，适合竞标场景",
            "performance_score": 0.5,
            "style": "aggressive",
        },
        {
            "id": "battlecard_defensive",
            "desc": "防守战术卡 — 强调我方壁垒和差异化护城河，适合防守场景",
            "performance_score": 0.5,
            "style": "defensive",
        },
    ],
    "reviewer": [
        {
            "id": "reviewer_default",
            "desc": "标准审查 — 4维度均衡评分，通用性强",
            "performance_score": 0.5,
            "style": "balanced",
        },
        {
            "id": "reviewer_strict",
            "desc": "严格审查 — 降低容错阈值，适合高可靠性要求场景",
            "performance_score": 0.5,
            "style": "strict",
        },
        {
            "id": "reviewer_lenient",
            "desc": "宽松审查 — 提高容错阈值，适合快速迭代场景",
            "performance_score": 0.5,
            "style": "lenient",
        },
    ],
}


def get_templates_for_agent(agent_name: str) -> list[dict]:
    """获取某 Agent 的全部候选模板列表"""
    return TEMPLATE_REGISTRY.get(agent_name, [])


def select_template(agent_name: str, competitor: str = "", dimension: str = "") -> Optional[dict]:
    """根据历史 performance_score 加权随机选择最优模板。

    返回选中的模板 dict，若该 Agent 无模板注册则返回 None。
    """
    templates = get_templates_for_agent(agent_name)
    if not templates:
        return None

    scores = [max(t.get("performance_score", 0.5), 0.01) for t in templates]
    total = sum(scores)
    weights = [s / total for s in scores]

    # 加权随机选择
    chosen = random.choices(templates, weights=weights, k=1)[0]
    return chosen


def update_template_score(agent_name: str, template_id: str, is_correct: bool) -> float:
    """根据人类反馈调整模板评分。

    - 确认正确 → +0.1（上限 1.0）
    - 标记错误 → -0.2（下限 0.0）
    返回更新后的 score。
    """
    templates = get_templates_for_agent(agent_name)
    for t in templates:
        if t["id"] == template_id:
            old = t["performance_score"]
            if is_correct:
                t["performance_score"] = min(1.0, old + 0.10)
            else:
                t["performance_score"] = max(0.0, old - 0.20)
            return t["performance_score"]
    return 0.0


def get_template_performance(agent_name: str) -> list[dict]:
    """获取某 Agent 全部模板的当前评分排行（按 score 降序）"""
    templates = get_templates_for_agent(agent_name)
    return sorted(
        [{"id": t["id"], "desc": t["desc"], "score": t["performance_score"]} for t in templates],
        key=lambda x: x["score"],
        reverse=True,
    )


def get_all_template_performance() -> dict[str, list[dict]]:
    """获取所有 Agent 的模板评分排行"""
    return {agent: get_template_performance(agent) for agent in TEMPLATE_REGISTRY}
