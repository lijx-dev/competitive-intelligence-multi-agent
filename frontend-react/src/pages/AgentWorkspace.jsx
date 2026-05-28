import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  BarChart3,
  CircleAlert,
  CircleCheck,
  Download,
  Loader2,
  Play,
  Plus,
  RefreshCw,
  Wand2,
  Zap,
} from 'lucide-react';
import { api, analyzeStream, notifyAnalysisRecordsUpdated } from '../api/client.js';
import { dagNodes, getDownstreamNodes } from '../data/agentFlow.js';
import { AgentDAG } from '../components/agent/AgentDAG.jsx';
import { AgentStreamPanel } from '../components/agent/AgentStreamPanel.jsx';
import { AgentOutputCard } from '../components/agent/AgentOutputCard.jsx';
import { AnalysisReport } from '../components/agent/AnalysisReport.jsx';

const RESULT_NODES = ['monitor', 'research', 'survey', 'fact_check', 'compare', 'battlecard', 'reviewer', 'citation'];

function linesToUrls(value) {
  return value.split(/\n|,/).map((s) => s.trim()).filter(Boolean);
}

function initNodeStatuses() {
  const statuses = {};
  dagNodes.forEach((node) => {
    statuses[node.id] = { status: 'idle' };
  });
  return statuses;
}

function listOf(payload) {
  if (Array.isArray(payload)) return payload;
  return payload?.logs || payload?.items || payload?.events || payload?.nodes || payload?.records || [];
}

function buildResultsFromFinal(finalResult = {}) {
  return {
    source_evidence: finalResult.source_evidence || [],
    monitor: { changes_detected: finalResult.changes_detected || [] },
    research: { research_results: finalResult.research_results || [] },
    survey: { survey_results: finalResult.survey_results || {} },
    fact_check: { fact_check_result: finalResult.fact_check_result || {} },
    compare: { comparison_matrix: finalResult.comparison_matrix || {} },
    battlecard: { battlecard: finalResult.battlecard || {} },
    reviewer: { review_feedback: finalResult.review_feedback || {} },
    citation: { citation_report: finalResult.citation_report || {} },
  };
}

function extractQuality(nodeId, data, fallback = null) {
  if (nodeId === 'reviewer') {
    return data?.review_feedback?.overall_score ?? data?.quality_score ?? fallback;
  }
  return fallback;
}

function downloadReport(competitor, results, qualityScore, telemetry) {
  const report = {
    title: `${competitor || '竞品'} 竞争情报分析报告`,
    generated_at: new Date().toISOString(),
    quality_score: qualityScore,
    results,
    telemetry: {
      token_usage: telemetry?.usage || null,
      decision_logs: listOf(telemetry?.logs).slice(0, 50),
      events: listOf(telemetry?.events).slice(0, 100),
    },
  };
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `competitive-report-${competitor || 'analysis'}-${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

export function AgentWorkspace() {
  const [competitors, setCompetitors] = useState([]);
  const [analysisRecords, setAnalysisRecords] = useState([]);
  const [mockStatus, setMockStatus] = useState(null);
  const [form, setForm] = useState({ competitor: '', urls: '' });
  const [saving, setSaving] = useState(false);
  const [togglingMock, setTogglingMock] = useState(false);

  const [pipelineState, setPipelineState] = useState('idle');
  const [events, setEvents] = useState([]);
  const [nodeStatuses, setNodeStatuses] = useState(initNodeStatuses);
  const [runningNode, setRunningNode] = useState(null);
  const [results, setResults] = useState({});
  const [qualityScore, setQualityScore] = useState(null);
  const [reflexionCount, setReflexionCount] = useState(0);
  const [telemetry, setTelemetry] = useState({ usage: null, logs: [], events: [], dag: null, infra: null });
  const [analysisStartedAt, setAnalysisStartedAt] = useState(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const abortRef = useRef(null);
  const completedRef = useRef(false);
  const nodeStartedAtRef = useRef({});
  const runningNodeRef = useRef(null);

  const urls = useMemo(() => linesToUrls(form.urls), [form.urls]);

  const loadBaseData = useCallback(async () => {
    const [cp, ms, ar] = await Promise.allSettled([api.competitors(), api.mockStatus(), api.analysisRecords()]);
    if (cp.status === 'fulfilled') setCompetitors(cp.value || []);
    if (ms.status === 'fulfilled') setMockStatus(ms.value);
    if (ar.status === 'fulfilled') setAnalysisRecords(listOf(ar.value));
  }, []);

  const loadTelemetry = useCallback(async () => {
    const calls = await Promise.allSettled([
      api.tokenUsage(),
      api.decisionLogs(30),
      api.infraEvents(80),
      api.dagSnapshot(),
      api.infraStatus(),
    ]);
    setTelemetry((prev) => ({
      usage: calls[0].status === 'fulfilled' ? calls[0].value : prev.usage,
      logs: calls[1].status === 'fulfilled' ? listOf(calls[1].value) : prev.logs,
      events: calls[2].status === 'fulfilled' ? listOf(calls[2].value) : prev.events,
      dag: calls[3].status === 'fulfilled' ? calls[3].value : prev.dag,
      infra: calls[4].status === 'fulfilled' ? calls[4].value : prev.infra,
    }));
  }, []);

  useEffect(() => {
    loadBaseData().catch(() => {});
    loadTelemetry().catch(() => {});
  }, [loadBaseData, loadTelemetry]);

  useEffect(() => {
    if (pipelineState === 'running') {
      loadTelemetry().catch(() => {});
      const timer = window.setInterval(() => loadTelemetry().catch(() => {}), 700);
      return () => window.clearInterval(timer);
    }
    if (pipelineState === 'completed' || pipelineState === 'error') {
      loadTelemetry().catch(() => {});
    }
    return undefined;
  }, [pipelineState, loadTelemetry]);

  const markRunning = (nodeIds) => {
    const ids = Array.isArray(nodeIds) ? nodeIds : [nodeIds];
    const now = Date.now();
    ids.forEach((id) => {
      if (!nodeStartedAtRef.current[id]) nodeStartedAtRef.current[id] = now;
    });
    setNodeStatuses((prev) => {
      const next = { ...prev };
      ids.forEach((id) => {
        if (next[id]?.status !== 'completed') {
          next[id] = { ...(next[id] || {}), status: 'running', startedAt: nodeStartedAtRef.current[id] };
        }
      });
      return next;
    });
  };

  const setCurrentRunningNode = (nodeId) => {
    runningNodeRef.current = nodeId;
    setRunningNode(nodeId);
  };

  const resetAnalysis = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    completedRef.current = false;
    nodeStartedAtRef.current = {};
    setPipelineState('idle');
    setEvents([]);
    setNodeStatuses(initNodeStatuses());
    setCurrentRunningNode(null);
    setAnalysisStartedAt(null);
    setResults({});
    setQualityScore(null);
    setReflexionCount(0);
    setError('');
    setMessage('');
  };

  const chooseCompetitor = (item) => {
    setForm({ competitor: item.name, urls: Array.isArray(item.urls) ? item.urls.join('\n') : '' });
    resetAnalysis();
  };

  const saveCompetitor = async () => {
    if (!form.competitor.trim()) {
      setError('请先填写竞品名称');
      return;
    }
    setSaving(true);
    setError('');
    setMessage('');
    try {
      await api.createCompetitor({ name: form.competitor.trim(), urls });
      setMessage('竞品已保存到竞品库');
      await loadBaseData();
    } catch (err) {
      setError(err.message || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const startAnalysis = () => {
    if (!form.competitor.trim()) {
      setError('请填写竞品名称后再启动分析');
      return;
    }

    resetAnalysis();
    setAnalysisStartedAt(Date.now());
    setPipelineState('running');
    markRunning('monitor');
    setCurrentRunningNode('monitor');

    abortRef.current = analyzeStream(
      { competitor: form.competitor.trim(), urls },
      {
        onEvent(nodeId, data) {
          const timestamp = Date.now();
          const startedAt = nodeStartedAtRef.current[nodeId] || timestamp;
          const duration = data?._meta?.duration_ms ?? (timestamp - startedAt);
          const meta = data?._meta || {};

          setNodeStatuses((prev) => ({
            ...prev,
            [nodeId]: { status: 'completed', data, timestamp, duration },
          }));
          setEvents((prev) => [...prev, { nodeId, data, timestamp, status: 'completed', duration, meta }]);
          setResults((prev) => ({ ...prev, [nodeId]: data }));

          const nextQuality = extractQuality(nodeId, data, qualityScore);
          if (nextQuality != null) {
            setQualityScore(Number(nextQuality));
            if (nodeId === 'reviewer' && Number(nextQuality) < 7) {
              setReflexionCount((count) => count + 1);
            }
          }

          const downstream = getDownstreamNodes(nodeId).filter((id) => id !== '__end__');
          const runnable = nodeId === 'reviewer'
            ? downstream.filter((id) => (id === 'targeted_fix' ? Number(nextQuality) < 7 : Number(nextQuality) >= 7))
            : downstream;
          const nextRunning = runnable[0] || null;
          if (runnable.length) markRunning(runnable);
          setCurrentRunningNode(nextRunning);
        },
        onComplete(data) {
          if (completedRef.current) return;
          completedRef.current = true;
          if (data?.result) {
            const finalResults = buildResultsFromFinal(data.result);
            setResults((prev) => ({ ...finalResults, ...prev }));
            const finalQuality = data.quality_score ?? data.result.review_feedback?.overall_score;
            if (finalQuality != null) setQualityScore(Number(finalQuality));
          }
          setPipelineState('completed');
          setCurrentRunningNode(null);
          loadTelemetry().catch(() => {});
          loadBaseData()
            .then(() => notifyAnalysisRecordsUpdated({
              competitor: form.competitor.trim(),
              recordId: data?.record_id,
              status: data?.status || 'completed',
            }))
            .catch(() => notifyAnalysisRecordsUpdated({
              competitor: form.competitor.trim(),
              recordId: data?.record_id,
              status: data?.status || 'completed',
            }));
          window.setTimeout(() => {
            loadBaseData().catch(() => {});
            notifyAnalysisRecordsUpdated({
              competitor: form.competitor.trim(),
              recordId: data?.record_id,
              status: data?.status || 'completed',
            });
          }, 800);
        },
        onError(err) {
          const errorMessage = typeof err === 'string' ? err : err?.message || '分析失败';
          const failedNode = runningNodeRef.current || 'system';
          setPipelineState('error');
          setError(errorMessage);
          setEvents((prev) => [
            ...prev,
            {
              nodeId: failedNode,
              data: { error: errorMessage, _meta: { status: 'failed' } },
              timestamp: Date.now(),
              status: 'failed',
              duration: 0,
              meta: { status: 'failed' },
            },
          ]);
          setCurrentRunningNode(null);
          setNodeStatuses((prev) => {
            const next = { ...prev };
            for (const key of Object.keys(next)) {
              if (next[key].status === 'running') next[key] = { ...next[key], status: 'failed' };
            }
            return next;
          });
          loadTelemetry().catch(() => {});
          loadBaseData()
            .then(() => notifyAnalysisRecordsUpdated({
              competitor: form.competitor.trim(),
              status: 'failed',
            }))
            .catch(() => notifyAnalysisRecordsUpdated({
              competitor: form.competitor.trim(),
              status: 'failed',
            }));
        },
      },
    );
  };

  const enableDemoAndRetry = async () => {
    setTogglingMock(true);
    setError('');
    setMessage('');
    try {
      await api.mockToggle(true, mockStatus?.current_scenario || 'scenario1');
      const status = await api.mockStatus();
      setMockStatus(status);
      setMessage('演示模式已开启，正在重新发起分析');
      window.setTimeout(startAnalysis, 0);
    } catch (err) {
      setError(err.message || '切换演示模式失败');
    } finally {
      setTogglingMock(false);
    }
  };

  const switchToRealMode = async () => {
    setTogglingMock(true);
    setError('');
    setMessage('');
    try {
      await api.mockToggle(false, mockStatus?.current_scenario || 'scenario1');
      const status = await api.mockStatus();
      setMockStatus(status);
      setMessage('已切换到真实模型模式，后续分析会调用真实后端 Agent 流程');
    } catch (err) {
      setError(err.message || '切换真实模式失败');
    } finally {
      setTogglingMock(false);
    }
  };

  const resultEntries = RESULT_NODES.filter((id) => results[id]).map((id) => [id, results[id]]);
  const completedCount = events.length;
  const tokenTotal = Object.values(telemetry.usage?.agents || {}).reduce(
    (sum, item) => sum + Number(item.input || item.total_input || 0) + Number(item.output || item.total_output || 0),
    0,
  );

  return (
    <div className="page-stack">
      <section className="panel hero-panel workspace-hero">
        <div className="workspace-hero-copy">
          <span className="workspace-hero-icon"><BarChart3 size={30} /></span>
          <div>
            <div className="panel-kicker">智能体工作台</div>
            <h2>发起竞品分析</h2>
            <p>输入竞品名称和公开来源后，系统会按 DAG 调度多个 Agent。</p>
          </div>
        </div>
        <div className="workspace-status-actions">
          <div className="status-inline">
            <span>{mockStatus?.mock_mode ? '演示模式' : '真实模型'}</span>
          </div>
          {mockStatus?.mock_mode ? (
            <button className="secondary-button" type="button" onClick={switchToRealMode} disabled={togglingMock || pipelineState === 'running'}>
              {togglingMock ? <Loader2 className="spin" size={18} /> : <Zap size={18} />}
              切换真实模式
            </button>
          ) : (
            <button className="secondary-button" type="button" onClick={enableDemoAndRetry} disabled={togglingMock || pipelineState === 'running'}>
              {togglingMock ? <Loader2 className="spin" size={18} /> : <Wand2 size={18} />}
              启用演示模式
            </button>
          )}
        </div>
      </section>

      {(message || error) && (
        <div className={`notice ${error ? 'warn' : 'good'}`}>
          {error ? <CircleAlert size={18} /> : <CircleCheck size={18} />}
          <span>{error || message}</span>
        </div>
      )}

      <section className="workspace-grid">
        <article className="panel form-panel">
          <div className="panel-heading">
            <div>
              <div className="panel-kicker">分析配置</div>
              <h3>竞品对象与信息来源</h3>
            </div>
            <button className="ghost-button" type="button" onClick={loadBaseData} title="刷新竞品库">
              <RefreshCw size={16} />
            </button>
          </div>

          <label className="field">
            <span>竞品名称</span>
            <input value={form.competitor} onChange={(e) => setForm((f) => ({ ...f, competitor: e.target.value }))} placeholder="例如：快手电商" />
          </label>

          <label className="field">
            <span>公开来源链接</span>
            <textarea value={form.urls} onChange={(e) => setForm((f) => ({ ...f, urls: e.target.value }))} placeholder="每行一个链接，也可以留空使用 Mock/知识库数据" rows={4} />
          </label>

          <div className="button-row">
            <button className="secondary-button" type="button" onClick={saveCompetitor} disabled={saving}>
              {saving ? <Loader2 className="spin" size={18} /> : <Plus size={18} />}
              保存竞品
            </button>
            <button className="primary-button" type="button" onClick={startAnalysis} disabled={pipelineState === 'running'}>
              {pipelineState === 'running' ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
              {pipelineState === 'running' ? '分析中' : '启动分析'}
            </button>
          </div>

          {competitors.length > 0 && (
            <div className="competitor-chips">
              {competitors.map((item) => (
                <button key={item.id} type="button" onClick={() => chooseCompetitor(item)}>{item.name}</button>
              ))}
            </div>
          )}
        </article>

        <article className="panel workspace-overview-panel">
          <div className="panel-heading">
            <div>
              <div className="panel-kicker">分析概览</div>
              <h3>{pipelineState === 'idle' ? '等待任务' : form.competitor}</h3>
            </div>
            {qualityScore != null && <span className="score-badge">质量 {Number(qualityScore).toFixed(1)}/10</span>}
          </div>
          <div className="overview-stats">
            <div className="overview-stat"><span>{completedCount}</span><small>完成节点</small></div>
            <div className="overview-stat"><span>{reflexionCount}</span><small>修复轮次</small></div>
            <div className="overview-stat"><span>{tokenTotal ? tokenTotal.toLocaleString() : '-'}</span><small>Token</small></div>
          </div>
          {pipelineState === 'idle' && <p className="empty-text">点击“启动分析”后，DAG、Agent 日志和最终报告会在下方实时展开。</p>}
        </article>
      </section>

      {pipelineState !== 'idle' && (
        <section className="analysis-split">
          <div className="analysis-left">
            <AgentDAG nodeStatuses={nodeStatuses} reflexionCount={reflexionCount} />
          </div>
          <div className="analysis-right">
            <AgentStreamPanel
              events={events}
              runningNode={runningNode}
              pipelineState={pipelineState}
              telemetry={telemetry}
              analysisStartedAt={analysisStartedAt}
            />
          </div>
        </section>
      )}

      {pipelineState === 'completed' && resultEntries.length > 0 && (
        <section className="analysis-output-section analysis-output-section--report">
          <div className="analysis-output-heading">
            <div>
              <span>最终输出</span>
              <h2>最终分析报告</h2>
            </div>
            <small>汇总 Agent 中间结果、质量审查、图表分析和来源证据</small>
          </div>
          <AnalysisReport
            competitor={form.competitor}
            urls={urls}
            results={results}
            qualityScore={qualityScore}
            telemetry={telemetry}
            events={events}
            historyRecords={analysisRecords}
          />
        </section>
      )}

      {(pipelineState === 'completed' || pipelineState === 'error') && resultEntries.length > 0 && (
        <section className="analysis-output-section analysis-output-section--nodes">
          <div className="analysis-output-heading">
            <div>
              <span>节点产物</span>
              <h2>结构化节点结果</h2>
            </div>
            <button className="download-json-button" type="button" onClick={() => downloadReport(form.competitor, results, qualityScore, telemetry)}>
              <Download size={18} />
              下载 JSON
            </button>
          </div>
          <div className="result-count-banner">{resultEntries.length} 个 Agent 模块已输出结构化结果</div>
          <section className="result-cards-grid">
            {resultEntries.map(([nodeId, data]) => (
              <AgentOutputCard key={nodeId} nodeId={nodeId} data={data} />
            ))}
          </section>
        </section>
      )}
    </div>
  );
}
