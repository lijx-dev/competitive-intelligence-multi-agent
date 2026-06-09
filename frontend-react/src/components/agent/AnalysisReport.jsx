import { useMemo, useState } from 'react';
import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  ClipboardList,
  Lightbulb,
  Link2,
  Network,
  Target,
  Zap,
} from 'lucide-react';
import { HighlightText } from '../common/HighlightText.jsx';

function num(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function clamp(value, min = 0, max = 100) {
  return Math.max(min, Math.min(max, value));
}

function pct(value) {
  return `${Math.round(num(value) * 100)}%`;
}

function asArray(value) {
  if (Array.isArray(value)) return value.filter(Boolean);
  if (typeof value === 'string') return value.split(/\n|、|;|；/).map((item) => item.trim()).filter(Boolean);
  return [];
}

function take(list, count = 5) {
  return asArray(list).slice(0, count);
}

function pickResults(results) {
  const monitor = results.monitor || {};
  const research = results.research || {};
  const survey = results.survey?.survey_results || results.survey || {};
  const compare = results.compare?.comparison_matrix || results.compare || {};
  const battlecard = results.battlecard?.battlecard || results.battlecard || {};
  const reviewer = results.reviewer?.review_feedback || results.reviewer || {};
  const citation = results.citation?.citation_report || results.citation || {};
  // ★ 提取Ontology图谱数据（支持多种嵌套格式）
  const ontology = results.ontology_graph
    || results.ontology?.ontology_graph
    || results.ontology
    || {};

  return {
    evidence: results.source_evidence || results.evidence || [],
    changes: monitor.changes_detected || [],
    research: research.research_results || [],
    survey,
    compare,
    battlecard,
    reviewer,
    citation,
    ontology,
  };
}

function dimensionsOf(matrix) {
  return Array.isArray(matrix?.dimensions) ? matrix.dimensions : [];
}

const WEIGHTS = {
  '产品功能': 0.16,
  'Product Features': 0.16,
  '价格与价值': 0.12,
  'Pricing & Value': 0.12,
  '用户体验': 0.14,
  'User Experience': 0.14,
  '市场份额与增长势能': 0.16,
  'Market Share & Momentum': 0.16,
  '客户口碑': 0.12,
  'Customer Sentiment': 0.12,
  '技术创新': 0.14,
  'Technology & Innovation': 0.14,
  '生态集成': 0.09,
  'Ecosystem & Integrations': 0.09,
  '支持与文档': 0.07,
  'Support & Documentation': 0.07,
};

function weightedPower(dims, side = 'our_score') {
  const rows = dimensionsOf({ dimensions: dims });
  if (!rows.length) return 0;
  let totalWeight = 0;
  let score = 0;
  rows.forEach((dim) => {
    const weight = WEIGHTS[dim.dimension] || 0.1;
    totalWeight += weight;
    score += num(dim[side], 5) * weight;
  });
  return totalWeight ? score / totalWeight : 0;
}

function winRateFromPower(ourPower, competitorPower) {
  return clamp(50 + (ourPower - competitorPower) * 6, 5, 95);
}

function isRealSourceUrl(url) {
  if (!url) return false;
  try {
    const parsed = new URL(url);
    if (!['http:', 'https:'].includes(parsed.protocol)) return false;
    return !parsed.hostname.replace(/^www\./, '').endsWith('example.com');
  } catch {
    return false;
  }
}

function sourceUrl(item) {
  if (!item) return '';
  const url = typeof item === 'string' ? item : item.url || item.link || item.source_url || '';
  return isRealSourceUrl(url) ? url : '';
}

function sourceTypeLabel(type) {
  const labels = {
    url: '网页',
    website: '网页',
    document: '文档',
    survey: '问卷',
    interview: '访谈',
    agent_analysis: 'Agent',
    agent_output: 'Agent',
  };
  return labels[type] || type || '来源';
}

function jumpToEvidence(locator, sourceAgent) {
  const locatorNode = String(locator || '').match(/^agent:\/\/([^/]+)/)?.[1] || '';
  const agentMap = {
    '监控采集 Agent': 'monitor',
    '深度研究 Agent': 'research',
    '用户调研 Agent': 'survey',
    '对比分析 Agent': 'compare',
    '对战卡 Agent': 'battlecard',
    '质量审查 Agent': 'reviewer',
    '来源溯源 Agent': 'citation',
  };
  const nodeId = locatorNode || agentMap[sourceAgent] || sourceAgent || '';
  const el = nodeId ? document.querySelector(`[data-agent-output="${nodeId}"]`) : null;
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    el.classList.add('agent-output-flash');
    window.setTimeout(() => el.classList.remove('agent-output-flash'), 1200);
  }
}

function fallbackEvidence(data) {
  return [
    ...take(data.changes, 4).map((change) => ({
      claim: change.title || change.summary,
      source_agent: '监控采集 Agent',
      source_type: '网站信息',
      url: change.source_url || change.url || '',
      detail: change.summary || '',
    })),
    ...take(data.research, 5).flatMap((insight) => {
      const url = sourceUrl(take(insight.sources, 1)[0]);
      return take(insight.key_findings, 2).map((finding) => ({
        claim: finding,
        source_agent: '深度研究 Agent',
        source_type: 'Agent 分析结果',
        url,
        detail: insight.topic || insight.summary || '',
      }));
    }),
    ...take(data.survey.key_findings, 4).map((finding) => ({
      claim: finding,
      source_agent: '用户调研 Agent',
      source_type: 'Agent 分析结果',
      url: '',
      detail: '由问卷、用户画像和访谈模拟归纳',
    })),
  ].filter((item) => item.claim);
}

function ReportMetric({ icon: Icon, label, value, caption }) {
  return (
    <div className="report-metric">
      <Icon size={18} />
      <span>{label}</span>
      <strong>{value}</strong>
      {caption && <small>{caption}</small>}
    </div>
  );
}

function ScoreBar({ value, max = 10, tone = 'blue' }) {
  const safe = clamp((num(value) / max) * 100);
  return (
    <div className={`report-score-track report-score-track--${tone}`}>
      <span style={{ width: `${safe}%` }} />
    </div>
  );
}

function impactOfDimension(dim, gap) {
  const weight = WEIGHTS[dim.dimension] || 0.1;
  const scoreGapImpact = clamp(Math.abs(gap) / 4, 0, 1);
  const weightImpact = clamp(weight / 0.16, 0, 1);
  return clamp(scoreGapImpact * 0.68 + weightImpact * 0.32, 0, 1);
}

function RadarChart({ dims }) {
  const [active, setActive] = useState(0);
  const rows = take(dims, 8);
  const size = 320;
  const cx = 160;
  const cy = 160;
  const radius = 108;

  if (!rows.length) return <p className="empty-text">暂无可绘制的八维度评分。</p>;

  const point = (index, value) => {
    const angle = -Math.PI / 2 + (Math.PI * 2 * index) / rows.length;
    const r = radius * clamp(num(value), 0, 10) / 10;
    return [cx + Math.cos(angle) * r, cy + Math.sin(angle) * r];
  };
  const ring = (level) => rows.map((_, index) => point(index, level)).map(([x, y]) => `${x},${y}`).join(' ');
  const our = rows.map((dim, index) => point(index, dim.our_score)).map(([x, y]) => `${x},${y}`).join(' ');
  const competitor = rows.map((dim, index) => point(index, dim.competitor_score)).map(([x, y]) => `${x},${y}`).join(' ');
  const activeDim = rows[active] || rows[0];

  return (
    <div className="battle-radar">
      <svg viewBox={`0 0 ${size} ${size}`} role="img" aria-label="八维度雷达图">
        {[2, 4, 6, 8, 10].map((level) => (
          <polygon key={level} points={ring(level)} className="radar-ring" />
        ))}
        {rows.map((dim, index) => {
          const [x, y] = point(index, 10);
          const [lx, ly] = point(index, 11.6);
          return (
            <g key={dim.dimension}>
              <line x1={cx} y1={cy} x2={x} y2={y} className="radar-axis" />
              <text x={lx} y={ly} textAnchor={lx < cx - 10 ? 'end' : lx > cx + 10 ? 'start' : 'middle'}>
                {dim.dimension}
              </text>
            </g>
          );
        })}
        <polygon points={our} className="radar-area radar-area--our" />
        <polygon points={competitor} className="radar-area radar-area--competitor" />
        {rows.map((dim, index) => {
          const [ox, oy] = point(index, dim.our_score);
          const [cx2, cy2] = point(index, dim.competitor_score);
          return (
            <g
              key={`${dim.dimension}-points`}
              role="button"
              tabIndex="0"
              className="radar-hit"
              onClick={() => setActive(index)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') setActive(index);
              }}
            >
              <circle cx={ox} cy={oy} r={active === index ? 6 : 4} className="radar-dot radar-dot--our" />
              <circle cx={cx2} cy={cy2} r={active === index ? 6 : 4} className="radar-dot radar-dot--competitor" />
            </g>
          );
        })}
      </svg>
      <div className="radar-detail">
        <strong>{activeDim.dimension}</strong>
        <span>我方 {num(activeDim.our_score).toFixed(1)} / 竞品 {num(activeDim.competitor_score).toFixed(1)}</span>
        <p>{activeDim.notes || '暂无该维度说明。'}</p>
      </div>
    </div>
  );
}

function ComparisonVisual({ matrix }) {
  const dims = take(dimensionsOf(matrix), 8);
  if (!dims.length) return <p className="empty-text">暂无对比矩阵。</p>;

  return (
    <div className="report-compare-list">
      {dims.map((dim) => {
        const gap = num(dim.our_score) - num(dim.competitor_score);
        const impact = impactOfDimension(dim, gap);
        const impactLevel = impact > 0.72 ? 'high' : impact > 0.42 ? 'medium' : 'low';
        const competitorTone = gap < -1.2 && impactLevel === 'high' ? 'red' : 'orange';
        return (
          <div
            className={`report-compare-row report-compare-row--${impactLevel}`}
            key={dim.dimension}
            style={{ '--impact-pct': `${Math.max(8, impact * 100)}%` }}
          >
            <div className="report-compare-head">
              <strong>{dim.dimension}</strong>
              <span className={`impact-badge ${gap >= 0 ? 'good' : 'warn'}`}>
                差距 {gap >= 0 ? '+' : ''}{gap.toFixed(1)} · 影响 {(impact * 100).toFixed(0)}%
              </span>
            </div>
            <div className="report-bars">
              <label>我方</label>
              <ScoreBar value={dim.our_score} tone="blue" />
              <b>{num(dim.our_score).toFixed(1)}</b>
              <label>竞品</label>
              <ScoreBar value={dim.competitor_score} tone={competitorTone} />
              <b>{num(dim.competitor_score).toFixed(1)}</b>
            </div>
            <div className="impact-strip" aria-hidden="true"><span /></div>
          </div>
        );
      })}
    </div>
  );
}

function HeatmapBlock({ label, items, tone, intensity, impactLevel }) {
  const value = clamp(intensity, 0, 1);
  const level = impactLevel || (value > 0.78 ? 'hot' : value > 0.58 ? 'green' : value > 0.34 ? 'pink' : 'gray');
  const labels = { hot: '最高影响', green: '高影响', pink: '中影响', gray: '低影响' };
  return (
    <div className={`strategy-heat-block strategy-heat-block--${tone} strategy-heat-block--${level}`}>
      <strong>{label}</strong>
      <span>{labels[level]}</span>
      {take(items, 3).map((item, index) => <p key={index}><HighlightText text={item} /></p>)}
      {!take(items, 1).length && <small>暂无结构化内容</small>}
    </div>
  );
}

function StrategyHeatmap({ battlecard, ourPower, competitorPower }) {
  const ourStrengths = take(battlecard.our_strengths, 6);
  const ourWeaknesses = take(battlecard.our_weaknesses, 6);
  const competitorStrengths = take(battlecard.competitor_strengths, 6);
  const competitorWeaknesses = take(battlecard.competitor_weaknesses, 6);
  const blocks = [
    { label: '我方优势', tone: 'good', items: ourStrengths, intensity: (ourPower / 10 + ourStrengths.length / 6) / 2 },
    { label: '我方短板', tone: 'weak', items: ourWeaknesses, intensity: (1 - ourPower / 10 + ourWeaknesses.length / 6) / 2 },
    { label: '竞品优势', tone: 'rival', items: competitorStrengths, intensity: (competitorPower / 10 + competitorStrengths.length / 6) / 2 },
    { label: '竞品弱点', tone: 'chance', items: competitorWeaknesses, intensity: (1 - competitorPower / 10 + competitorWeaknesses.length / 6) / 2 },
  ];
  const levels = ['hot', 'green', 'pink', 'gray'];
  const levelByLabel = new Map(
    [...blocks]
      .sort((a, b) => b.intensity - a.intensity)
      .map((block, index) => [block.label, levels[index] || 'gray']),
  );
  return (
    <div className="strategy-heatmap">
      {blocks.map((block) => (
        <HeatmapBlock
          key={block.label}
          {...block}
          impactLevel={levelByLabel.get(block.label)}
        />
      ))}
    </div>
  );
}

function PowerVisuals({ ourPower, competitorPower, winRate }) {
  return (
    <div className="battle-power-grid">
      <div className="battle-power-card">
        <h4>综合战力对比</h4>
        <div className="power-row"><span>我方</span><ScoreBar value={ourPower} tone="blue" /><strong>{ourPower.toFixed(1)}</strong></div>
        <div className="power-row"><span>竞品</span><ScoreBar value={competitorPower} tone="orange" /><strong>{competitorPower.toFixed(1)}</strong></div>
      </div>
      <div className="win-donut" style={{ '--win': `${winRate}%` }}>
        <strong>{winRate.toFixed(0)}%</strong>
        <span>预测胜率</span>
      </div>
    </div>
  );
}

function historyWinRows(records, currentCompetitor, currentWinRate) {
  const rows = asArray(records)
    .filter((record) => !currentCompetitor || record.competitor_name === currentCompetitor)
    .slice(-8)
    .map((record) => {
      const dims = dimensionsOf(record.analysis_result?.comparison_matrix || {});
      const our = weightedPower(dims, 'our_score');
      const comp = weightedPower(dims, 'competitor_score');
      return {
        label: String(record.created_at || '').slice(5, 10) || `#${record.id}`,
        value: dims.length ? winRateFromPower(our, comp) : num(record.quality_score, 6) * 10,
      };
    });
  if (!rows.length) rows.push({ label: '本次', value: currentWinRate });
  return rows.slice(-8);
}

function WinTrend({ rows }) {
  const [active, setActive] = useState(rows.length - 1);
  const width = 360;
  const height = 150;
  const pad = 24;
  const points = rows.map((row, index) => {
    const x = pad + (index * (width - pad * 2)) / Math.max(rows.length - 1, 1);
    const y = height - pad - (clamp(row.value, 0, 100) / 100) * (height - pad * 2);
    return { ...row, x, y };
  });
  const line = points.map((p) => `${p.x},${p.y}`).join(' ');
  const current = points[active] || points[points.length - 1];

  return (
    <div className="win-trend">
      <div className="win-trend-head">
        <h4>历史胜率波动</h4>
        <span>{current?.label} · {num(current?.value).toFixed(0)}%</span>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="历史胜率折线图">
        {[25, 50, 75].map((v) => {
          const y = height - pad - (v / 100) * (height - pad * 2);
          return <line key={v} x1={pad} y1={y} x2={width - pad} y2={y} className="trend-grid" />;
        })}
        <polyline points={line} className="trend-line" />
        {points.map((point, index) => (
          <g
            role="button"
            tabIndex="0"
            key={`${point.label}-${index}`}
            onClick={() => setActive(index)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') setActive(index);
            }}
          >
            <circle cx={point.x} cy={point.y} r={active === index ? 6 : 4} className="trend-dot" />
          </g>
        ))}
      </svg>
    </div>
  );
}

function EvidenceList({ evidence }) {
  const rows = take(evidence, 10);
  if (!rows.length) return <p className="empty-text">暂无可溯源结论。</p>;
  return (
    <div className="evidence-list">
      {rows.map((item, index) => (
        <div className="evidence-item" key={`${item.claim}-${index}`}>
          <p>{item.claim}</p>
          <div>
            <span>{item.source_agent || '系统汇总'}</span>
            <small>{item.detail || sourceTypeLabel(item.source_type) || 'Agent 分析结果'}</small>
            {isRealSourceUrl(item.url) && (
              <a href={item.url} target="_blank" rel="noreferrer">
                <Link2 size={13} />
                打开来源
              </a>
            )}
            {!isRealSourceUrl(item.url) && item.locator && (
              <button className="inline-source-jump" type="button" onClick={() => jumpToEvidence(item.locator, item.source_agent)}>
                <Link2 size={13} />
                查看{sourceTypeLabel(item.source_type)}
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function RecommendationList({ battlecard, reviewer }) {
  const differentiators = take(battlecard.key_differentiators, 4);
  const objections = Object.entries(battlecard.objection_handling || {}).slice(0, 3);
  const issues = take(reviewer.issues, 3).map((issue) => issue.description || issue.fix_instruction || String(issue));

  return (
    <div className="report-action-grid">
      <div>
        <h4><Lightbulb size={16} />优先打法</h4>
        <ul className="findings-list">
          {differentiators.map((item, index) => <li key={index}><HighlightText text={item} /></li>)}
        </ul>
        {!differentiators.length && <p className="empty-text">等待对战卡生成后展示。</p>}
      </div>
      <div>
        <h4><AlertTriangle size={16} />风险与异议</h4>
        <ul className="findings-list">
          {objections.map(([question]) => <li key={question}><HighlightText text={question} /></li>)}
          {issues.map((item, index) => <li key={`issue-${index}`}><HighlightText text={item} /></li>)}
        </ul>
        {!objections.length && !issues.length && <p className="empty-text">暂无被审查打回的问题。</p>}
      </div>
    </div>
  );
}

/* ── Ontology 知识图谱可视化 ── */
const LAYER_COLORS = { L1: '#2563eb', L2: '#16a34a', L3: '#9333ea', L4: '#ea580c', L5: '#6b7280' };

function OntologyGraph({ ontology }) {
  const nodes = ontology.nodes || [];
  const edges = ontology.relations || [];
  if (!nodes.length) return <p className="empty-text">暂无图谱数据。</p>;

  // 按层级分组
  const layers = {};
  nodes.forEach((n) => {
    const l = n.layer || 'L1';
    if (!layers[l]) layers[l] = [];
    layers[l].push(n);
  });

  return (
    <div className="ontology-graph">
      <div className="ontology-stats">
        <span>{nodes.length} 节点</span><span>{edges.length} 关系</span>
        {ontology.stats && <span>{ontology.stats.layers || Object.keys(layers).length} 层</span>}
      </div>
      <div className="ontology-layers">
        {Object.entries(layers).sort().map(([layer, layerNodes]) => (
          <div key={layer} className="ontology-layer">
            <div className="ontology-layer-label" style={{ borderColor: LAYER_COLORS[layer] || '#999' }}>
              L{layer}
            </div>
            <div className="ontology-layer-nodes">
              {layerNodes.map((n) => (
                <div key={n.id} className="ontology-node" style={{ borderColor: n.color || LAYER_COLORS[layer] || '#999', fontSize: n.size ? Math.max(10, Math.min(16, n.size - 8)) : 12 }}>
                  <span className="ontology-node-type">{n.entity_type || 'Entity'}</span>
                  <strong>{n.label || n.id}</strong>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      {edges.length > 0 && (
        <div className="ontology-edges">
          <span>关系: {edges.map((e) => e.relation_type).filter((v, i, a) => a.indexOf(v) === i).join(' | ')}</span>
        </div>
      )}
    </div>
  );
}

export function AnalysisReport({ competitor, urls = [], results = {}, qualityScore, telemetry, events = [], historyRecords = [] }) {
  const data = pickResults(results);
  const dims = dimensionsOf(data.compare);
  const ourPower = weightedPower(dims, 'our_score');
  const competitorPower = weightedPower(dims, 'competitor_score');
  const winRate = winRateFromPower(ourPower, competitorPower);
  const score = num(qualityScore || data.reviewer.overall_score);
  const sourceReliability = num(data.citation.overall_reliability_score);
  const tokenAgents = telemetry?.usage?.agents || {};
  const totalTokens = Object.values(tokenAgents).reduce(
    (sum, item) => sum + num(item.input ?? item.total_input) + num(item.output ?? item.total_output),
    0,
  );
  const evidence = data.evidence?.length ? data.evidence : fallbackEvidence(data);
  const sourceCount = new Set([
    ...(data.citation.source_list || []),
    ...(data.citation.source_details || []).map((item) => item.url || item.locator),
    ...evidence.map((item) => item.url || item.locator),
  ].filter(Boolean).filter((item) => !String(item).includes('example.com'))).size;
  const trendRows = useMemo(
    () => historyWinRows(historyRecords, competitor, winRate),
    [historyRecords, competitor, winRate],
  );

  return (
    <section className="analysis-report panel">
      <div className="report-head">
        <div>
          <div className="panel-kicker">最终分析报告</div>
          <h3>{competitor || '竞品'} 竞争情报摘要</h3>
          <p>整合 Agent 中间输出、质量审查、八维度评分、战术卡和来源证据。</p>
        </div>
        <div className="report-quality">
          <strong>{score ? score.toFixed(1) : '-'}</strong>
          <span>质量评分 / 10</span>
        </div>
      </div>

      <div className="report-metric-grid">
        <ReportMetric icon={CheckCircle2} label="完成节点" value={events.length} caption="SSE 节点输出" />
        <ReportMetric icon={BarChart3} label="对比维度" value={dims.length} caption="八维评分矩阵" />
        <ReportMetric icon={Link2} label="来源可信度" value={sourceReliability ? pct(sourceReliability) : '-'} caption={`${sourceCount || 0} 个来源/证据`} />
        <ReportMetric icon={Zap} label="Token 消耗" value={totalTokens ? totalTokens.toLocaleString() : '-'} caption={`${Object.keys(tokenAgents).length} 个 Agent`} />
      </div>

      <div className="report-layout">
        <div className="report-section report-section--wide">
          <h4><ClipboardList size={16} />关键发现与来源证据</h4>
          <EvidenceList evidence={evidence} />
        </div>

        <div className="report-section">
          <h4><Target size={16} />分析输入</h4>
          <p className="report-input-text">{urls.length ? urls.join(' / ') : '未提供 URL，使用竞品名称、知识库上下文和 Agent 过程输出分析。'}</p>
        </div>

        <div className="report-section report-section--wide">
          <h4><BarChart3 size={16} />八维雷达图</h4>
          <RadarChart dims={dims} />
        </div>

        <div className="report-section report-section--wide">
          <h4><Target size={16} />战术卡热力区</h4>
          <StrategyHeatmap battlecard={data.battlecard} ourPower={ourPower} competitorPower={competitorPower} />
        </div>

        <div className="report-section report-section--wide">
          <h4><BarChart3 size={16} />综合战力与胜率</h4>
          <PowerVisuals ourPower={ourPower} competitorPower={competitorPower} winRate={winRate} />
          <WinTrend rows={trendRows} />
        </div>

        <div className="report-section report-section--wide">
          <h4><BarChart3 size={16} />评分矩阵明细</h4>
          <ComparisonVisual matrix={data.compare} />
          {data.compare.overall_assessment && <p className="report-summary-text">{data.compare.overall_assessment}</p>}
        </div>

        <div className="report-section report-section--wide">
          <RecommendationList battlecard={data.battlecard} reviewer={data.reviewer} />
        </div>

        {data.ontology?.nodes?.length > 0 && (
          <div className="report-section report-section--wide">
            <h4><Network size={16} />Ontology 知识图谱</h4>
            <OntologyGraph ontology={data.ontology} />
          </div>
        )}
      </div>
    </section>
  );
}
