/**
 * AgentDAG — 11 节点 DAG 实时可视化面板。
 *
 * 用 CSS Grid 布局展示拓扑，节点状态实时变色。
 */

import {
  Search, Bell, BookOpen, Users, ShieldCheck,
  BarChart3, Target, CheckCircle, Wrench, Link2, Send,
  Loader2, Check, X, Circle,
} from 'lucide-react';
import { dagNodes, dagModules, dagEdges } from '../../data/agentFlow.js';

const iconMap = { Search, Bell, BookOpen, Users, ShieldCheck, BarChart3, Target, CheckCircle, Wrench, Link2, Send };

/** DAG 拓扑按行分组 */
const dagRows = [
  ['monitor'],
  ['alert', 'research', 'survey'],
  ['fact_check'],
  ['compare'],
  ['battlecard'],
  ['reviewer', 'targeted_fix'],
  ['citation'],
  ['feishu_push'],
];

function StatusIcon({ status }) {
  if (status === 'running') return <Loader2 size={14} className="spin" />;
  if (status === 'completed') return <Check size={14} />;
  if (status === 'failed') return <X size={14} />;
  return <Circle size={14} />;
}

export function AgentDAG({ nodeStatuses = {}, reflexionCount = 0 }) {
  return (
    <div className="dag-panel panel">
      <div className="dag-panel-header">
        <strong>任务流拓扑</strong>
        <small>{dagNodes.length} 个智能体节点</small>
      </div>
      <div className="dag-flow">
        {dagRows.map((row, ri) => (
          <div className="dag-row" key={ri}>
            {ri > 0 && <div className="dag-edge-down" />}
            <div className="dag-row-nodes">
              {row.map((nodeId) => {
                const node = dagNodes.find((n) => n.id === nodeId);
                if (!node) return null;
                const mod = dagModules.find((m) => m.id === node.module);
                const status = nodeStatuses[nodeId]?.status || 'idle';
                const duration = nodeStatuses[nodeId]?.duration;
                const Icon = iconMap[node.icon] || Circle;

                return (
                  <div className={`dag-card dag-card--${status}`} key={nodeId}>
                    <div className="dag-card-top">
                      <span className="dag-module-dot" style={{ background: mod?.color || '#6b7280' }} />
                      <Icon size={15} />
                      <StatusIcon status={status} />
                    </div>
                    <span className="dag-card-label">{node.label}</span>
                    {duration != null && <small className="dag-card-time">{(duration / 1000).toFixed(1)}s</small>}
                    {nodeId === 'targeted_fix' && reflexionCount > 0 && (
                      <small className="dag-card-loop">
                        {'\u21BB'} {reflexionCount} 轮修复
                      </small>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
