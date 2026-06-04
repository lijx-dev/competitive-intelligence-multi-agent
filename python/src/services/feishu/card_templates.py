"""
飞书消息卡片模板 — 竞品分析报告 / 告警通知 / 反馈收集。
纯文本无emoji 100%兼容飞书JSON协议。
"""
import json
import re


def _sanitize_text(text: str) -> str:
    """清理文本中的非法控制字符和特殊emoji，避免破坏JSON结构。"""
    if not isinstance(text, str):
        text = str(text)
    # 移除所有不可打印控制字符
    text = re.sub(r'[\x00-\x1f\x7f]', '', text)
    # 把回车替换成换行，合并多余空行
    text = text.replace('\r', '\n')
    text = re.sub(r'\n\s*\n+', '\n', text)
    # 额外移除emoji等特殊Unicode字符，保证100%JSON兼容
    text = re.sub(r'[^\u0020-\u007e\u4e00-\u9fff\n\t\-]', '', text)
    return text.strip()


# ── 竞品分析报告卡片（主卡片，分析完成时推送）───────────────
REPORT_CARD_TEMPLATE = {
    "msg_type": "interactive",
    "card": {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "blue",
            "title": {
                "tag": "plain_text",
                "content": "竞品分析报告：{competitor}",
            },
            "subtitle": {
                "tag": "plain_text",
                "content": "多Agent协作系统 自动生成 {timestamp}",
            },
        },
        "elements": [
            {
                "tag": "div",
                "fields": [
                    {"is_short": True, "text": {"tag": "lark_md", "content": "质量评分\n{quality_score}/10"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": "数据来源\n{total_sources} 个来源"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": "验证可信度\n{reliability}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": "分析耗时\n{duration_ms}ms"}},
                ],
            },
            {"tag": "hr"},
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": "关键发现\n{key_findings}"},
            },
            {"tag": "hr"},
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": "对比摘要\n{comparison_summary}"},
            },
            {"tag": "hr"},
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "查看完整报告"},
                        "type": "primary",
                        "url": "{base_url}/api/v1/feishu/feedback?action=view&report_id={report_id}",
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "分析准确"},
                        "type": "default",
                        "value": json.dumps({"action": "confirm", "report_id": "{report_id}"}),
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "需要修正"},
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
                "content": "竞品监控告警：{competitor}",
            },
        },
        "elements": [
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": "告警级别：{severity}\n变更类型：{change_type}\n摘要：{summary}\n检测时间：{detected_at}"},
            },
            {"tag": "hr"},
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "查看详情"},
                        "type": "primary",
                        "url": "{base_url}",
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "已知悉"},
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
                "content": "分析反馈收集",
            },
        },
        "elements": [
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": "感谢您的反馈！请选择以下操作帮助改进分析质量。\n报告ID：`{report_id}`"},
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "分析准确"},
                        "type": "primary",
                        "value": json.dumps({"action": "confirm", "report_id": "{report_id}"}),
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "需修正"},
                        "type": "danger",
                        "value": json.dumps({"action": "correct", "report_id": "{report_id}"}),
                    },
                ],
            },
        ],
    },
}


# ── 辅助构建函数 ─────────────────────────────────────────────
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
    competitor = _sanitize_text(competitor)
    key_findings = _sanitize_text(key_findings)[:300]
    comparison_summary = _sanitize_text(comparison_summary)[:300]
    reliability = _sanitize_text(reliability)
    timestamp = _sanitize_text(timestamp)
    base_url = _sanitize_text(base_url)
    report_id = _sanitize_text(report_id)
    
    raw = json.dumps(REPORT_CARD_TEMPLATE, ensure_ascii=False)
    raw = raw.replace("{competitor}", competitor)
    raw = raw.replace("{quality_score}", f"{quality_score:.1f}")
    raw = raw.replace("{total_sources}", str(total_sources))
    raw = raw.replace("{reliability}", reliability)
    raw = raw.replace("{duration_ms}", f"{duration_ms:,}")
    raw = raw.replace("{key_findings}", key_findings)
    raw = raw.replace("{comparison_summary}", comparison_summary)
    raw = raw.replace("{report_id}", report_id)
    raw = raw.replace("{base_url}", base_url)
    raw = raw.replace("{timestamp}", timestamp)
    return json.loads(raw)


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
    competitor = _sanitize_text(competitor)
    severity = _sanitize_text(severity)
    change_type = _sanitize_text(change_type)
    summary = _sanitize_text(summary)[:300]
    base_url = _sanitize_text(base_url)
    alert_id = _sanitize_text(alert_id)
    detected_at = _sanitize_text(detected_at)
    
    raw = json.dumps(ALERT_CARD_TEMPLATE, ensure_ascii=False)
    raw = raw.replace("{competitor}", competitor)
    raw = raw.replace("{severity}", severity.upper())
    raw = raw.replace("{change_type}", change_type)
    raw = raw.replace("{summary}", summary)
    raw = raw.replace("{base_url}", base_url)
    raw = raw.replace("{alert_id}", alert_id)
    raw = raw.replace("{detected_at}", detected_at)
    return json.loads(raw)
