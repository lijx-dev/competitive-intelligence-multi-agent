"""
DAG 可视化引擎 — 纯 HTML/CSS/JS 实现，无 React/ReactFlow 依赖。

创新点：
  1. 纯 SVG + CSS 动画渲染 DAG，可嵌入 Streamlit st.components.v1.html()
  2. 节点热力图：执行耗时越长→颜色越深（HSL色相偏移）
  3. SVG 导出：一键下载 DAG 为独立 SVG 文件，用于答辩展示
  4. 点击节点展开对应 Agent 决策日志详情（内联面板）
  5. 运行时控制：暂停/恢复/手动标记节点状态

使用示例:
    snapshot = DAGSnapshot(nodes=[...], edges=[...])
    html = dag_visualizer.render(snapshot)
    st.components.v1.html(html, height=600)

    # 导出 SVG
    dag_visualizer.export_svg(snapshot, "dag_output.svg")
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Optional

from .data_models import (
    DAGEdge,
    DAGNodeRuntime,
    DAGSnapshot,
    NodeStatus,
)

logger = logging.getLogger(__name__)

# 状态颜色映射
STATUS_COLORS = {
    NodeStatus.IDLE:      {"fill": "#64748b", "stroke": "#475569", "text": "#94a3b8"},
    NodeStatus.RUNNING:   {"fill": "#3b82f6", "stroke": "#2563eb", "text": "#93c5fd", "pulse": True},
    NodeStatus.COMPLETED: {"fill": "#10b981", "stroke": "#059669", "text": "#6ee7b7"},
    NodeStatus.FAILED:    {"fill": "#ef4444", "stroke": "#dc2626", "text": "#fca5a5"},
    NodeStatus.PAUSED:    {"fill": "#f59e0b", "stroke": "#d97706", "text": "#fde68a"},
}

# 布局参数
NODE_WIDTH = 160
NODE_HEIGHT = 80
H_GAP = 260
V_GAP = 140
CANVAS_PADDING = 60


class DAGVisualizer:
    """DAG 可视化引擎"""

    def __init__(self):
        self._snapshot: Optional[DAGSnapshot] = None
        self._decision_logs: dict[str, list[dict]] = {}  # node_id → log entries

    # ------------------------------------------------------------------
    # 渲染 HTML
    # ------------------------------------------------------------------

    def render(
        self,
        snapshot: DAGSnapshot,
        decision_logs: dict[str, list[dict]] | None = None,
        height: int = 600,
        interactive: bool = True,
    ) -> str:
        """渲染 DAG 为完整 HTML 页面，可直接嵌入 Streamlit。

        Args:
            snapshot: DAG 快照
            decision_logs: node_id → 决策日志列表（点击节点时展示）
            height: 渲染区域高度（px）
            interactive: 是否启用交互（点击/暂停/恢复）
        """
        self._snapshot = snapshot
        self._decision_logs = decision_logs or {}

        # 计算画布尺寸
        canvas_w = self._calc_canvas_width(snapshot)
        canvas_h = self._calc_canvas_height(snapshot)

        # 布局节点
        positions = self._layout(snapshot)

        # 生成 HTML
        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0f172a;font-family:system-ui,sans-serif;overflow:hidden;color:#e2e8f0}}
.dag-container{{width:100%;height:{height}px;position:relative;overflow:auto}}
.dag-svg{{display:block}}
.edge-line{{fill:none;stroke:#475569;stroke-width:2;transition:stroke 0.3s}}
.edge-line.animated{{stroke:#6366f1;stroke-dasharray:8,4;animation:dash-flow 0.8s linear infinite}}
.edge-arrow{{fill:#475569}}
@keyframes dash-flow{{to{{stroke-dashoffset:-12}}}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:0.5}}}}
.node-group{{cursor:pointer;transition:transform 0.2s}}
.node-group:hover{{transform:scale(1.03)}}
.node-rect{{rx:12;ry:12;stroke-width:2.5;transition:all 0.3s}}
.node-label{{font-size:13px;font-weight:600;fill:#e2e8f0;text-anchor:middle}}
.node-meta{{font-size:10px;fill:#94a3b8;text-anchor:middle}}
.node-icon{{font-size:18px;text-anchor:middle}}
.node-badge{{font-size:9px;font-weight:700;text-anchor:middle}}
.heat-legend{{position:absolute;bottom:10px;right:10px;background:#1e293b;border-radius:8px;padding:8px 12px;font-size:11px}}
.heat-bar{{display:inline-block;width:60px;height:8px;border-radius:4px;background:linear-gradient(90deg,#10b981,#f59e0b,#ef4444)}}
.control-panel{{position:absolute;top:10px;right:10px;display:flex;gap:6px}}
.ctrl-btn{{background:#1e293b;border:1px solid #334155;color:#e2e8f0;padding:4px 10px;border-radius:6px;cursor:pointer;font-size:11px}}
.ctrl-btn:hover{{background:#334155}}
.log-panel{{display:none;position:absolute;top:50px;right:10px;width:320px;max-height:400px;overflow-y:auto;background:#1e293b;border:1px solid #334155;border-radius:8px;padding:12px;font-size:11px;z-index:10}}
.log-panel.active{{display:block}}
.log-entry{{border-bottom:1px solid #334155;padding:6px 0}}
.log-entry:last-child{{border-bottom:none}}
.log-key{{color:#94a3b8}}
.log-val{{color:#e2e8f0}}
</style></head><body>
<div class="dag-container">
  <svg class="dag-svg" viewBox="0 0 {canvas_w} {canvas_h}" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
        <polygon points="0 0, 10 3.5, 0 7" class="edge-arrow"/>
      </marker>
      <filter id="glow"><feGaussianBlur stdDeviation="3" result="blur"/>
        <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>
    </defs>
    {self._render_edges(positions, snapshot.edges)}
    {self._render_nodes(positions, snapshot.nodes)}
  </svg>
  {self._render_legend() if interactive else ""}
  {self._render_controls() if interactive else ""}
  {self._render_log_panel() if interactive else ""}
  {self._render_js(interactive)}
</div></body></html>"""

    # ------------------------------------------------------------------
    # 导出 SVG
    # ------------------------------------------------------------------

    def export_svg(self, snapshot: DAGSnapshot, filepath: str = "dag_output.svg") -> str:
        """导出 DAG 为独立 SVG 文件，可直接在浏览器中打开或嵌入答辩 PPT"""
        self._snapshot = snapshot
        canvas_w = self._calc_canvas_width(snapshot)
        canvas_h = self._calc_canvas_height(snapshot)
        positions = self._layout(snapshot)

        svg_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_w} {canvas_h}" width="{canvas_w}" height="{canvas_h}">
  <rect width="100%" height="100%" fill="#0f172a"/>
  <defs>
    <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
      <polygon points="0 0, 10 3.5, 0 7" fill="#475569"/>
    </marker>
  </defs>
  <text x="{canvas_w/2}" y="25" fill="#64748b" font-size="12" text-anchor="middle" font-family="system-ui">
    DAG Snapshot — {snapshot.timestamp.isoformat()} | Progress: {snapshot.total_progress*100:.0f}%
  </text>
  {self._render_edges(positions, snapshot.edges)}
  {self._render_nodes(positions, snapshot.nodes)}
</svg>"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(svg_content)
        logger.info(f"DAG SVG exported to {filepath}")
        return svg_content

    # ------------------------------------------------------------------
    # 布局算法（层次布局）
    # ------------------------------------------------------------------

    def _layout(self, snapshot: DAGSnapshot) -> dict[str, tuple[int, int]]:
        """按拓扑层次布局节点，同层居中排列"""
        if not snapshot.nodes:
            return {}

        # 计算每个节点的深度（拓扑排序）
        depths: dict[str, int] = {}
        edge_map: dict[str, list[str]] = {n.node_id: [] for n in snapshot.nodes}
        for e in snapshot.edges:
            if e.target in edge_map:
                edge_map[e.target].append(e.source)

        def get_depth(node_id: str, visited: Optional[set] = None) -> int:
            if visited is None:
                visited = set()
            if node_id in visited:
                return 0
            visited.add(node_id)
            parents = edge_map.get(node_id, [])
            if not parents:
                return 0
            return 1 + max(get_depth(p, visited.copy()) for p in parents)

        for node in snapshot.nodes:
            depths[node.node_id] = get_depth(node.node_id)

        # 按层分组
        layers: dict[int, list[str]] = {}
        for nid, d in depths.items():
            layers.setdefault(d, []).append(nid)

        # 计算坐标
        positions: dict[str, tuple[int, int]] = {}
        for depth, node_ids in sorted(layers.items()):
            count = len(node_ids)
            for i, nid in enumerate(node_ids):
                x = CANVAS_PADDING + depth * H_GAP
                y = CANVAS_PADDING + (i - (count - 1) / 2) * V_GAP + (V_GAP * 1.5)
                positions[nid] = (x, int(y))

        # 未分配节点放底部
        for node in snapshot.nodes:
            if node.node_id not in positions:
                positions[node.node_id] = (CANVAS_PADDING, CANVAS_PADDING + len(positions) * V_GAP)

        return positions

    # ------------------------------------------------------------------
    # 渲染子组件
    # ------------------------------------------------------------------

    def _render_edges(
        self, positions: dict[str, tuple[int, int]], edges: list[DAGEdge]
    ) -> str:
        svg = ""
        for edge in edges:
            if edge.source not in positions or edge.target not in positions:
                continue
            x1, y1 = positions[edge.source]
            x2, y2 = positions[edge.target]
            # 偏移到节点边缘
            x1 += NODE_WIDTH
            y1 += NODE_HEIGHT // 2
            x2_start = x2
            y2_start = y2 + NODE_HEIGHT // 2

            anim_cls = " animated" if edge.animated else ""
            mid_x = (x1 + x2_start) / 2
            path = f"M{x1},{y1} C{mid_x},{y1} {mid_x},{y2_start} {x2_start},{y2_start}"
            svg += f'<path d="{path}" class="edge-line{anim_cls}" marker-end="url(#arrowhead)"/>\n'
            if edge.label:
                svg += f'<text x="{mid_x}" y="{y1 - 8}" class="node-meta" font-size="9">{edge.label}</text>\n'
        return svg

    def _render_nodes(
        self, positions: dict[str, tuple[int, int]], nodes: list[DAGNodeRuntime]
    ) -> str:
        svg = ""
        for node in nodes:
            if node.node_id not in positions:
                continue
            x, y = positions[node.node_id]
            sc = STATUS_COLORS.get(node.status, STATUS_COLORS[NodeStatus.IDLE])

            # 热力图颜色：用 HSL 色相表达耗时（绿→黄→红）
            heat_color = self._heat_color(node.duration_ms)

            glow = ' filter="url(#glow)"' if node.status == NodeStatus.RUNNING else ""

            svg += f"""<g class="node-group" onclick="showLogs('{node.node_id}')"{glow}>
  <rect x="{x}" y="{y}" width="{NODE_WIDTH}" height="{NODE_HEIGHT}"
        class="node-rect" fill="{sc['fill']}" stroke="{sc['stroke']}"
        style="--heat:{heat_color}"/>
  <rect x="{x}" y="{y + NODE_HEIGHT - 6}" width="{NODE_WIDTH * min(node.progress, 1.0)}"
        height="6" fill="{heat_color}" rx="3" opacity="0.7"/>
  <text x="{x + NODE_WIDTH/2}" y="{y + 24}" class="node-icon">{node.icon}</text>
  <text x="{x + NODE_WIDTH/2}" y="{y + 46}" class="node-label">{node.label}</text>
  <text x="{x + NODE_WIDTH/2}" y="{y + 62}" class="node-meta">{self._fmt_duration(node.duration_ms)} | {node.status.value}</text>
</g>\n"""
        return svg

    def _render_legend(self) -> str:
        return """<div class="heat-legend">
  <div style="margin-bottom:4px">⏱️ 耗时热力图</div>
  <div class="heat-bar"></div>
  <span style="float:left;font-size:10px;color:#10b981">快</span>
  <span style="float:right;font-size:10px;color:#ef4444">慢</span>
</div>"""

    def _render_controls(self) -> str:
        return """<div class="control-panel">
  <button class="ctrl-btn" onclick="pauseDAG()">⏯️ 暂停</button>
  <button class="ctrl-btn" onclick="exportSVG()">📥 导出 SVG</button>
</div>"""

    def _render_log_panel(self) -> str:
        logs_json = json.dumps(self._decision_logs, ensure_ascii=False)
        return f"""<div class="log-panel" id="logPanel">
  <div style="display:flex;justify-content:space-between;margin-bottom:8px">
    <b id="logPanelTitle">Agent 决策日志</b>
    <span style="cursor:pointer" onclick="closeLogs()">✕</span>
  </div>
  <div id="logPanelBody">点击节点查看详情</div>
</div>
<script>
const decisionLogs = {logs_json};
function showLogs(nodeId) {{
  const panel = document.getElementById('logPanel');
  const body = document.getElementById('logPanelBody');
  const title = document.getElementById('logPanelTitle');
  panel.classList.add('active');
  title.textContent = 'Agent: ' + nodeId;
  const logs = decisionLogs[nodeId] || [];
  if (logs.length === 0) {{
    body.innerHTML = '<div class="log-entry"><span class="log-key">暂无决策日志</span></div>';
    return;
  }}
  body.innerHTML = logs.map(l =>
    '<div class="log-entry">' +
    '<div><span class="log-key">步数:</span> <span class="log-val">' + (l.step_number||l.seq||'') + '</span></div>' +
    '<div><span class="log-key">耗时:</span> <span class="log-val">' + (l.duration_ms||0) + 'ms</span></div>' +
    '<div><span class="log-key">Token:</span> <span class="log-val">' + ((l.input_tokens||0)+(l.output_tokens||0)) + '</span></div>' +
    '<div><span class="log-key">推理:</span> <span class="log-val">' + ((l.reasoning||l.reasoning_preview||'').substring(0,100)) + '</span></div>' +
    '</div>'
  ).join('');
}}
function closeLogs() {{ document.getElementById('logPanel').classList.remove('active'); }}
</script>"""

    def _render_js(self, interactive: bool) -> str:
        if not interactive:
            return ""
        return """<script>
function pauseDAG() {
  const btn = event.target;
  btn.textContent = btn.textContent === '⏯️ 暂停' ? '▶️ 恢复' : '⏯️ 暂停';
  // 通过 postMessage 通知 Streamlit
  window.parent.postMessage({type: 'dag_pause', paused: btn.textContent === '▶️ 恢复'}, '*');
}
function exportSVG() {
  const svg = document.querySelector('.dag-svg');
  const clone = svg.cloneNode(true);
  const data = new XMLSerializer().serializeToString(clone);
  const blob = new Blob(['<?xml version="1.0" encoding="UTF-8"?>\\n' + data], {type: 'image/svg+xml'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'dag_snapshot.svg';
  a.click(); URL.revokeObjectURL(url);
}
</script>"""

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    def _heat_color(self, duration_ms: int) -> str:
        """根据耗时生成热力图 HSL 颜色（0ms=绿, 15000ms+=红）"""
        ratio = min(duration_ms / 15_000, 1.0)  # 0-1
        hue = 120 - ratio * 120  # 120(绿) → 0(红)
        return f"hsl({hue:.0f}, 70%, 50%)"

    def _calc_canvas_width(self, snapshot: DAGSnapshot) -> int:
        if not snapshot.nodes:
            return 800
        depths = set()
        edge_map: dict[str, list[str]] = {n.node_id: [] for n in snapshot.nodes}
        for e in snapshot.edges:
            if e.target in edge_map:
                edge_map[e.target].append(e.source)

        for node in snapshot.nodes:
            visited = set()

            def get_depth(nid: str) -> int:
                if nid in visited:
                    return 0
                visited.add(nid)
                parents = edge_map.get(nid, [])
                if not parents:
                    return 0
                return 1 + max(get_depth(p) for p in parents)

            depths.add(get_depth(node.node_id))
        max_depth = max(depths) if depths else 2
        return CANVAS_PADDING * 2 + max(max_depth, 2) * H_GAP + NODE_WIDTH

    def _calc_canvas_height(self, snapshot: DAGSnapshot) -> int:
        if not snapshot.nodes:
            return 400
        max_in_layer = max(1, len(snapshot.nodes) // 2 or 1)
        return CANVAS_PADDING * 2 + max_in_layer * V_GAP + NODE_HEIGHT

    @staticmethod
    def _fmt_duration(ms: int) -> str:
        if ms < 1000:
            return f"{ms}ms"
        if ms < 60_000:
            return f"{ms/1000:.1f}s"
        return f"{ms/60000:.1f}m"


# 模块级单例
dag_visualizer = DAGVisualizer()
