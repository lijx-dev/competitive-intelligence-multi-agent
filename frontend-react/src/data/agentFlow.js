/**
 * DAG 节点、模块与边定义 — 与后端 workflow.py 12 节点完全对应。
 */

export const dagModules = [
  { id: 'M1', label: '多源采集', color: '#2563eb' },
  { id: 'M2', label: '深度分析', color: '#16a34a' },
  { id: 'M3', label: '报告生成', color: '#9333ea' },
  { id: 'M4', label: '质量保障', color: '#ea580c' },
  { id: 'M5', label: '消息推送', color: '#6b7280' },
];

export const dagNodes = [
  { id: 'monitor',      label: '监控采集',  module: 'M1', icon: 'Search',      desc: '网页变更检测与公开信息抓取' },
  { id: 'alert',        label: '变更告警',  module: 'M5', icon: 'Bell',        desc: '重大变更实时推送通知' },
  { id: 'research',     label: '深度研究',  module: 'M1', icon: 'BookOpen',    desc: '5 维度并行深度分析' },
  { id: 'multimodal',   label: '多模态分析',module: 'M1', icon: 'Image',       desc: '截图/海报/视频素材视觉分析' },
  { id: 'fact_check',   label: '交叉验证',  module: 'M4', icon: 'ShieldCheck', desc: '多源数据一致性校验' },
  { id: 'compare',      label: '对比分析',  module: 'M2', icon: 'BarChart3',   desc: '8 维度竞品评分矩阵' },
  { id: 'battlecard',   label: '对战卡',    module: 'M3', icon: 'Target',      desc: '销售战术卡与异议处理' },
  { id: 'reviewer',     label: '质量审查',  module: 'M4', icon: 'CheckCircle', desc: '4 维度质量评分与打回' },
  { id: 'targeted_fix', label: '定向修复',  module: 'M4', icon: 'Wrench',      desc: '针对审查问题精准修补' },
  { id: 'citation',     label: '来源溯源',  module: 'M4', icon: 'Link2',       desc: '引用验证与可信度评估' },
  { id: 'ontology',     label: '图谱构建',  module: 'M3', icon: 'Network',     desc: 'Ontology五层知识图谱生成' },
  { id: 'feishu_push',  label: '飞书推送',  module: 'M5', icon: 'Send',        desc: '报告卡片推送到团队' },
];

export const dagEdges = [
  { from: 'monitor', to: 'alert' },
  { from: 'monitor', to: 'research' },
  { from: 'research', to: 'multimodal' },
  { from: 'multimodal', to: 'fact_check' },
  { from: 'fact_check', to: 'compare' },
  { from: 'compare', to: 'battlecard' },
  { from: 'battlecard', to: 'reviewer' },
  { from: 'reviewer', to: 'targeted_fix', conditional: true, condition: '评分 < 7' },
  { from: 'reviewer', to: 'citation', conditional: true, condition: '评分 ≥ 7' },
  { from: 'targeted_fix', to: 'reviewer', loop: true },
  { from: 'citation', to: 'ontology' },
  { from: 'ontology', to: 'feishu_push' },
];

/** 根据节点 id 查模块信息 */
export function getNodeModule(nodeId) {
  const node = dagNodes.find((n) => n.id === nodeId);
  if (!node) return null;
  return dagModules.find((m) => m.id === node.module) || null;
}

/** 获取某节点的所有下游节点 id */
export function getDownstreamNodes(nodeId) {
  return dagEdges.filter((e) => e.from === nodeId).map((e) => e.to);
}
