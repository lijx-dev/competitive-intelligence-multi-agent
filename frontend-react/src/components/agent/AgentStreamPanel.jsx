import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  Check,
  ChevronUp,
  Clock3,
  Cpu,
  FileText,
  Loader2,
  Radio,
  Zap,
} from 'lucide-react';
import { dagNodes } from '../../data/agentFlow.js';
import { SourceCitationList } from './SourceCitation.jsx';
import { MarkdownText } from '../common/MarkdownText.jsx';
import { HighlightText } from '../common/HighlightText.jsx';
import { formatAgentOutputAsMarkdown } from '../../utils/agentMarkdown.js';

function listOf(payload) {
  if (Array.isArray(payload)) return payload;
  return payload?.logs || payload?.items || payload?.events || payload?.nodes || payload?.records || [];
}

function num(value) {
  return Number.isFinite(Number(value)) ? Number(value) : 0;
}

function formatDuration(ms) {
  const value = num(ms);
  if (!value) return '';
  return value < 1000 ? `${value}ms` : `${(value / 1000).toFixed(1)}s`;
}

function formatTokens(value) {
  const v = num(value);
  if (v >= 10000) return `${(v / 10000).toFixed(1)}万`;
  if (v >= 1000) return `${(v / 1000).toFixed(1)}k`;
  return `${v}`;
}

function splitProgressChunks(content) {
  const text = String(content || '').trim();
  if (!text) return [];
  const lines = text.split(/\r?\n/);
  const chunks = [];
  let current = [];
  let inTable = false;

  const flush = () => {
    const chunk = current.join('\n').trim();
    if (chunk) chunks.push(chunk);
    current = [];
  };

  lines.forEach((line) => {
    const trimmed = line.trim();
    const isTableRow = trimmed.startsWith('|') && trimmed.endsWith('|');
    const startsBlock = /^(### |#### |- |> )/.test(trimmed);

    if (!trimmed) {
      flush();
      inTable = false;
      return;
    }

    if (!isTableRow && inTable) {
      flush();
      inTable = false;
    }
    if (startsBlock && current.length && !inTable) flush();

    current.push(line);
    if (isTableRow) inTable = true;
  });

  flush();
  return chunks.length ? chunks : [text];
}

function ProgressiveMarkdown({ content, compact = false, active = false }) {
  const chunks = useMemo(() => splitProgressChunks(content), [content]);
  const [visible, setVisible] = useState(active ? Math.min(1, chunks.length) : chunks.length);

  useEffect(() => {
    if (!active) {
      setVisible(chunks.length);
      return undefined;
    }
    setVisible(Math.min(1, chunks.length));
    if (chunks.length <= 1) return undefined;

    const timer = window.setInterval(() => {
      setVisible((value) => {
        const next = Math.min(value + 1, chunks.length);
        if (next >= chunks.length) window.clearInterval(timer);
        return next;
      });
    }, 180);

    return () => window.clearInterval(timer);
  }, [active, chunks.length, content]);

  return <MarkdownText content={chunks.slice(0, visible).join('\n\n')} compact={compact} />;
}

function getNodeLabel(nodeId) {
  return dagNodes.find((n) => n.id === nodeId)?.label || nodeId;
}

function getUsageForAgent(telemetry, nodeId, meta = {}) {
  const agents = telemetry?.usage?.agents || telemetry?.infra?.tokens?.agents || {};
  const usage = agents[nodeId] || {};
  const input = num(meta.input_tokens ?? usage.input ?? usage.total_input);
  const output = num(meta.output_tokens ?? usage.output ?? usage.total_output);
  return { input, output, total: input + output };
}

function parseTimestamp(value, fallback = Date.now()) {
  if (!value) return fallback;
  const ts = new Date(value).getTime();
  return Number.isFinite(ts) ? ts : fallback;
}

function summarizeNodeOutput(nodeId, data) {
  if (!data) return { text: '', sources: [], details: [] };
  if (data.error) {
    return {
      text: `执行失败：${data.error}`,
      sources: [],
      details: ['请检查模型 Key、模型 Endpoint、网络访问或后端日志。'],
      badge: 'fail',
    };
  }

  switch (nodeId) {
    case 'monitor': {
      const changes = data.changes_detected || [];
      const high = changes.filter((c) => String(c.severity).toUpperCase() === 'HIGH').length;
      return {
        text: `发现 ${changes.length} 条竞品动态${high ? `，其中 ${high} 条高优先级` : ''}`,
        sources: changes.map((c) => c.source_url || c.url).filter(Boolean),
        details: changes.slice(0, 3).map((c) => `[${c.severity || 'INFO'}] ${c.title}`),
      };
    }
    case 'alert': {
      const alerts = data.alerts_sent || [];
      return {
        text: alerts.length ? `已生成 ${alerts.length} 条高优先级告警` : '没有达到告警阈值的变更',
        sources: [],
        details: alerts.slice(0, 3).map((a) => a.title || a.message || a.severity),
      };
    }
    case 'research': {
      const results = data.research_results || [];
      const avgConf = results.length
        ? (results.reduce((s, r) => s + num(r.confidence), 0) / results.length * 100).toFixed(0)
        : 0;
      return {
        text: `完成 ${results.length} 个研究维度，平均置信度 ${avgConf}%`,
        sources: results.flatMap((r) => r.sources || []),
        details: results.map((r) => r.topic || r.summary).slice(0, 4),
      };
    }
    case 'survey': {
      const sr = data.survey_results || data;
      const sat = num(sr.satisfaction_avg);
      const pains = sr.top_pain_points || [];
      return {
        text: `用户满意度 ${sat.toFixed(1)}/10${pains.length ? `，首要痛点：${pains[0]}` : ''}`,
        sources: [],
        details: (sr.key_findings || []).slice(0, 3),
      };
    }
    case 'fact_check': {
      const fc = data.fact_check_result || data;
      const verified = num(fc.verified_count);
      const total = verified + num(fc.unverified_count);
      return {
        text: `${verified}/${total || verified} 条结论通过交叉验证，整体置信度 ${((num(fc.overall_confidence)) * 100).toFixed(0)}%`,
        sources: [],
        details: fc.verification_summary ? [fc.verification_summary] : [],
      };
    }
    case 'compare': {
      const mx = data.comparison_matrix || data;
      const dims = mx.dimensions || [];
      const ourAvg = dims.length ? (dims.reduce((s, d) => s + num(d.our_score), 0) / dims.length).toFixed(1) : '-';
      const compAvg = dims.length ? (dims.reduce((s, d) => s + num(d.competitor_score), 0) / dims.length).toFixed(1) : '-';
      return {
        text: `${dims.length} 个维度对比完成，我方均分 ${ourAvg}，竞品均分 ${compAvg}`,
        sources: dims.flatMap((d) => d.evidence || []),
        details: dims.slice(0, 3).map((d) => `${d.dimension}: ${d.our_score} vs ${d.competitor_score}`),
      };
    }
    case 'battlecard': {
      const bc = data.battlecard || data;
      return {
        text: `生成对战卡：${(bc.key_differentiators || []).length} 条差异化论点，${Object.keys(bc.objection_handling || {}).length} 条异议处理`,
        sources: [],
        details: (bc.key_differentiators || []).slice(0, 4),
      };
    }
    case 'reviewer': {
      const rf = data.review_feedback || data;
      const score = num(rf.overall_score || data.quality_score);
      const pass = rf.approved !== false && score >= 7;
      return {
        text: `质量评分 ${score.toFixed(1)}/10，${pass ? '通过审查' : '需要定向修复'}`,
        sources: [],
        details: (rf.issues || []).slice(0, 3).map((issue) => issue.description || String(issue)),
        badge: pass ? 'pass' : 'fail',
      };
    }
    case 'targeted_fix':
      return { text: `第 ${data.targeted_fix_count || 1} 轮定向修复完成`, sources: [], details: [] };
    case 'citation': {
      const cr = data.citation_report || data;
      return {
        text: `验证 ${cr.total_sources || 0} 个来源，可信度 ${((num(cr.overall_reliability_score)) * 100).toFixed(0)}%`,
        sources: cr.source_list || [],
        details: cr.missing_citations?.length ? [`缺失引用：${cr.missing_citations.length} 处`] : [],
      };
    }
    case 'feishu_push': {
      const status = data.feishu_push_status || '';
      return {
        text: status.includes('success') ? '报告卡片推送成功' : status.includes('skip') ? '未配置推送，已跳过' : '推送节点执行完成',
        sources: [],
        details: [],
      };
    }
    default:
      return { text: JSON.stringify(data).slice(0, 120), sources: [], details: [] };
  }
}

function describeBusEvent(evt) {
  const type = evt.event_type || evt.type;
  const source = evt.source || evt.agent;
  const data = evt.data || {};
  if (!source || !type) return null;
  if (type === 'agent_completed') return null;

  if (type === 'agent_started') {
    return {
      text: `开始执行 ${getNodeLabel(source)}，正在准备上下文和输入数据。`,
      status: 'running',
      details: data.task ? [`任务：${data.task}`] : [],
    };
  }
  if (type === 'dag_node_changed') {
    const message = data.message || data.reasoning || data.summary || data.text || '';
    if (!message) return null;
    return {
      text: message,
      status: 'running',
      details: [
        data.phase ? `阶段：${data.phase}` : '',
        data.progress != null ? `进度 ${Math.round(num(data.progress) * 100)}%` : '',
      ].filter(Boolean),
      phase: data.phase || 'output',
      progress: data.progress,
    };
  }
  if (type === 'token_consumed') {
    const input = num(data.input_tokens);
    const output = num(data.output_tokens);
    return {
      text: `记录 Token 消耗：输入 ${input.toLocaleString()}，输出 ${output.toLocaleString()}。`,
      status: 'running',
      details: [],
    };
  }
  if (type === 'agent_failed') {
    return {
      text: `执行失败：${data.error || '未知错误'}`,
      status: 'failed',
      details: ['该节点已中断，后续报告不会生成完整结果。'],
      badge: 'fail',
    };
  }
  return {
    text: typeof data === 'object' ? JSON.stringify(data).slice(0, 160) : String(data || type),
    status: 'running',
    details: [],
  };
}

function buildLiveEntries(completedEvents, telemetry, sinceTime = 0) {
  const entries = [];
  const completedKeys = new Set();
  const threshold = sinceTime ? sinceTime - 1500 : 0;

  completedEvents.forEach((evt, i) => {
    completedKeys.add(evt.nodeId);
    entries.push({
      id: `node-${evt.nodeId}-${evt.timestamp || i}`,
      kind: 'node',
      nodeId: evt.nodeId,
      status: evt.status || 'completed',
      timestamp: evt.timestamp || Date.now(),
      data: evt.data,
      meta: evt.meta || evt.data?._meta || {},
      duration: evt.duration,
    });
  });

  listOf(telemetry?.logs).forEach((log, index) => {
    const nodeId = log.agent_name || log.agent;
    const status = log.status || 'running';
    const phase = log.phase || 'working';
    const timestamp = parseTimestamp(log.timestamp || log.created_at, Date.now() - 1);
    if (!nodeId || timestamp < threshold) return;
    if (phase === 'working') return;
    if (status === 'completed' && completedKeys.has(nodeId)) return;
    entries.push({
      id: log.log_id || `log-${nodeId}-${index}`,
      kind: 'log',
      nodeId,
      status,
      timestamp,
      text: log.reasoning || log.decision || log.message || '正在处理 Agent 中间步骤',
      details: phase !== 'execution' ? [`阶段：${phase}`] : [],
      duration: log.duration_ms,
      meta: {
        input_tokens: log.input_tokens,
        output_tokens: log.output_tokens,
      },
    });
  });

  listOf(telemetry?.events).forEach((evt, index) => {
    const nodeId = evt.source || evt.agent;
    const described = describeBusEvent(evt);
    const timestamp = parseTimestamp(evt.timestamp || evt.created_at, Date.now() - 2);
    if (!nodeId || !described || timestamp < threshold) return;
    entries.push({
      id: evt.event_id || evt.id || `event-${nodeId}-${index}`,
      kind: 'event',
      nodeId,
      status: described.status,
      timestamp,
      text: described.text,
      details: described.details,
      badge: described.badge,
      phase: described.phase,
      progress: described.progress,
      meta: {},
    });
  });

  const byId = new Map();
  entries
    .sort((a, b) => a.timestamp - b.timestamp)
    .forEach((entry) => byId.set(entry.id, entry));
  return [...byId.values()].slice(-60);
}

function TelemetrySummary({ telemetry, events }) {
  const agentUsage = telemetry?.usage?.agents || telemetry?.infra?.tokens?.agents || {};
  const totals = Object.values(agentUsage).reduce(
    (acc, item) => ({
      input: acc.input + num(item.input ?? item.total_input),
      output: acc.output + num(item.output ?? item.total_output),
    }),
    { input: 0, output: 0 },
  );
  const completed = telemetry?.dag?.nodes
    ? listOf(telemetry.dag.nodes).filter((n) => n.status === 'completed').length
    : events.length;

  return (
    <div className="stream-metrics">
      <span><Activity size={14} />完成 {completed}</span>
      <span><Zap size={14} />Token {formatTokens(totals.input + totals.output)}</span>
      <span><FileText size={14} />日志 {listOf(telemetry?.logs).length}</span>
      <span><Radio size={14} />事件 {listOf(telemetry?.events).length}</span>
    </div>
  );
}

function DecisionLogPreview({ logs }) {
  const rows = listOf(logs).filter((log) => log.phase !== 'working').slice(-4).reverse();
  if (!rows.length) return null;

  return (
    <div className="stream-subpanel">
      <div className="stream-subpanel-title">
        <FileText size={14} />
        <span>最近决策</span>
      </div>
      {rows.map((log, index) => (
        <div className="mini-log-row" key={log.id || `${log.agent_name}-${index}`}>
          <strong>{log.agent_name || log.agent || '-'}</strong>
          <span>{log.phase || log.status || 'execution'}</span>
          <p><HighlightText text={log.reasoning || log.decision || log.message || log.summary || '-'} /></p>
        </div>
      ))}
    </div>
  );
}

function AgentTokenPreview({ usage }) {
  const agents = usage?.agents || {};
  const rows = Object.entries(agents)
    .map(([agent, data]) => ({
      agent,
      input: num(data.input ?? data.total_input),
      output: num(data.output ?? data.total_output),
    }))
    .sort((a, b) => (b.input + b.output) - (a.input + a.output))
    .slice(0, 5);

  if (!rows.length) return null;
  const maxTotal = Math.max(...rows.map((r) => r.input + r.output), 1);

  return (
    <div className="stream-subpanel">
      <div className="stream-subpanel-title">
        <Cpu size={14} />
        <span>Token 消耗</span>
      </div>
      {rows.map((row) => {
        const total = row.input + row.output;
        return (
          <div className="mini-token-row" key={row.agent}>
            <div>
              <strong>{getNodeLabel(row.agent)}</strong>
              <span>{formatTokens(total)}</span>
            </div>
            <div className="mini-token-track">
              <i style={{ width: `${Math.max((total / maxTotal) * 100, 4)}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function AgentStreamPanel({ events = [], runningNode, pipelineState, telemetry, analysisStartedAt = 0 }) {
  const bottomRef = useRef(null);
  const [quickInsightsCollapsed, setQuickInsightsCollapsed] = useState(false);
  const liveEntries = useMemo(
    () => buildLiveEntries(events, telemetry, analysisStartedAt),
    [events, telemetry, analysisStartedAt],
  );
  const hasCurrentRunningOutput = liveEntries.some(
    (entry) => entry.nodeId === runningNode && entry.status === 'running',
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [liveEntries.length, runningNode]);

  return (
    <div className="stream-panel panel">
      <div className="stream-panel-header">
        <div>
          <strong>Agent 运行过程</strong>
          <small>节点输出、决策日志、Token 和事件总线实时汇总</small>
        </div>
        {pipelineState === 'running' && <Loader2 size={16} className="spin" />}
        {pipelineState === 'completed' && <Check size={16} style={{ color: 'var(--green)' }} />}
      </div>

      <TelemetrySummary telemetry={telemetry} events={events} />

      <div className={`stream-insight-toggle-row ${quickInsightsCollapsed ? 'is-collapsed' : ''}`}>
        <span>{quickInsightsCollapsed ? '最近决策与 Token 消耗已隐藏' : '最近决策与 Token 消耗'}</span>
        <button
          type="button"
          className="stream-collapse-button"
          aria-expanded={!quickInsightsCollapsed}
          onClick={() => setQuickInsightsCollapsed((value) => !value)}
          title={quickInsightsCollapsed ? '展开最近决策与 Token 消耗' : '隐藏最近决策与 Token 消耗'}
        >
          <ChevronUp size={16} />
        </button>
      </div>

      {!quickInsightsCollapsed && (
        <div className="stream-side-grid">
          <DecisionLogPreview logs={telemetry?.logs} />
          <AgentTokenPreview usage={telemetry?.usage} />
        </div>
      )}

      <div className="stream-body">
        {liveEntries.length === 0 && (
          <p className="empty-text">
            {pipelineState === 'running'
              ? '正在建立实时过程流，稍等片刻会显示 Agent 的中间步骤。'
              : '启动分析后，各 Agent 的工作进展会实时显示在这里。'}
          </p>
        )}

        {liveEntries.map((evt, i) => {
          const meta = evt.meta || evt.data?._meta || {};
          const summarized = evt.kind === 'node'
            ? summarizeNodeOutput(evt.nodeId, evt.data)
            : { text: evt.text, sources: [], details: evt.details || [], badge: evt.badge };
          const { text, sources, details, badge } = summarized;
          const markdownContent = evt.kind === 'node'
            ? formatAgentOutputAsMarkdown(evt.nodeId, evt.data)
            : text;
          const usage = getUsageForAgent(telemetry, evt.nodeId, meta);
          const duration = formatDuration(evt.duration ?? meta.duration_ms);
          const isFailed = evt.status === 'failed';
          const isRunning = evt.status === 'running';
          return (
            <div
              className={`stream-entry ${isFailed ? 'stream-entry--failed' : isRunning ? 'stream-entry--running' : 'stream-entry--done'}`}
              key={`${evt.id || evt.nodeId}-${evt.timestamp || i}`}
            >
              <div className={`stream-entry-icon ${isFailed ? 'stream-entry-icon--failed' : isRunning ? 'stream-entry-icon--running' : 'stream-entry-icon--done'}`}>
                {isFailed ? <AlertTriangle size={14} /> : isRunning ? <Activity size={14} /> : <Check size={14} />}
              </div>
              <div className="stream-entry-body">
                <div className="stream-entry-head">
                  <strong>{getNodeLabel(evt.nodeId)}</strong>
                  {isRunning && <span className="quality-live">实时</span>}
                  {badge === 'pass' && <span className="quality-pass">通过</span>}
                  {badge === 'fail' && <span className="quality-fail">打回</span>}
                </div>
                {markdownContent ? (
                  <div className="stream-markdown-box">
                    <ProgressiveMarkdown
                      content={markdownContent}
                      compact
                      active={isRunning || evt.kind === 'event' || evt.kind === 'log'}
                    />
                  </div>
                ) : (
                  <p className="stream-entry-text"><HighlightText text={text} /></p>
                )}
                <div className="stream-entry-meta">
                  {duration && <span><Clock3 size={12} />{duration}</span>}
                  {usage.total > 0 && <span><Zap size={12} />{formatTokens(usage.total)} tokens</span>}
                </div>
                {details?.length > 0 && (
                  <ul className="stream-entry-details">
                    {details.map((d, j) => <li key={j}><HighlightText text={d} /></li>)}
                  </ul>
                )}
                <SourceCitationList sources={sources} />
              </div>
            </div>
          );
        })}

        {runningNode && !hasCurrentRunningOutput && (
          <div className="stream-entry stream-entry--running">
            <div className="stream-entry-icon stream-entry-icon--running">
              <Loader2 size={14} className="spin" />
            </div>
            <div className="stream-entry-body">
              <strong>{getNodeLabel(runningNode)}</strong>
              <p className="stream-entry-text"><HighlightText text="正在继续生成分析内容，过程消息会自动追加到上方" /></p>
              <span className="typing-dots"><span /><span /><span /></span>
            </div>
          </div>
        )}

        {pipelineState === 'error' && (
          <div className="stream-entry stream-entry--failed">
            <div className="stream-entry-icon stream-entry-icon--failed">
              <AlertTriangle size={14} />
            </div>
            <div className="stream-entry-body">
              <strong>分析异常</strong>
              <p className="stream-entry-text"><HighlightText text="执行过程出现错误，请查看上方提示或后端日志。" /></p>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}
