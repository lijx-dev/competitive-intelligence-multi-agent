"""
飞书自然语言命令解析器 — 从飞书用户发来的纯文本消息里自动提取竞品名称。

支持两种格式：
  1. 纯自然语言："分析一下快手电商" / "帮我做SHEIN竞品分析"
  2. 结构化快捷命令：/ci 快手电商

输出结构化解析结果：{competitor: str, urls: list[str], mode: "mock"|"real"}

新增功能（100%增量，零修改原有代码）。
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ── 竞品关键词库（可扩展，支持中文/英文）─────────────────────
BUILTIN_COMPETITOR_PATTERNS: list[tuple[str, str]] = [
    # (匹配正则, 标准化名称)
    (r"快手(?:电商)?", "快手电商"),
    (r"抖音(?:电商)?", "抖音电商"),
    (r"拼多多|temu", "Temu"),
    (r"shein|希音", "SHEIN"),
    (r"阿里(?:巴巴)?(?:电商)?|淘宝|天猫", "阿里电商AI"),
    (r"京东(?:电商)?", "京东电商"),
    (r"小红书(?:电商)?", "小红书电商"),
    (r"美团(?:电商)?", "美团电商"),
    (r"amazon|亚马逊", "Amazon"),
    (r"shopee", "Shopee"),
    (r"lazada", "Lazada"),
    (r"notion", "Notion"),
    (r"crayon", "Crayon"),
    (r"klue", "Klue"),
    (r"kompyte", "Kompyte"),
]

# ── 命令触发模式 ──────────────────────────────────────────────
# 快捷命令：/ci <竞品名称>
QUICK_COMMAND_RE = re.compile(r"^/ci\s+(.+)$", re.IGNORECASE)
# 命令格式：分析|竞品分析|帮我分析|做竞品分析
NATURAL_LANG_TRIGGERS = [
    r"分析(?:\p{L}+)*(?:一下|下)?(.+)",
    r"(.+?)(?:的)?竞品分析",
    r"帮我(?:\p{L}+)*(?:分析|做|查|搜)(.+)",
    r"(?:做|查|搜)(.+)(?:的)?(?:竞品)?分析",
    r"我要分析(.+)",
    r"研究(?:\p{L}+)*(?:一下|下)?(.+)",
    r"对比(.+?)(?:和|vs|与)(.+)",
]


def parse_feishu_command(text: str, *, default_mode: str = "mock") -> dict[str, Any]:
    """解析飞书用户发来的自然语言文本，提取竞品名称和模式。

    Args:
        text: 飞书用户原始消息文本
        default_mode: 未指定模式时的默认值 ("mock" 或 "real")

    Returns:
        {
            "competitor": str,      # 提取的竞品名称（标准化后）
            "urls": list[str],      # 可选的额外URL列表
            "mode": "mock"|"real",  # 分析模式
            "raw_text": str,        # 原始输入（调试用）
            "matched_pattern": str, # 匹配到的模式类型
        }
    """
    result: dict[str, Any] = {
        "competitor": "",
        "urls": [],
        "mode": default_mode,
        "raw_text": text.strip(),
        "matched_pattern": "unknown",
    }

    if not text or not text.strip():
        logger.debug("空文本，跳过命令解析")
        return result

    cleaned = text.strip()

    # ── 1. 检查结构化快捷命令 /ci ──
    quick_match = QUICK_COMMAND_RE.match(cleaned)
    if quick_match:
        target = quick_match.group(1).strip()
        result["competitor"] = _normalize_competitor_name(target)
        result["matched_pattern"] = "quick_command"
        result["mode"] = _extract_mode(cleaned, default_mode)
        logger.info("快捷命令解析: /ci → %s", result["competitor"])
        return result

    # ── 2. 尝试自然语言模式匹配 ──
    for pattern in NATURAL_LANG_TRIGGERS:
        try:
            match = re.search(pattern, cleaned, re.IGNORECASE)
            if match:
                # 取第一个非空捕获组作为竞品名称
                for group in match.groups():
                    if group and group.strip():
                        result["competitor"] = _normalize_competitor_name(group.strip())
                        result["matched_pattern"] = "natural_language"
                        break
                if result["competitor"]:
                    result["mode"] = _extract_mode(cleaned, default_mode)
                    logger.info("自然语言解析: '%s' → %s", cleaned[:50], result["competitor"])
                    return result
        except re.error:
            continue

    # ── 3. 关键词直接匹配（兜底）──
    for pattern, standard_name in BUILTIN_COMPETITOR_PATTERNS:
        try:
            if re.search(pattern, cleaned, re.IGNORECASE):
                result["competitor"] = standard_name
                result["matched_pattern"] = "keyword_match"
                result["mode"] = _extract_mode(cleaned, default_mode)
                logger.info("关键词匹配: '%s' → %s", cleaned[:50], result["competitor"])
                return result
        except re.error:
            continue

    # ── 4. 完全无法识别时，取文本中看起来像名称的部分 ──
    # 去除常见口语词后取前8个字符
    noise_words = [
        "分析一下", "帮我", "做一下", "的", "一下", "下", "分析",
        "竞品", "研究", "帮我做", "我想要", "请", "麻烦", "帮",
        "hello", "hi", "你好", "帮我分析",
    ]
    candidate = cleaned
    for noise in sorted(noise_words, key=len, reverse=True):
        candidate = candidate.replace(noise, "")
    candidate = candidate.strip().strip("，。！？,!? ")

    if candidate and len(candidate) >= 2:
        result["competitor"] = candidate[:30]
        result["matched_pattern"] = "fallback_extraction"
        logger.info("兜底提取: '%s' → '%s'", cleaned[:50], result["competitor"])
    else:
        logger.warning("无法从文本中提取竞品名称: '%s'", cleaned[:100])

    result["mode"] = _extract_mode(cleaned, default_mode)
    return result


def _normalize_competitor_name(raw: str) -> str:
    """标准化竞品名称：去除空白、括号、引号等干扰字符。"""
    name = raw.strip()
    # 去除引号
    name = name.strip('"\'""''「」『』')
    # 去除尾部的"的"和"分析"等词
    for suffix in ["的分析", "的竞品分析", "竞品分析", "分析", "的"]:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    # 去除中文标点
    name = re.sub(r"[，。！？、；：""''（）《》【】]$", "", name)
    # 限制长度
    if len(name) > 50:
        name = name[:50]
    # 尝试匹配内置关键词库
    for pattern, standard in BUILTIN_COMPETITOR_PATTERNS:
        try:
            if re.search(pattern, name, re.IGNORECASE):
                return standard
        except re.error:
            continue
    return name.strip() or raw.strip()[:30]


def _extract_mode(text: str, default: str = "mock") -> str:
    """从文本中检测用户是否指定了分析模式。"""
    text_lower = text.lower()
    real_keywords = ["真实", "真实模式", "real", "生产", "正式", "线上", "实际"]
    mock_keywords = ["mock", "演示", "demo", "模拟", "测试", "test"]
    for kw in real_keywords:
        if kw in text_lower:
            return "real"
    for kw in mock_keywords:
        if kw in text_lower:
            return "mock"
    return default


# ── 交互式确认卡片生成函数 ───────────────────────────────────

def build_confirmation_card(
    competitor: str,
    mode: str = "mock",
    task_id: str = "",
) -> dict:
    """生成飞书交互式确认卡片。

    用户发送命令后立即回复此卡片，包含确认/取消按钮。

    Args:
        competitor: 解析出的竞品名称
        mode: 分析模式（mock/real）
        task_id: 任务ID（用于追踪）

    Returns:
        飞书交互卡片消息体（兼容飞书开放平台规范）
    """
    import json as _json
    from datetime import datetime

    mode_label = "🎭 演示模式（Mock，3秒完成）" if mode == "mock" else "🤖 真实LLM模式（约60秒）"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    card = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True, "enable_forward": True},
            "header": {
                "template": "blue",
                "title": {
                    "tag": "plain_text",
                    "content": f"✅ 已收到竞品分析指令",
                },
            },
            "elements": [
                {
                    "tag": "div",
                    "fields": [
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**目标竞品**\n📌 {competitor}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**分析模式**\n{mode_label}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**任务ID**\n`{task_id or 'auto-generated'}`"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**发起时间**\n🕐 {now_str}"}},
                    ],
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": (
                        "系统将通过 **12节点DAG** 自动执行以下分析流程：\n"
                        "Monitor → Research(5维) → FactCheck → Compare(8维) → Battlecard → Reviewer → Citation → Ontology\n\n"
                        "预计耗时：**3-5秒（Mock模式）** / **60秒（真实模式）**"
                    )},
                },
                {"tag": "hr"},
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "🚀 确认开始分析"},
                            "type": "primary",
                            "value": _json.dumps({
                                "action": "confirm_analysis",
                                "competitor": competitor,
                                "mode": mode,
                                "task_id": task_id or "",
                            }, ensure_ascii=False),
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "❌ 取消任务"},
                            "type": "danger",
                            "value": _json.dumps({
                                "action": "cancel_analysis",
                                "task_id": task_id or "",
                            }, ensure_ascii=False),
                        },
                    ],
                },
                {
                    "tag": "note",
                    "elements": [
                        {"tag": "plain_text", "content": "💡 提示：分析完成后会自动推送报告卡片 + 飞书云文档链接到此群"},
                    ],
                },
            ],
        },
    }
    return card


def build_progress_card(
    competitor: str,
    task_id: str,
    node_statuses: dict[str, str],  # node_name → "pending"|"running"|"completed"|"failed"
    mode: str = "mock",
) -> dict:
    """生成分析进度卡片（12节点状态实时展示）。

    灰色 = 未开始，蓝色 = 执行中，绿色 = 已完成，红色 = 失败
    """
    import json as _json

    # 12 个 DAG 节点定义
    DAG_NODES = [
        ("monitor", "🔍 网页监控"),
        ("alert", "🚨 告警检测"),
        ("research", "📚 5维深度研究"),
        ("multimodal", "🖼️ 多模态分析"),
        ("fact_check", "🔬 交叉验证"),
        ("compare", "📊 8维对比矩阵"),
        ("schema_validation", "✅ Schema校验"),
        ("battlecard", "🎯 销售战术卡"),
        ("reviewer", "📋 质量审查"),
        ("targeted_fix", "🔧 定向修复"),
        ("citation", "📎 引用溯源"),
        ("ontology", "🗺️ 知识图谱"),
    ]

    progress_lines: list[str] = []
    for node_id, node_label in DAG_NODES:
        status = node_statuses.get(node_id, "pending")
        if status == "completed":
            icon = "🟢"
        elif status == "running":
            icon = "🔵"
        elif status == "failed":
            icon = "🔴"
        else:
            icon = "⚪"
        progress_lines.append(f"{icon} {node_label}")

    total = len(DAG_NODES)
    completed = sum(1 for s in node_statuses.values() if s == "completed")
    progress_pct = int(completed / total * 100) if total > 0 else 0

    card = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "blue",
                "title": {
                    "tag": "plain_text",
                    "content": f"📊 分析进度：{competitor}（{progress_pct}%）",
                },
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": "\n".join(progress_lines)},
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": (
                        f"**任务ID**: `{task_id}`\n"
                        f"**进度**: {completed}/{total} 节点完成\n"
                        f"**模式**: {'🎭 Mock演示' if mode == 'mock' else '🤖 真实LLM'}"
                    )},
                },
            ],
        },
    }
    return card
