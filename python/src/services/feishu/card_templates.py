"""
飞书消息卡片模板 — 竞品分析报告 / 告警通知 / 反馈收集。
"""
import json

# ── 竞品分析报告卡片（主卡片，分析完成时推送）───────────────
# template 变量用 {var} 占位，send 时 .format(**data) 替换

REPORT_CARD_TEMPLATE = {
    "msg_type": "interactive",
    "card": {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "blue",
            "title": {
                "tag": "plain_text",
                "content": "📊 竞品分析报告：{competitor}",
            },
            "subtitle": {
                "tag": "plain_text",
                "content": "多Agent协作系统 · 自动生成 · {timestamp}",
            },
        },
        "elements": [
            # ── 概览区 ──
            {
                "tag": "div",
                "fields": [
                    {"is_short": True, "text": {"tag": "lark_md", "content": "**质量评分**\n⭐ {quality_score}/10"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": "**数据来源**\n📎 {total_sources} 个来源"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": "**验证可信度**\n🔗 {reliability}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": "**分析耗时**\n⏱️ {duration_ms}ms"}},
                ],
            },
            {"tag": "hr"},
            # ── 关键发现 ──
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": "**🔍 关键发现**\n{key_findings}"},
            },
            {"tag": "hr"},
            # ── 对比摘要 ──
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": "**📈 对比摘要**\n{comparison_summary}"},
            },
            {"tag": "hr"},
            # ── 操作按钮 ──
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "📄 查看完整报告"},
                        "type": "primary",
                        "url": "{base_url}/api/v1/feishu/feedback?action=view&report_id={report_id}",
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "✅ 分析准确"},
                        "type": "default",
                        "value": json.dumps({"action": "confirm", "report_id": "{report_id}"}),
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "❌ 需要修正"},
                        "type": "danger",
                        "value": json.dumps({"action": "correct", "report_id": "{report_id}"}),
                    },
                ],
            },
        ],
    },
}


# ── 告警通知卡片（红色，HIGH/CRITICAL 告警时推送）───────────

ALERT_CARD_TEMPLATE = {
    "msg_type": "interactive",
    "card": {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "red",
            "title": {
                "tag": "plain_text",
                "content": "🚨 竞品监控告警：{competitor}",
            },
        },
        "elements": [
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": "**告警级别**：{severity}\n**变更类型**：{change_type}\n**摘要**：{summary}\n**检测时间**：{detected_at}"},
            },
            {"tag": "hr"},
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "🔍 查看详情"},
                        "type": "primary",
                        "url": "{base_url}",
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "✅ 已知悉"},
                        "type": "default",
                        "value": json.dumps({"action": "ack", "alert_id": "{alert_id}"}),
                    },
                ],
            },
        ],
    },
}


# ── 反馈收集卡片 ────────────────────────────────────────────

FEEDBACK_CARD_TEMPLATE = {
    "msg_type": "interactive",
    "card": {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "purple",
            "title": {
                "tag": "plain_text",
                "content": "📝 分析反馈收集",
            },
        },
        "elements": [
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": "感谢您的反馈！请选择以下操作帮助改进分析质量：\n\n报告ID：`{report_id}`"},
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "✅ 分析准确"},
                        "type": "primary",
                        "value": json.dumps({"action": "confirm", "report_id": "{report_id}"}),
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "❌ 需修正"},
                        "type": "danger",
                        "value": json.dumps({"action": "correct", "report_id": "{report_id}"}),
                    },
                ],
            },
        ],
    },
}


# ── 辅助函数 ────────────────────────────────────────────────

def build_report_card(
    competitor: str,
    quality_score: float,
    total_sources: int,
    reliability: str,
    duration_ms: int,
    key_findings: str,
    comparison_summary: str,
    report_id: str,
    base_url: str = "http://localhost:8000",
    timestamp: str = "",
) -> dict:
    """构建竞品分析报告卡片，替换占位符。"""
    import json as _json
    raw = _json.dumps(REPORT_CARD_TEMPLATE)
    raw = raw.replace("{competitor}", competitor)
    raw = raw.replace("{quality_score}", f"{quality_score:.1f}")
    raw = raw.replace("{total_sources}", str(total_sources))
    raw = raw.replace("{reliability}", reliability)
    raw = raw.replace("{duration_ms}", f"{duration_ms:,}")
    raw = raw.replace("{key_findings}", key_findings[:300])
    raw = raw.replace("{comparison_summary}", comparison_summary[:300])
    raw = raw.replace("{report_id}", report_id)
    raw = raw.replace("{base_url}", base_url)
    raw = raw.replace("{timestamp}", timestamp)
    return _json.loads(raw)


def build_alert_card(
    competitor: str,
    severity: str,
    change_type: str,
    summary: str,
    base_url: str,
    alert_id: str = "",
    detected_at: str = "",
) -> dict:
    """构建告警通知卡片"""
    raw = json.dumps(ALERT_CARD_TEMPLATE)
    raw = raw.replace("{competitor}", competitor)
    raw = raw.replace("{severity}", severity.upper())
    raw = raw.replace("{change_type}", change_type)
    raw = raw.replace("{summary}", summary[:300])
    raw = raw.replace("{base_url}", base_url)
    raw = raw.replace("{alert_id}", alert_id)
    raw = raw.replace("{detected_at}", detected_at)
    return json.loads(raw)
