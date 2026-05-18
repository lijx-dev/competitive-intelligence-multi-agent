"""
EventBus 事件总线 — 事件溯源 + SQLite 持久化 + 告警规则 + 订阅接口。

创新点：
  1. trace_chain(event_id) 根据 parent_event_id 回溯完整执行链路
  2. 自定义告警规则（AlertRule），Agent 失败/Token 超支时自动触发
  3. 事件持久化到 SQLite（非仅内存），支持重启后恢复
  4. subscribe() / unsubscribe() 接口，供 Streamlit/React 前端实时监听

使用示例:
    bus = EventBus(db_path="events.db")
    bus.subscribe("dag_node_changed", my_handler)
    await bus.publish(BusEvent(event_type=EventType.AGENT_STARTED, source="monitor"))
    chain = bus.trace_chain("evt_abc123")
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Callable, Awaitable, Optional

from .data_models import (
    AlertRule,
    BusEvent,
    EventType,
    Severity,
)

logger = logging.getLogger(__name__)

EventHandler = Callable[[BusEvent], Awaitable[None]]


class EventBus:
    """事件总线 — 事件溯源 + 持久化 + 告警 + 订阅"""

    def __init__(self, db_path: str = "events.db"):
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._events: list[BusEvent] = []
        self._alert_rules: list[AlertRule] = []
        self._alert_stats: dict[str, datetime] = {}  # rule_id → last triggered
        self.db_path = db_path
        self._init_db()

    # ------------------------------------------------------------------
    # 持久化（SQLite）
    # ------------------------------------------------------------------

    def _init_db(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                source TEXT NOT NULL,
                data TEXT NOT NULL DEFAULT '{}',
                parent_event_id TEXT,
                timestamp TEXT NOT NULL,
                CONSTRAINT fk_parent FOREIGN KEY (parent_event_id) REFERENCES events(event_id)
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_events_source ON events(source)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_events_parent ON events(parent_event_id)')
        conn.commit()
        conn.close()

    def _persist(self, event: BusEvent):
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.execute(
                'INSERT OR IGNORE INTO events VALUES (?, ?, ?, ?, ?, ?)',
                (
                    event.event_id, event.event_type.value, event.source,
                    json.dumps(event.data, ensure_ascii=False),
                    event.parent_event_id, event.timestamp.isoformat(),
                ),
            )
            conn.commit()
            conn.close()
            event.persisted = True
        except Exception as e:
            logger.error(f"Failed to persist event {event.event_id}: {e}")

    # ------------------------------------------------------------------
    # 发布/订阅
    # ------------------------------------------------------------------

    async def publish(self, event: BusEvent) -> None:
        """发布事件：记录 → 持久化 → 通知订阅者 → 检查告警规则"""
        self._events.append(event)
        self._persist(event)

        # 通知订阅者
        handlers = self._subscribers.get(event.event_type.value, [])
        handlers += self._subscribers.get("*", [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Event handler error for {event.event_type}: {e}")

        # 检查告警规则
        await self._check_alerts(event)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """订阅指定事件类型。event_type="*" 订阅全部。"""
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        if handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)

    # ------------------------------------------------------------------
    # 事件溯源
    # ------------------------------------------------------------------

    def trace_chain(self, event_id: str, max_depth: int = 20) -> list[dict]:
        """根据事件 ID 回溯完整执行链路（沿 parent_event_id 向上追溯）。

        返回从根事件到当前事件的完整链路。
        """
        # 构建事件索引
        event_map: dict[str, BusEvent] = {e.event_id: e for e in self._events}

        chain = []
        current_id = event_id
        depth = 0
        while current_id and depth < max_depth:
            evt = event_map.get(current_id)
            if not evt:
                # 尝试从 DB 加载
                evt = self._load_from_db(current_id)
            if not evt:
                break
            chain.append({
                "event_id": evt.event_id,
                "event_type": evt.event_type.value,
                "source": evt.source,
                "data_preview": str(evt.data)[:200],
                "parent_event_id": evt.parent_event_id,
                "timestamp": evt.timestamp.isoformat(),
            })
            current_id = evt.parent_event_id
            depth += 1

        chain.reverse()  # 从根到叶
        return chain

    def _load_from_db(self, event_id: str) -> Optional[BusEvent]:
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.execute('SELECT * FROM events WHERE event_id = ?', (event_id,))
            row = cursor.fetchone()
            conn.close()
            if row:
                return BusEvent(
                    event_id=row[0],
                    event_type=EventType(row[1]),
                    source=row[2],
                    data=json.loads(row[3]),
                    parent_event_id=row[4],
                    timestamp=datetime.fromisoformat(row[5]),
                )
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # 告警规则
    # ------------------------------------------------------------------

    def add_alert_rule(self, rule: AlertRule) -> str:
        self._alert_rules.append(rule)
        return rule.rule_id

    async def _check_alerts(self, event: BusEvent):
        """检查事件是否触发告警规则"""
        now = datetime.now()
        for rule in self._alert_rules:
            if not rule.enabled:
                continue
            if rule.event_types and event.event_type not in rule.event_types:
                continue

            # 冷却检查
            last = self._alert_stats.get(rule.rule_id)
            if last and (now - last).total_seconds() < rule.cooldown_seconds:
                continue

            # 触发告警
            self._alert_stats[rule.rule_id] = now
            rule.last_triggered = now
            alert_event = BusEvent(
                event_type=EventType.ALERT_TRIGGERED,
                source="event_bus",
                data={
                    "rule_name": rule.name,
                    "triggered_by": event.event_type.value,
                    "triggered_source": event.source,
                    "message": f"告警规则 '{rule.name}' 被触发：{event.event_type.value} from {event.source}",
                },
                parent_event_id=event.event_id,
            )
            await self.publish(alert_event)

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_events(
        self, event_type: EventType | None = None, source: str | None = None
    ) -> list[BusEvent]:
        events = self._events
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if source:
            events = [e for e in events if e.source == source]
        return events

    def get_recent(self, count: int = 50) -> list[BusEvent]:
        return self._events[-count:]

    def get_all(self) -> list[BusEvent]:
        return list(self._events)


# 全局单例
event_bus = EventBus()
