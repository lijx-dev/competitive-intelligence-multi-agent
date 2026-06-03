"""
飞书群内实时流式进度更新 — 基于 SSE 事件发布订阅机制。

每个 Agent 节点执行完成后，自动异步回调更新飞书卡片状态：
- 灰度 = 未开始
- 蓝色 = 执行中
- 绿色 = 已完成
- 红色 = 失败

通过 EventBus 订阅 Agent 节点状态变更事件，
每次变更后自动调用 FeishuBot 更新进度卡片。
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from datetime import datetime
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ── 12节点DAG定义（与workflow.py保持一致）───────────────────
ALL_DAG_NODES: list[tuple[str, str]] = [
    ("monitor", "网页监控"),
    ("alert", "告警检测"),
    ("research", "5维深度研究"),
    ("multimodal", "多模态分析"),
    ("fact_check", "交叉验证"),
    ("research_retry", "Research重执行"),
    ("compare", "8维对比矩阵"),
    ("schema_validation", "Schema校验"),
    ("battlecard", "销售战术卡"),
    ("reviewer", "质量审查"),
    ("targeted_fix", "定向修复"),
    ("citation", "引用溯源"),
    ("ontology", "知识图谱"),
    ("feishu_push", "飞书推送"),
]

# ── 全局任务状态存储（内存，同一个进程内有效）─────────────
_task_registry: dict[str, "TaskProgress"] = {}


class TaskProgress:
    """单个分析任务的实时进度追踪器。"""

    def __init__(
        self,
        task_id: str,
        competitor: str,
        mode: str = "mock",
        chat_id: str = "",
    ):
        self.task_id = task_id
        self.competitor = competitor
        self.mode = mode
        self.chat_id = chat_id
        self.created_at = datetime.utcnow()

        # 节点状态: node_name → "pending" | "running" | "completed" | "failed"
        self.node_status: dict[str, str] = {}
        for node_id, _ in ALL_DAG_NODES:
            self.node_status[node_id] = "pending"

        self._lock = threading.Lock()
        self._on_update: Optional[Callable] = None
        self._update_count = 0
        self._last_update_at: float = 0.0
        self._update_cooldown: float = 0.5  # 500ms 冷却（防飞书API限频）

    def update_node(self, node_name: str, status: str) -> bool:
        """更新单个节点的执行状态。

        Returns:
            True if status actually changed (should trigger card push)
        """
        if node_name not in self.node_status:
            # 映射到已知节点名
            mapped = _map_node_name(node_name)
            if mapped and mapped in self.node_status:
                node_name = mapped
            else:
                logger.debug("未知DAG节点: %s，跳过进度更新", node_name)
                return False

        with self._lock:
            old_status = self.node_status.get(node_name, "pending")
            if old_status == status:
                return False  # 状态无变化
            self.node_status[node_name] = status
            self._update_count += 1
            self._last_update_at = time.time()

        # 检查冷却
        if self._on_update:
            try:
                self._on_update(self)
            except Exception as e:
                logger.debug("进度回调异常: %s", e)

        return True

    def get_progress(self) -> dict:
        """获取当前进度摘要。"""
        total = len(ALL_DAG_NODES)
        completed = sum(1 for s in self.node_status.values() if s == "completed")
        failed = sum(1 for s in self.node_status.values() if s == "failed")
        running = sum(1 for s in self.node_status.values() if s == "running")
        return {
            "task_id": self.task_id,
            "competitor": self.competitor,
            "total": total,
            "completed": completed,
            "failed": failed,
            "running": running,
            "pending": total - completed - failed - running,
            "progress_pct": int(completed / total * 100) if total > 0 else 0,
            "node_status": dict(self.node_status),
            "mode": self.mode,
        }

    @property
    def is_complete(self) -> bool:
        return all(
            s in ("completed", "failed")
            for s in self.node_status.values()
        )


def _map_node_name(node_name: str) -> Optional[str]:
    """将可能变体的节点名映射到标准节点名。"""
    mapping = {
        "monitor_agent": "monitor",
        "alert_agent": "alert",
        "research_agent": "research",
        "fact_check_agent": "fact_check",
        "compare_agent": "compare",
        "battlecard_agent": "battlecard",
        "reviewer_agent": "reviewer",
        "targeted_fix_agent": "targeted_fix",
        "citation_agent": "citation",
        "ontology_builder": "ontology",
        "feishu_push_node": "feishu_push",
    }
    return mapping.get(node_name, node_name if node_name in dict(ALL_DAG_NODES) else None)


# ── 公共 API ──────────────────────────────────────────────

def create_task(
    task_id: str,
    competitor: str,
    mode: str = "mock",
    chat_id: str = "",
) -> TaskProgress:
    """创建一个新任务并注册到全局注册表。"""
    progress = TaskProgress(task_id, competitor, mode, chat_id)
    _task_registry[task_id] = progress
    logger.info("飞书任务已注册: %s → %s (mode=%s)", task_id, competitor, mode)
    return progress


def get_task(task_id: str) -> Optional[TaskProgress]:
    """根据task_id获取任务进度。"""
    return _task_registry.get(task_id)


def get_all_tasks() -> list[TaskProgress]:
    """获取所有活跃任务。"""
    return list(_task_registry.values())


def cleanup_completed_tasks(max_age_seconds: float = 3600) -> int:
    """清理已完成超过指定时间的任务记录。"""
    now = datetime.utcnow()
    to_remove = []
    for task_id, progress in _task_registry.items():
        if progress.is_complete:
            age = (now - progress.created_at).total_seconds()
            if age > max_age_seconds:
                to_remove.append(task_id)
    for tid in to_remove:
        del _task_registry[tid]
    if to_remove:
        logger.info("清理了 %d 个过期飞书任务", len(to_remove))
    return len(to_remove)


# ── 飞书卡片回调集成 ──────────────────────────────────────


class FeishuLiveUpdater:
    """飞书实时进度更新器。

    绑定 FeishuBot 实例，在每次节点状态变更时自动推送进度卡片。

    使用示例:
        updater = FeishuLiveUpdater(bot)
        task = create_task("task_001", "快手电商")
        task.on_update = updater.on_node_update  # 注册回调
    """

    def __init__(self, bot=None):
        self._bot = bot
        self._pending_updates: dict[str, float] = {}  # task_id → last_push_ts

    async def on_node_update(self, progress: TaskProgress) -> None:
        """节点状态变更回调 — 异步推送进度卡片到飞书。"""
        if not self._bot:
            return

        # 冷却检查（防止频繁推送）
        now = time.time()
        last_push = self._pending_updates.get(progress.task_id, 0)
        if now - last_push < 0.8:  # 800ms 冷却
            return

        self._pending_updates[progress.task_id] = now

        try:
            await self._bot.send_progress_card(
                competitor=progress.competitor,
                task_id=progress.task_id,
                node_statuses=progress.node_status,
                mode=progress.mode,
            )
        except Exception as e:
            logger.warning("飞书进度卡片推送失败（不阻塞主流程）: %s", e)


# ── EventBus 集成（自动订阅模式）───────────────────────────

async def _on_agent_event(event_type: str, event_data: dict) -> None:
    """EventBus 回调：Agent 状态变更时自动更新飞书进度。

    集成到 instrumented_node 的 EventBus 回调链路中。
    """
    try:
        task_id = event_data.get("task_id") or event_data.get("pipeline_run_id", "")
        if not task_id:
            return

        progress = get_task(task_id)
        if not progress:
            return  # 未注册的任务，跳过

        agent_name = event_data.get("agent_name", "")
        status = _event_to_status(event_type)
        if agent_name and status:
            progress.update_node(agent_name, status)
    except Exception as e:
        logger.debug("EventBus进度同步跳过: %s", e)


def _event_to_status(event_type: str) -> str:
    """将 EventBus 事件类型映射到节点状态。"""
    if "started" in event_type:
        return "running"
    elif "completed" in event_type:
        return "completed"
    elif "failed" in event_type:
        return "failed"
    return ""


# ── FeishuBot 集成（从 workflow 自动触发）───────────────────

async def push_progress_update(
    bot,  # FeishuBot instance
    task_id: str,
    node_name: str,
    status: str,
    competitor: str = "",
    mode: str = "mock",
) -> None:
    """从 workflow 节点包装器中调用：每次 Agent 执行完成后更新飞书卡片。

    用法（在 instrumented_node 成功后调用）：
        await push_progress_update(bot, task_id, "monitor", "completed", competitor, mode)
    """
    try:
        progress = get_task(task_id)
        if not progress:
            # 自动创建
            progress = create_task(task_id, competitor, mode)

        changed = progress.update_node(node_name, status)
        if changed:
            updater = FeishuLiveUpdater(bot)
            await updater.on_node_update(progress)
    except Exception as e:
        logger.debug("飞书进度推送非阻塞: %s", e)


# ── Mock 模式演示辅助 ─────────────────────────────────────

async def mock_feishu_progress_demo(
    bot,
    task_id: str,
    competitor: str = "快手电商",
    mode: str = "mock",
    delay_s: float = 0.3,
) -> None:
    """Mock 模式下演示飞书进度卡片逐节点更新效果。

    依次点亮12个节点，每个节点间延迟 delay_s 秒。
    """
    import asyncio

    task = create_task(task_id, competitor, mode)
    updater = FeishuLiveUpdater(bot)

    for node_id, node_label in ALL_DAG_NODES:
        task.update_node(node_id, "running")
        await updater.on_node_update(task)
        await asyncio.sleep(delay_s * 0.5)

        task.update_node(node_id, "completed")
        await updater.on_node_update(task)
        await asyncio.sleep(delay_s * 0.5)

    logger.info("Mock 飞书进度演示完成: %s (%s)", competitor, task_id)
