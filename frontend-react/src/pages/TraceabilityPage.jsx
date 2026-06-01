import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Clock,
  Database,
  Download,
  Eye,
  FileText,
  GitBranch,
  Hash,
  Link2,
  Radio,
  RefreshCw,
  ShieldCheck,
  X,
  Zap,
} from 'lucide-react';
import { ANALYSIS_RECORDS_UPDATED_EVENT, api } from '../api/client.js';
import { dagNodes } from '../data/agentFlow.js';
import { AnalysisReport } from '../components/agent/AnalysisReport.jsx';
import { AgentOutputCard } from '../components/agent/AgentOutputCard.jsx';
import { HighlightText } from '../components/common/HighlightText.jsx';

const RECORD_RESULT_NODES = ['monitor', 'research', 'survey', 'fact_check', 'compare', 'battlecard', 'reviewer', 'citation', 'feishu_push'];

function listOf(payload) {
  if (Array.isArray(payload)) return payload;
  return payload?.logs || payload?.items || payload?.events || payload?.nodes || payload?.snapshots || payload?.records || payload?.timeline || [];
}

function num(value) {
  return Number.isFinite(Number(value)) ? Number(value) : 0;
}

function formatTokens(value) {
  const v = num(value);
  if (v >= 10000) return `${(v / 10000).toFixed(1)}万`;
  if (v >= 1000) return `${(v / 1000).toFixed(1)}k`;
  return `${v}`;
}

function parseTime(value) {
  if (!value) return null;
  if (typeof value === 'number') {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
  }
  const raw = String(value).trim();
  if (!raw) return null;
  const hasZone = /(?:z|[+-]\d{2}:?\d{2})$/i.test(raw);
  const normalized = hasZone
    ? raw
    : `${raw.replace(' ', 'T')}Z`;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatTime(value) {
  const date = parseTime(value);
  if (!date) return '-';
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date).replace(/\//g, '-');
}

function getAgentLabel(agent) {
  return dagNodes.find((node) => node.id === agent)?.label || agent || '-';
}

function take(list, count = 5) {
  return Array.isArray(list) ? list.filter(Boolean).slice(0, count) : [];
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

function realSourceCount(result = {}) {
  const citationSources = result.citation_report?.source_list || [];
  const citationDetails = (result.citation_report?.source_details || []).map((item) => item?.url || item?.locator);
  const evidenceSources = (result.source_evidence || []).map((item) => item?.url);
  const evidenceLocators = (result.source_evidence || []).map((item) => item?.locator);
  const monitorSources = (result.changes_detected || []).map((item) => item?.source_url || item?.url);
  return new Set([
    ...citationSources,
    ...citationDetails,
    ...evidenceSources,
    ...evidenceLocators,
    ...monitorSources,
  ].filter(Boolean).filter((item) => !String(item).includes('example.com'))).size;
}

function buildResultsFromAnalysis(result = {}) {
  return {
    source_evidence: result.source_evidence || [],
    monitor: { changes_detected: result.changes_detected || [] },
    research: { research_results: result.research_results || [] },
    survey: { survey_results: result.survey_results || {} },
    fact_check: { fact_check_result: result.fact_check_result || {} },
    compare: { comparison_matrix: result.comparison_matrix || {} },
    battlecard: { battlecard: result.battlecard || {} },
    reviewer: { review_feedback: result.review_feedback || {} },
    citation: { citation_report: result.citation_report || {} },
    feishu_push: { feishu_push_status: result.feishu_push_status || '' },
  };
}

const SOURCE_AGENT_NODE_MAP = {
  monitor: 'monitor',
  research: 'research',
  survey: 'survey',
  fact_check: 'fact_check',
  factcheck: 'fact_check',
  compare: 'compare',
  battlecard: 'battlecard',
  reviewer: 'reviewer',
  citation: 'citation',
  '监控': 'monitor',
  '深度研究': 'research',
  '研究': 'research',
  '用户调研': 'survey',
  '调研': 'survey',
  '交叉验证': 'fact_check',
  '事实核验': 'fact_check',
  '对比分析': 'compare',
  '对战卡': 'battlecard',
  '质量审查': 'reviewer',
  '来源溯源': 'citation',
};

function nodeIdFromSource(locator, sourceAgent) {
  const direct = String(locator || '').match(/^agent:\/\/([^/?#]+)/i);
  if (direct?.[1]) return direct[1].replace(/-/g, '_');

  const raw = `${locator || ''} ${sourceAgent || ''}`.toLowerCase();
  const matched = Object.entries(SOURCE_AGENT_NODE_MAP)
    .find(([key]) => raw.includes(String(key).toLowerCase()));
  return matched?.[1] || '';
}

function RecordSourcePanel({ result, onJump }) {
  const evidence = result.source_evidence || [];
  const citation = result.citation_report || {};
  const details = citation.source_details || [];
  const sourceList = take(citation.source_list || [], 20)
    .filter((url) => isRealSourceUrl(url))
    .map((url) => ({ url, label: new URL(url).hostname.replace(/^www\./, '') }));

  // ★ 新增：source_urls 列表（来自后端 CitationAgent，含可达性+可信度）
  const sourceUrls = take(citation.source_urls || [], 50);

  const renderPointer = (item) => {
    const url = item.url || item.source_url;
    const locator = item.locator || item.pointer;
    if (isRealSourceUrl(url)) {
      return (
        <a href={url} target="_blank" rel="noreferrer">
          打开来源
        </a>
      );
    }
    if (locator) {
      return (
        <button className="inline-source-jump" type="button" onClick={() => onJump(locator, item.source_agent || item.sourceAgent)}>
          定位输出
        </button>
      );
    }
    return <span className="source-muted">暂无定位</span>;
  };

  return (
    <section className="record-source-panel">
      <div className="panel-heading compact-heading">
        <div>
          <div className="panel-kicker">来源证据</div>
          <h3>结论与原始证据映射</h3>
        </div>
        <span className="score-badge">{realSourceCount(result)} 个可定位来源</span>
      </div>

      {/* ★ 新增：一键跳转来源列表 */}
      {sourceUrls.length > 0 && (
        <div className="source-urls-section">
          <h4 className="source-urls-heading">
            <Link2 size={14} /> 引用来源一键跳转
          </h4>
          <ul className="source-urls-list">
            {sourceUrls.map((item, index) => (
              <li key={index} className={`source-url-item ${item.reachable ? 'reachable' : 'broken'}`}>
                <a
                  href={item.url}
                  target="_blank"
                  rel="noreferrer"
                  title={item.reachable ? '链接可达，点击跳转' : '链接可能失效'}
                >
                  <span className="source-url-dot" />
                  <span className="source-url-host">
                    {(() => {
                      try { return new URL(item.url).hostname.replace(/^www\./, ''); }
                      catch { return item.url; }
                    })()}
                  </span>
                  <span className="source-url-path">
                    {(() => {
                      try { return new URL(item.url).pathname.slice(0, 40); }
                      catch { return ''; }
                    })()}
                  </span>
                </a>
                <span className="source-url-meta">
                  {item.reachable ? (
                    <small className="meta-reachable">可达</small>
                  ) : (
                    <small className="meta-broken">失效</small>
                  )}
                  {item.reliability != null && (
                    <small className="meta-reliability">
                      可信度 {(num(item.reliability) * 100).toFixed(0)}%
                    </small>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="source-evidence-list">
        {evidence.map((item, index) => (
          <article className="source-evidence-row" key={`${item.claim || item.locator || index}`}>
            <div>
              <strong>{item.claim || item.detail || `证据 ${index + 1}`}</strong>
              <p>{item.preview || item.summary || item.context || item.locator || item.url || '该证据来自 Agent 中间输出。'}</p>
              <small>
                {item.source_type || 'agent_output'} · {getAgentLabel(nodeIdFromSource(item.locator, item.source_agent) || item.source_agent)}
              </small>
            </div>
            {renderPointer(item)}
          </article>
        ))}
        {!evidence.length && <p className="empty-text">暂无结构化来源证据。</p>}
      </div>

      {(details.length > 0 || sourceList.length > 0) && (
        <div className="source-detail-grid">
          {[...details, ...sourceList].map((item, index) => (
            <article className="source-detail-card" key={`${item.url || item.locator || item.label || index}`}>
              <strong>{item.label || item.title || item.url || item.locator || `来源 ${index + 1}`}</strong>
              <span>{item.source_type || (item.url ? 'url' : 'agent_output')}</span>
              <p>{item.preview || item.snippet || item.locator || item.url || '可在对应 Agent 输出中查看上下文。'}</p>
              <div className="source-detail-actions">
                {renderPointer(item)}
                {item.reliability != null && <small>可信度 {(num(item.reliability) * 100).toFixed(0)}%</small>}
                {item.status && <small>{item.status}</small>}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function buildRecordMarkdown(record) {
  const result = record.analysis_result || {};
  const matrix = result.comparison_matrix || {};
  const battlecard = result.battlecard || {};
  const survey = result.survey_results || {};
  const citation = result.citation_report || {};
  const evidence = take(result.source_evidence || [], 12);
  const sourceCount = realSourceCount(result);
  const dims = take(matrix.dimensions, 12);
  const findings = [
    ...take((result.research_results || []).flatMap((r) => r.key_findings || []), 6),
    ...take(survey.key_findings, 4),
  ];

  return [
    `# ${record.competitor_name} 竞品分析报告`,
    '',
    `- 记录 ID：${record.id}`,
    `- 生成时间：${formatTime(record.created_at)}`,
    `- 质量评分：${num(record.quality_score).toFixed(1)}/10`,
    `- 来源数量：${sourceCount}`,
    `- 来源可信度：${citation.overall_reliability_score != null ? `${(num(citation.overall_reliability_score) * 100).toFixed(0)}%` : '-'}`,
    '',
    '## 关键发现',
    ...(findings.length ? findings.map((item) => `- ${item}`) : ['- 暂无关键发现。']),
    '',
    '## 对比评分矩阵',
    '| 维度 | 我方 | 竞品 | 说明 |',
    '| --- | --- | --- | --- |',
    ...(dims.length ? dims.map((d) => `| ${d.dimension || '-'} | ${num(d.our_score).toFixed(1)} | ${num(d.competitor_score).toFixed(1)} | ${(d.notes || '').replace(/\n/g, ' ')} |`) : ['| 暂无 | - | - | - |']),
    '',
    '## 综合判断',
    matrix.overall_assessment || '暂无综合判断。',
    '',
    '## 来源证据链',
    ...(evidence.length ? evidence.map((item) => [
      `- ${item.claim || item.detail || '未命名结论'}`,
      `  - 来源：${item.source_agent || '系统汇总'}${isRealSourceUrl(item.url) ? ` ｜ ${item.url}` : item.locator ? ` ｜ ${item.locator}` : ''}`,
    ].join('\n')) : ['- 暂无结构化来源证据链。']),
    '',
    '## 战术卡',
    '### 核心差异化',
    ...(take(battlecard.key_differentiators, 6).map((item) => `- ${item}`)),
    '',
    '### 电梯演讲',
    battlecard.elevator_pitch || '暂无。',
    '',
    '## 调研摘要',
    `- 平均满意度：${survey.satisfaction_avg != null ? `${num(survey.satisfaction_avg).toFixed(1)}/10` : '-'}`,
    ...(take(survey.top_pain_points, 6).map((item) => `- 痛点：${item}`)),
  ].join('\n');
}

function downloadRecord(record, format = 'json') {
  const isMarkdown = format === 'md';
  const content = isMarkdown ? buildRecordMarkdown(record) : JSON.stringify(record, null, 2);
  const blob = new Blob([content], { type: isMarkdown ? 'text/markdown;charset=utf-8' : 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `competitive-report-${record.competitor_name || record.id}-${String(record.created_at || '').slice(0, 10) || 'latest'}.${isMarkdown ? 'md' : 'json'}`;
  a.click();
  URL.revokeObjectURL(url);
}

function downloadRecordPdf(record) {
  if (!record?.id) return;
  const a = document.createElement('a');
  a.href = `${api.baseUrl}/analysis/records/${record.id}/report.pdf`;
  a.download = `competitive-report-${record.competitor_name || record.id}-${String(record.created_at || '').slice(0, 10) || 'latest'}.pdf`;
  a.click();
}

function normalizeTokenUsage(usage, infra) {
  const agents = usage?.agents || infra?.tokens?.agents || {};
  const rows = Object.entries(agents).map(([agent, item]) => {
    const input = num(item.input ?? item.total_input);
    const output = num(item.output ?? item.total_output);
    return { agent, input, output, total: input + output };
  });
  const totalInput = usage?.total_input ?? infra?.tokens?.total_input ?? rows.reduce((sum, item) => sum + item.input, 0);
  const totalOutput = usage?.total_output ?? infra?.tokens?.total_output ?? rows.reduce((sum, item) => sum + item.output, 0);
  const estimatedCost = num(
    usage?.estimated_cost
    ?? infra?.tokens?.estimated_cost
    ?? ((num(totalInput) / 1000) * 0.0008 + (num(totalOutput) / 1000) * 0.002),
  );
  return {
    rows: rows.sort((a, b) => b.total - a.total),
    totalInput: num(totalInput),
    totalOutput: num(totalOutput),
    estimatedCost,
  };
}

function normalizeAnomalies(payload) {
  const rawAgent = payload?.agent_anomalies;
  const agentItems = Array.isArray(rawAgent)
    ? rawAgent
    : listOf(rawAgent?.anomalies || rawAgent?.items || rawAgent?.logs || []);
  const auditItems = listOf(payload?.audit_violations);
  return { agentItems, auditItems, total: agentItems.length + auditItems.length };
}

const TRACE_MODULE_LABELS = {
  overview: '总览',
  logs: '决策日志',
  tokens: 'Token',
  events: '事件总线',
  dag: 'DAG',
  audit: '审计异常',
};

function getRecordAgentTrace(record) {
  const trace = record?.analysis_result?.agent_trace || {};
  if (Array.isArray(trace)) {
    return trace.map((item, index) => [item.agent || item.node_id || item.node || `agent_${index + 1}`, item]);
  }
  return Object.entries(trace).filter(([, value]) => value && typeof value === 'object');
}

function summarizeRecordAgentOutput(agent, data = {}) {
  if (data.error) return `执行失败：${data.error}`;
  const payload = data[agent] && typeof data[agent] === 'object' ? data[agent] : data;
  if (agent === 'monitor') return `监控采集完成，发现 ${listOf(payload.changes_detected).length} 条竞品动态。`;
  if (agent === 'research') return `深度研究完成，沉淀 ${listOf(payload.research_results).length} 组研究结果。`;
  if (agent === 'survey') return `用户调研完成，满意度 ${payload.survey_results?.satisfaction_avg ?? '-'}。`;
  if (agent === 'fact_check') return `交叉验证完成，置信度 ${payload.fact_check_result?.overall_confidence != null ? `${(num(payload.fact_check_result.overall_confidence) * 100).toFixed(0)}%` : '-'}。`;
  if (agent === 'compare') return `对比分析完成，输出 ${listOf(payload.comparison_matrix?.dimensions).length} 个评分维度。`;
  if (agent === 'battlecard') return `对战卡完成，输出 ${listOf(payload.battlecard?.key_differentiators).length} 条差异化论点。`;
  if (agent === 'reviewer') return `质量审查完成，评分 ${num(payload.review_feedback?.overall_score ?? payload.quality_score).toFixed(1)}/10。`;
  if (agent === 'citation') return `来源溯源完成，验证 ${payload.citation_report?.total_sources ?? realSourceCount(payload)} 个来源。`;
  return data.summary || data.reasoning || data.message || `${getAgentLabel(agent)} 输出已归档。`;
}

function buildRecordDecisionLogs(record) {
  const result = record?.analysis_result || {};
  const explicit = listOf(result.decision_logs || result.agent_logs || result.logs);
  if (explicit.length) return explicit;
  return getRecordAgentTrace(record).map(([agent, data], index) => ({
    id: `${record.id}-${agent}-${index}`,
    agent_name: agent,
    phase: data?._meta?.phase || '归档输出',
    reasoning: summarizeRecordAgentOutput(agent, data),
    status: data?.error ? 'failed' : 'completed',
    created_at: data?.timestamp || record.created_at,
  }));
}

function buildRecordEvents(record) {
  const result = record?.analysis_result || {};
  const explicit = listOf(result.events || result.event_bus || result.infra_events);
  if (explicit.length) return explicit;
  return getRecordAgentTrace(record).map(([agent, data], index) => ({
    id: `${record.id}-${agent}-event-${index}`,
    event_type: data?.error ? 'agent_failed' : 'agent_completed',
    source: agent,
    data: { summary: summarizeRecordAgentOutput(agent, data), record_id: record.id },
    timestamp: data?.timestamp || record.created_at,
  }));
}

function buildRecordDag(record) {
  const result = record?.analysis_result || {};
  if (result.dag_snapshot) return result.dag_snapshot;
  const traceEntries = getRecordAgentTrace(record);
  const completed = new Set(traceEntries.map(([agent]) => agent));
  const nodes = dagNodes
    .filter((node) => completed.has(node.id) || RECORD_RESULT_NODES.includes(node.id))
    .map((node) => ({
      node_id: node.id,
      label: node.label,
      icon: node.icon,
      status: completed.has(node.id) ? 'completed' : 'idle',
      desc: completed.has(node.id) ? '已归档' : '本次无输出',
    }));
  const done = nodes.filter((node) => node.status === 'completed').length;
  return { total_progress: nodes.length ? done / nodes.length : 0, nodes };
}

function buildRecordAudits(record) {
  const result = record?.analysis_result || {};
  const explicit = listOf(result.audit_logs || result.audits);
  if (explicit.length) return explicit;
  const review = result.review_feedback || {};
  const fact = result.fact_check_result || {};
  const citation = result.citation_report || {};
  const rows = [
    {
      id: `${record.id}-review`,
      action_type: '质量审查',
      operator: 'ReviewerAgent',
      target: `质量评分 ${num(record.quality_score || review.overall_score).toFixed(1)}/10`,
      severity: review.approved === false || num(record.quality_score) < 7 ? 'medium' : 'low',
      created_at: record.created_at,
    },
    {
      id: `${record.id}-fact`,
      action_type: '交叉验证',
      operator: 'FactCheckAgent',
      target: `置信度 ${fact.overall_confidence != null ? `${(num(fact.overall_confidence) * 100).toFixed(0)}%` : '-'}`,
      severity: num(fact.overall_confidence) < 0.6 ? 'medium' : 'low',
      created_at: record.created_at,
    },
    {
      id: `${record.id}-citation`,
      action_type: '来源溯源',
      operator: 'CitationAgent',
      target: `可定位来源 ${realSourceCount(result)} 个`,
      severity: realSourceCount(result) ? 'low' : 'medium',
      created_at: record.created_at,
    },
  ];
  return rows;
}

function buildRecordAnomalies(record) {
  const result = record?.analysis_result || {};
  const issues = listOf(result.review_feedback?.issues);
  const missing = listOf(result.citation_report?.missing_citations);
  const agentItems = [
    ...issues.map((item) => ({
      agent: 'reviewer',
      description: item.description || String(item),
    })),
    ...missing.map((item) => ({
      agent: 'citation',
      description: item.claim || item.reason || String(item),
    })),
  ];
  return { agentItems, auditItems: [], total: agentItems.length };
}

function recordTokenUsage(record) {
  return normalizeTokenUsage(record?.analysis_result?.token_usage || {}, null);
}

function Metric({ icon: Icon, label, value, tone = 'info' }) {
  return (
    <article className={`metric-card ${tone}`}>
      <Icon size={22} />
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function TokenUsagePanel({ usage, quota }) {
  const maxTotal = Math.max(...usage.rows.map((row) => row.total), 1);
  const quotaMap = quota?.quotas || {};

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <div className="panel-kicker">LLM 资源审计</div>
          <h3>各 Agent Token 消耗</h3>
        </div>
        <div className="token-total">
          <span>输入 {usage.totalInput.toLocaleString()}</span>
          <span>输出 {usage.totalOutput.toLocaleString()}</span>
          <span>预估 ¥{usage.estimatedCost.toFixed(4)}</span>
        </div>
      </div>

      <div className="token-grid">
        {usage.rows.map((row) => {
          const quotaInfo = quotaMap[row.agent] || {};
          const quotaTotal = num(quotaInfo.quota_input) + num(quotaInfo.quota_output);
          const quotaUsed = num(quotaInfo.used_input) + num(quotaInfo.used_output);
          const quotaPct = quotaTotal ? Math.min(100, (quotaUsed / quotaTotal) * 100) : 0;
          return (
            <div className="token-card" key={row.agent}>
              <div className="token-card-head">
                <strong>{getAgentLabel(row.agent)}</strong>
                <span>{formatTokens(row.total)} tokens</span>
              </div>
              <div className="token-bar">
                <div className="token-bar-input" style={{ flex: Math.max(row.input, 1) }} title={`输入 ${row.input}`} />
                <div className="token-bar-output" style={{ flex: Math.max(row.output, 1) }} title={`输出 ${row.output}`} />
              </div>
              <div className="token-detail">
                <small>输入 {row.input.toLocaleString()}</small>
                <small>输出 {row.output.toLocaleString()}</small>
              </div>
              <div className="trace-token-rank">
                <span style={{ width: `${Math.max((row.total / maxTotal) * 100, 4)}%` }} />
              </div>
              {quotaTotal > 0 && (
                <small className="quota-line">配额使用 {quotaPct.toFixed(0)}%</small>
              )}
            </div>
          );
        })}
        {!usage.rows.length && <p className="empty-text">暂无 Token 消耗。运行一次工作台分析后会自动记录。</p>}
      </div>
    </section>
  );
}

function LogsPanel({ logs }) {
  return (
    <section className="panel trace-fixed-panel">
      <div className="panel-heading">
        <div>
          <div className="panel-kicker">决策回放</div>
          <h3>Agent 决策日志</h3>
        </div>
      </div>
      <div className="trace-table trace-scroll-frame">
        <div className="trace-table-head">
          <span>Agent</span><span>阶段</span><span>推理/动作</span><span>状态</span><span>时间</span>
        </div>
        {logs.map((log, index) => (
          <div className="trace-table-row" key={log.id || `${log.agent_name}-${index}`}>
            <span className="trace-agent">{getAgentLabel(log.agent_name || log.agent)}</span>
            <span className="trace-phase">{log.phase || log.step || '-'}</span>
            <span className="trace-decision"><strong>{log.reasoning || log.decision || log.action || log.message || '-'}</strong></span>
            <span className={log.status === 'failed' ? 'severity-inline high' : 'severity-inline low'}>{log.status || 'completed'}</span>
            <small>{formatTime(log.created_at || log.timestamp)}</small>
          </div>
        ))}
        {!logs.length && <p className="empty-text">暂无决策日志。</p>}
      </div>
    </section>
  );
}

function EventBusPanel({ events }) {
  return (
    <section className="panel trace-fixed-panel">
      <div className="panel-heading">
        <div>
          <div className="panel-kicker">EventBus</div>
          <h3>事件总线</h3>
        </div>
      </div>
      <div className="trace-table trace-scroll-frame">
        <div className="trace-table-head">
          <span>事件ID</span><span>类型</span><span>来源</span><span>数据摘要</span><span>时间</span>
        </div>
        {events.map((evt, index) => (
          <div className="trace-table-row" key={evt.id || evt.event_id || index}>
            <small className="trace-id">{String(evt.id || evt.event_id || '').slice(0, 8) || '-'}</small>
            <span className="trace-agent">{evt.type || evt.event_type || '-'}</span>
            <span>{getAgentLabel(evt.source || evt.agent)}</span>
            <span className="trace-decision"><strong>{typeof evt.data === 'object' ? JSON.stringify(evt.data).slice(0, 120) : (evt.data || '-')}</strong></span>
            <small>{formatTime(evt.timestamp || evt.created_at)}</small>
          </div>
        ))}
        {!events.length && <p className="empty-text">暂无事件记录。</p>}
      </div>
    </section>
  );
}

function MiniBar({ label, value, max = 10, tone = 'blue', onFocus, active }) {
  const pctValue = Math.max(0, Math.min(100, (num(value) / max) * 100));
  return (
    <button
      className={`chart-bar-row ${active ? 'active' : ''}`}
      type="button"
      onClick={onFocus}
      onMouseEnter={onFocus}
    >
      <span>{label}</span>
      <div className="chart-bar-track">
        <i className={`chart-bar-fill ${tone}`} style={{ width: `${pctValue}%` }} />
      </div>
      <strong>{num(value).toFixed(1)}</strong>
    </button>
  );
}

function RecordVisuals({ record }) {
  const [chart, setChart] = useState('compare');
  const [focused, setFocused] = useState(null);
  const result = record.analysis_result || {};
  const matrix = result.comparison_matrix || {};
  const survey = result.survey_results || {};
  const citation = result.citation_report || {};
  const battlecard = result.battlecard || {};
  const dims = take(matrix.dimensions, 12);
  const painPoints = take(survey.top_pain_points, 6);
  const reliabilityRows = Object.entries(citation.reliability_distribution || {});
  const maxPain = Math.max(painPoints.length, 1);

  const tabs = [
    { id: 'compare', label: '评分矩阵' },
    { id: 'survey', label: '调研痛点' },
    { id: 'source', label: '来源可信度' },
    { id: 'strategy', label: '战术卡' },
  ];

  return (
    <section className="record-visual-panel">
      <div className="record-chart-tabs">
        {tabs.map((item) => (
          <button key={item.id} className={chart === item.id ? 'active' : ''} type="button" onClick={() => setChart(item.id)}>
            {item.label}
          </button>
        ))}
      </div>

      {chart === 'compare' && (
        <div className="interactive-chart">
          <div className="chart-legend"><span className="dot blue" />我方 <span className="dot orange" />竞品</div>
          {dims.map((dim, index) => (
            <div className="compare-chart-pair" key={dim.dimension || index}>
              <MiniBar label={dim.dimension || `维度 ${index + 1}`} value={dim.our_score} tone="blue" active={focused === `${index}-our`} onFocus={() => setFocused(`${index}-our`)} />
              <MiniBar label="竞品得分" value={dim.competitor_score} tone="orange" active={focused === `${index}-comp`} onFocus={() => setFocused(`${index}-comp`)} />
              {(focused === `${index}-our` || focused === `${index}-comp`) && <p>{dim.notes || '暂无评分说明。'}</p>}
            </div>
          ))}
          {!dims.length && <p className="empty-text">暂无评分矩阵。</p>}
        </div>
      )}

      {chart === 'survey' && (
        <div className="interactive-chart">
          <div className="survey-score-dial" style={{ '--score': `${Math.max(0, Math.min(100, num(survey.satisfaction_avg) * 10))}%` }}>
            <strong>{survey.satisfaction_avg != null ? num(survey.satisfaction_avg).toFixed(1) : '-'}</strong>
            <span>平均满意度 / 10</span>
          </div>
          {painPoints.map((item, index) => (
            <MiniBar
              key={item}
              label={item}
              value={maxPain - index}
              max={maxPain}
              tone={index < 2 ? 'orange' : 'blue'}
              active={focused === `pain-${index}`}
              onFocus={() => setFocused(`pain-${index}`)}
            />
          ))}
          {!painPoints.length && <p className="empty-text">暂无调研痛点。</p>}
        </div>
      )}

      {chart === 'source' && (
        <div className="interactive-chart">
          <div className="source-ring" style={{ '--score': `${Math.max(0, Math.min(100, num(citation.overall_reliability_score) * 100))}%` }}>
            <strong>{citation.overall_reliability_score != null ? `${(num(citation.overall_reliability_score) * 100).toFixed(0)}%` : '-'}</strong>
            <span>整体可信度</span>
          </div>
          {reliabilityRows.map(([bucket, count]) => (
            <MiniBar key={bucket} label={`可信度 ${bucket}`} value={count} max={Math.max(...reliabilityRows.map(([, v]) => num(v)), 1)} tone="blue" />
          ))}
          <p className="chart-note">可溯源证据 {realSourceCount(record.analysis_result || {})} 个，已定位 {citation.verified_sources || 0} 个，失效 URL {citation.broken_links || 0} 个。</p>
        </div>
      )}

      {chart === 'strategy' && (
        <div className="strategy-map">
          {[
            ['我方优势', battlecard.our_strengths],
            ['我方短板', battlecard.our_weaknesses],
            ['竞品优势', battlecard.competitor_strengths],
            ['差异化论点', battlecard.key_differentiators],
          ].map(([label, items]) => (
            <div className="strategy-map-card" key={label}>
              <strong>{label}</strong>
              {take(items, 4).map((item, index) => <p key={index}><HighlightText text={item} /></p>)}
              {!take(items, 1).length && <small>暂无内容</small>}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function RecordDetail({ record, onClose, historyRecords = [] }) {
  const [detailTab, setDetailTab] = useState('report');

  useEffect(() => {
    setDetailTab('report');
  }, [record?.id]);

  if (!record) return null;
  const result = record.analysis_result || {};
  const results = buildResultsFromAnalysis(result);
  const recordEntries = RECORD_RESULT_NODES
    .filter((id) => results[id] && Object.keys(results[id] || {}).length)
    .map((id) => [id, results[id]]);
  const detailTabs = [
    { id: 'report', label: '最终报告' },
    { id: 'nodes', label: 'Agent 结果', count: recordEntries.length },
    { id: 'visuals', label: '图表分析' },
    { id: 'sources', label: '来源证据', count: realSourceCount(result) },
    { id: 'dag', label: 'DAG 快照', count: result.dag_snapshot ? 1 : 0 },
  ];
  const jumpToNode = (locator, sourceAgent) => {
    const nodeId = nodeIdFromSource(locator, sourceAgent);
    if (!nodeId) return;
    setDetailTab('nodes');
    window.setTimeout(() => {
      const node = document.querySelector(`[data-agent-output="${nodeId}"]`);
      node?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      node?.classList.add('source-focus');
      window.setTimeout(() => node?.classList.remove('source-focus'), 1400);
    }, 80);
  };

  return (
    <section className="panel record-detail-panel">
      <div className="record-detail-head">
        <div>
          <div className="panel-kicker">分析记录详情</div>
          <h3>{record.competitor_name} 竞品分析报告</h3>
          <p>记录 ID {record.id} · {formatTime(record.created_at)}</p>
        </div>
        <div className="record-detail-actions">
          <button className="secondary-button" type="button" onClick={() => downloadRecordPdf(record)}>
            <Download size={16} /> 下载 PDF
          </button>
          <button className="secondary-button" type="button" onClick={() => downloadRecord(record, 'json')}>
            <Download size={16} /> 下载 JSON
          </button>
          <button className="ghost-button record-back-button" type="button" onClick={onClose} title="返回分析记录列表">
            <X size={18} /> 返回列表
          </button>
        </div>
      </div>

      <div className="record-detail-metrics">
        <Metric icon={Hash} label="记录编号" value={record.id} />
        <Metric icon={BarChart3} label="质量评分" value={`${num(record.quality_score).toFixed(1)}/10`} tone={num(record.quality_score) >= 7 ? 'good' : 'warn'} />
        <Metric icon={Link2} label="来源数量" value={realSourceCount(result)} />
        <Metric icon={ShieldCheck} label="可信度" value={result.citation_report?.overall_reliability_score != null ? `${(num(result.citation_report.overall_reliability_score) * 100).toFixed(0)}%` : '-'} />
      </div>

      <div className="record-detail-tabs" role="tablist" aria-label="分析记录详情">
        {detailTabs.map((tab) => (
          <button
            key={tab.id}
            className={detailTab === tab.id ? 'active' : ''}
            type="button"
            role="tab"
            aria-selected={detailTab === tab.id}
            onClick={() => setDetailTab(tab.id)}
          >
            {tab.label}
            {tab.count != null && <span>{tab.count}</span>}
          </button>
        ))}
      </div>

      <div className="record-detail-frame">
        {detailTab === 'report' && (
          <AnalysisReport
            competitor={record.competitor_name}
            urls={record.request_urls || []}
            results={results}
            qualityScore={record.quality_score}
            telemetry={{ usage: result.token_usage || {} }}
            events={recordEntries.map(([nodeId]) => ({ nodeId }))}
            historyRecords={historyRecords}
          />
        )}

        {detailTab === 'nodes' && (
          <div className="record-detail-block">
            <div className="panel-heading compact-heading">
              <div>
                <div className="panel-kicker">完整节点结果</div>
                <h3>工作台本次分析得到的全部 Agent 输出</h3>
              </div>
            </div>
            <section className="result-cards-grid record-node-results">
              {recordEntries.map(([nodeId, data]) => (
                <AgentOutputCard key={nodeId} nodeId={nodeId} data={data} />
              ))}
            </section>
            {!recordEntries.length && <p className="empty-text">暂无 Agent 中间结果。</p>}
          </div>
        )}

        {detailTab === 'visuals' && <RecordVisuals record={record} />}

        {detailTab === 'sources' && <RecordSourcePanel result={result} onJump={jumpToNode} />}

        {detailTab === 'dag' && (
          result.dag_snapshot
            ? <DagPanel dag={result.dag_snapshot} snapshots={[]} title="本次分析 DAG 快照" />
            : <p className="empty-text">暂无 DAG 快照。</p>
        )}
      </div>
    </section>
  );
}

function RecordsPanel({ records, selectedRecord, onSelect, onClose }) {
  if (selectedRecord) {
    return <RecordDetail record={selectedRecord} onClose={onClose} historyRecords={records} />;
  }

  return (
    <section className="panel records-list-panel">
      <div className="panel-heading">
        <div>
          <div className="panel-kicker">历史分析</div>
          <h3>分析记录与结构化结果</h3>
        </div>
      </div>
      <div className="trace-table trace-table--records">
        <div className="trace-table-head">
          <span>ID</span><span>竞品</span><span>质量评分</span><span>来源数</span><span>时间</span><span>操作</span>
        </div>
        {records.map((record) => (
          <div
            className={`trace-table-row trace-table-row--clickable ${selectedRecord?.id === record.id ? 'active' : ''}`}
            key={record.id}
            role="button"
            tabIndex="0"
            onClick={() => onSelect(record)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') onSelect(record);
            }}
          >
            <span><Hash size={14} /> {record.id}</span>
            <strong>{record.competitor_name}</strong>
            <span className={`score-inline ${num(record.quality_score) >= 7 ? 'good' : 'warn'}`}>{num(record.quality_score).toFixed(1)}/10</span>
            <span>{realSourceCount(record.analysis_result || {}) || record.request_urls?.filter(isRealSourceUrl).length || 0} 个来源</span>
            <small>{formatTime(record.created_at)}</small>
            <span className="record-row-actions">
              <button className="ghost-button" type="button" onClick={(event) => { event.stopPropagation(); onSelect(record); }} title="查看报告详情">
                <Eye size={16} />
              </button>
              <button className="ghost-button" type="button" onClick={(event) => { event.stopPropagation(); downloadRecordPdf(record); }} title="下载 PDF">
                <Download size={16} />
              </button>
            </span>
          </div>
        ))}
        {!records.length && <p className="empty-text">暂无分析记录。</p>}
      </div>
    </section>
  );
}

function TraceRecordListPanel({ records, moduleLabel, onSelect }) {
  return (
    <section className="panel records-list-panel trace-record-list-panel">
      <div className="panel-heading">
        <div>
          <div className="panel-kicker">{moduleLabel}</div>
          <h3>分析记录</h3>
        </div>
      </div>
      <div className="trace-table trace-table--records">
        <div className="trace-table-head">
          <span>ID</span><span>竞品</span><span>质量评分</span><span>来源数</span><span>时间</span><span>操作</span>
        </div>
        {records.map((record) => (
          <div
            className="trace-table-row trace-table-row--clickable"
            key={record.id}
            role="button"
            tabIndex="0"
            onClick={() => onSelect(record)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') onSelect(record);
            }}
          >
            <span><Hash size={14} /> {record.id}</span>
            <strong>{record.competitor_name}</strong>
            <span className={`score-inline ${num(record.quality_score) >= 7 ? 'good' : 'warn'}`}>{num(record.quality_score).toFixed(1)}/10</span>
            <span>{realSourceCount(record.analysis_result || {}) || record.request_urls?.filter(isRealSourceUrl).length || 0} 个来源</span>
            <small>{formatTime(record.created_at)}</small>
            <span className="record-row-actions">
              <button className="ghost-button" type="button" onClick={(event) => { event.stopPropagation(); onSelect(record); }} title={`查看${moduleLabel}详情`}>
                <Eye size={16} />
              </button>
            </span>
          </div>
        ))}
        {!records.length && <p className="empty-text">暂无分析记录。</p>}
      </div>
    </section>
  );
}

function RecordOverviewPanel({ record }) {
  const result = record.analysis_result || {};
  const usage = recordTokenUsage(record);
  return (
    <section className="trace-overview-grid">
      <div className="record-detail-metrics">
        <Metric icon={Hash} label="记录编号" value={record.id} />
        <Metric icon={BarChart3} label="质量评分" value={`${num(record.quality_score).toFixed(1)}/10`} tone={num(record.quality_score) >= 7 ? 'good' : 'warn'} />
        <Metric icon={Link2} label="来源数量" value={realSourceCount(result)} />
        <Metric icon={Zap} label="Token 总量" value={formatTokens(usage.totalInput + usage.totalOutput)} />
      </div>
      <OpsLoopPanel records={[record]} />
      <RecordVisuals record={record} />
    </section>
  );
}

function TraceRecordModuleDetail({ record, activeTab, onClose }) {
  const moduleLabel = TRACE_MODULE_LABELS[activeTab] || '详情';
  let content = null;
  if (activeTab === 'overview') {
    content = <RecordOverviewPanel record={record} />;
  } else if (activeTab === 'logs') {
    content = <LogsPanel logs={buildRecordDecisionLogs(record)} />;
  } else if (activeTab === 'tokens') {
    content = <TokenUsagePanel usage={recordTokenUsage(record)} quota={null} />;
  } else if (activeTab === 'events') {
    content = <EventBusPanel events={buildRecordEvents(record)} />;
  } else if (activeTab === 'dag') {
    content = <DagPanel dag={buildRecordDag(record)} snapshots={[]} title="本次分析 DAG 快照" />;
  } else if (activeTab === 'audit') {
    content = <AuditPanel audits={buildRecordAudits(record)} anomalies={buildRecordAnomalies(record)} />;
  }

  return (
    <section className="trace-record-module-detail">
      <div className="panel trace-record-detail-head">
        <div>
          <div className="panel-kicker">{moduleLabel}</div>
          <h3>{record.competitor_name}</h3>
          <p>记录 ID {record.id} · {formatTime(record.created_at)}</p>
        </div>
        <button className="ghost-button record-back-button" type="button" onClick={onClose}>
          <X size={18} /> 返回列表
        </button>
      </div>
      <div className="trace-record-detail-body">
        {content}
      </div>
    </section>
  );
}

function RecordShortcutPanel({ records, onSelect }) {
  return (
    <section className="panel record-shortcut-panel">
      <div className="panel-heading compact-heading">
        <div>
          <div className="panel-kicker">分析记录</div>
          <h3>历史任务</h3>
        </div>
        <span className="score-badge">{records.length}</span>
      </div>
      <div className="record-shortcut-list">
        {records.map((record) => (
          <button type="button" key={record.id} onClick={() => onSelect(record)}>
            <strong>{record.competitor_name}</strong>
            <span>{num(record.quality_score).toFixed(1)}/10</span>
            <small>{formatTime(record.created_at)}</small>
          </button>
        ))}
        {!records.length && <p className="empty-text">暂无分析记录。</p>}
      </div>
    </section>
  );
}

function TraceModuleLayout({ children, records, onSelect }) {
  return (
    <section className="trace-module-grid">
      <div>{children}</div>
      <RecordShortcutPanel records={records} onSelect={onSelect} />
    </section>
  );
}

function DagPanel({ dag, snapshots, title = '当前 Agent 编排状态' }) {
  const nodes = listOf(dag?.nodes || dag);
  const progress = num(dag?.total_progress ?? dag?.progress);

  return (
    <section className="panel trace-fixed-panel">
      <div className="panel-heading">
        <div>
          <div className="panel-kicker">DAG 快照</div>
          <h3>{title}</h3>
        </div>
        <span className="score-badge">进度 {(progress * 100).toFixed(0)}%</span>
      </div>
      <div className="trace-scroll-frame trace-scroll-frame--dag">
        <div className="dag-grid">
          {nodes.map((node, index) => (
            <div className="dag-node" key={node.node_id || node.id || node.name || index}>
              <span>{node.icon || index + 1}</span>
              <strong>{node.label || getAgentLabel(node.node_id || node.id || node.name)}</strong>
              <small>{node.status || node.desc || '-'}</small>
            </div>
          ))}
          {!nodes.length && <p className="empty-text">暂无 DAG 快照。</p>}
        </div>

        {snapshots.length > 0 && (
          <>
          <div className="panel-heading" style={{ marginTop: 24 }}>
            <div>
              <div className="panel-kicker">演化快照</div>
              <h3>分析结果沉淀</h3>
            </div>
          </div>
          <div className="trace-table">
            <div className="trace-table-head">
              <span>ID</span><span>竞品</span><span>Agent</span><span>维度</span><span>置信度</span>
            </div>
            {snapshots.map((snapshot, index) => (
              <div className="trace-table-row" key={snapshot.id || index}>
                <small>{snapshot.id || '-'}</small>
                <span>{snapshot.competitor || '-'}</span>
                <span className="trace-agent">{getAgentLabel(snapshot.agent_name)}</span>
                <span className="trace-decision">{snapshot.dimension || '-'}</span>
                <span>{snapshot.confidence != null ? `${(num(snapshot.confidence) * 100).toFixed(0)}%` : '-'}</span>
              </div>
            ))}
          </div>
          </>
        )}
      </div>
    </section>
  );
}

function AuditPanel({ audits, anomalies }) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <div className="panel-kicker">审计与异常</div>
          <h3>合规操作、异常检测和风险信号</h3>
        </div>
      </div>

      <div className="trace-table">
        <div className="trace-table-head">
          <span>类型</span><span>操作者</span><span>目标</span><span>级别</span><span>时间</span>
        </div>
        {audits.map((audit, index) => (
          <div className="trace-table-row" key={audit.id || index}>
            <span className="trace-agent">{audit.action_type || audit.type || '-'}</span>
            <span>{audit.operator || '-'}</span>
            <span className="trace-decision">{audit.target || audit.description || '-'}</span>
            <span className="severity-inline low">{audit.severity || 'info'}</span>
            <small>{formatTime(audit.created_at || audit.timestamp)}</small>
          </div>
        ))}
        {!audits.length && <p className="empty-text">暂无审计日志。</p>}
      </div>

      {(anomalies.agentItems.length > 0 || anomalies.auditItems.length > 0) && (
        <div className="anomaly-section" style={{ marginTop: 18 }}>
          <h4>异常检测</h4>
          {[...anomalies.agentItems, ...anomalies.auditItems].map((item, index) => (
            <div className="anomaly-item" key={index}>
              <AlertTriangle size={16} color="var(--orange)" />
              <div>
                <strong>{item.agent || item.agent_name || item.action_type || item.type || '异常'}</strong>
                <p>{item.description || item.message || item.reasoning || JSON.stringify(item)}</p>
              </div>
            </div>
          ))}
        </div>
      )}
      {anomalies.total === 0 && <p className="empty-text" style={{ marginTop: 14 }}>未检测到异常。</p>}
    </section>
  );
}

function calcOpsMetrics(records) {
  const rows = records.map((record) => record.analysis_result || {}).filter(Boolean);
  const total = rows.length || 1;
  const avg = (values) => values.reduce((sum, value) => sum + num(value), 0) / Math.max(values.length, 1);
  const accuracy = avg(rows.map((result) => result.fact_check_result?.overall_confidence || result.fact_check_result?.coverage_rate || 0));
  const coverage = avg(rows.map((result) => result.citation_report?.evidence_coverage || 0));
  const sourceCount = rows.reduce((sum, result) => sum + realSourceCount(result), 0);
  const needsHuman = rows.filter((result) => {
    const reviewer = result.review_feedback || {};
    return reviewer.approved === false || (reviewer.issues || []).length > 0 || num(result.quality_score) < 7;
  }).length;
  const avgQuality = avg(records.map((record) => record.quality_score || record.analysis_result?.quality_score || 0));
  return {
    accuracy,
    coverage,
    sourceCount,
    manualFixRate: needsHuman / total,
    avgQuality,
    total: rows.length,
  };
}

function OpsLoopPanel({ records }) {
  const metrics = calcOpsMetrics(records);
  return (
    <section className="panel ops-loop-panel">
      <div className="panel-heading">
        <div>
          <div className="panel-kicker">运营闭环指标</div>
          <h3>准确率、覆盖率、人工修正率</h3>
        </div>
      </div>
      <div className="ops-loop-grid">
        <div>
          <strong>{(metrics.accuracy * 100).toFixed(0)}%</strong>
          <span>交叉验证置信度</span>
        </div>
        <div>
          <strong>{(metrics.coverage * 100).toFixed(0)}%</strong>
          <span>证据覆盖率</span>
        </div>
        <div>
          <strong>{(metrics.manualFixRate * 100).toFixed(0)}%</strong>
          <span>待人工修正率</span>
        </div>
        <div>
          <strong>{metrics.sourceCount}</strong>
          <span>累计可溯源证据</span>
        </div>
      </div>
      <div className="ops-loop-steps">
        <span>Agent 自动分析</span>
        <span>交叉验证</span>
        <span>来源溯源</span>
        <span>人工修正</span>
        <span>沉淀复用</span>
      </div>
    </section>
  );
}

export function TraceabilityPage() {
  const [state, setState] = useState({
    infra: null,
    logs: [],
    usage: null,
    quota: null,
    dag: null,
    events: [],
    anomalies: null,
    audits: [],
    records: [],
    snapshots: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('overview');
  const [selectedRecord, setSelectedRecord] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    const calls = await Promise.allSettled([
      api.infraStatus(),
      api.decisionLogs(80),
      api.tokenUsage(),
      api.tokenQuota(),
      api.dagSnapshot(),
      api.infraEvents(160),
      api.anomalies(),
      api.auditLogs(80),
      api.analysisRecords(),
      api.evolutionSnapshots(40),
    ]);
    setState({
      infra: calls[0].status === 'fulfilled' ? calls[0].value : null,
      logs: calls[1].status === 'fulfilled' ? listOf(calls[1].value) : [],
      usage: calls[2].status === 'fulfilled' ? calls[2].value : null,
      quota: calls[3].status === 'fulfilled' ? calls[3].value : null,
      dag: calls[4].status === 'fulfilled' ? calls[4].value : null,
      events: calls[5].status === 'fulfilled' ? listOf(calls[5].value) : [],
      anomalies: calls[6].status === 'fulfilled' ? calls[6].value : null,
      audits: calls[7].status === 'fulfilled' ? listOf(calls[7].value) : [],
      records: calls[8].status === 'fulfilled' ? listOf(calls[8].value) : [],
      snapshots: calls[9].status === 'fulfilled' ? listOf(calls[9].value) : [],
    });
    const rejected = calls.find((item) => item.status === 'rejected');
    if (rejected) setError(rejected.reason?.message || '部分可观测接口暂时不可用');
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    setSelectedRecord(null);
  }, [activeTab]);

  useEffect(() => {
    const refresh = () => load();
    const refreshWhenVisible = () => {
      if (document.visibilityState === 'visible') load();
    };
    window.addEventListener(ANALYSIS_RECORDS_UPDATED_EVENT, refresh);
    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', refreshWhenVisible);
    return () => {
      window.removeEventListener(ANALYSIS_RECORDS_UPDATED_EVENT, refresh);
      window.removeEventListener('focus', refresh);
      document.removeEventListener('visibilitychange', refreshWhenVisible);
    };
  }, [load]);

  const tokenUsage = useMemo(() => normalizeTokenUsage(state.usage, state.infra), [state.usage, state.infra]);
  const anomalies = useMemo(() => normalizeAnomalies(state.anomalies), [state.anomalies]);
  const latestRecord = state.records[0];
  const recordDag = latestRecord?.analysis_result?.dag_snapshot;
  const currentDagProgress = num(state.dag?.total_progress ?? state.infra?.dag?.progress);
  const dagForPanel = currentDagProgress ? state.dag : (recordDag || state.dag);
  const dagProgress = currentDagProgress || num(recordDag?.total_progress ?? recordDag?.progress);

  const tabs = [
    { id: 'overview', label: '总览', count: '' },
    { id: 'logs', label: '决策日志', count: state.records.length },
    { id: 'tokens', label: 'Token', count: state.records.length },
    { id: 'events', label: '事件总线', count: state.records.length },
    { id: 'records', label: '分析记录', count: state.records.length },
    { id: 'dag', label: 'DAG', count: state.records.length },
    { id: 'audit', label: '审计异常', count: state.records.length },
  ];

  return (
    <div className="page-stack">
      <div className="trace-action-row">
        <button className="secondary-button" type="button" onClick={load} disabled={loading}>
          <RefreshCw className={loading ? 'spin' : ''} size={18} />
          刷新
        </button>
      </div>

      {error && <div className="notice warn"><AlertTriangle size={18} /><span>{error}</span></div>}

      <section className="metric-grid">
        <Metric icon={Activity} label="系统状态" value={state.infra?.status || state.infra?.overall_status || '运行中'} />
        <Metric icon={GitBranch} label="DAG 进度" value={`${(dagProgress * 100).toFixed(0)}%`} />
        <Metric icon={Zap} label="Token 总量" value={formatTokens(tokenUsage.totalInput + tokenUsage.totalOutput)} />
        <Metric icon={BarChart3} label="预估计费" value={`¥${tokenUsage.estimatedCost.toFixed(4)}`} />
        <Metric icon={FileText} label="决策日志" value={state.logs.length} />
        <Metric icon={Radio} label="事件总线" value={state.events.length} />
        <Metric icon={ShieldCheck} label="异常告警" value={anomalies.total} tone={anomalies.total ? 'warn' : 'good'} />
      </section>

      <div className="trace-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={activeTab === tab.id ? 'active' : ''}
            type="button"
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
            {tab.count !== '' && <span className="tab-badge">{tab.count}</span>}
          </button>
        ))}
      </div>

      {activeTab === 'records' ? (
        <RecordsPanel
          records={state.records}
          selectedRecord={selectedRecord}
          onSelect={setSelectedRecord}
          onClose={() => setSelectedRecord(null)}
        />
      ) : selectedRecord ? (
        <TraceRecordModuleDetail
          record={selectedRecord}
          activeTab={activeTab}
          onClose={() => setSelectedRecord(null)}
        />
      ) : (
        <TraceRecordListPanel
          records={state.records}
          moduleLabel={TRACE_MODULE_LABELS[activeTab] || '可观测溯源'}
          onSelect={setSelectedRecord}
        />
      )}
    </div>
  );
}
