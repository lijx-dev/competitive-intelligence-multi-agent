import { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  Bot,
  CircleAlert,
  CircleCheck,
  Database,
  Link2,
  MessageCircle,
  RefreshCw,
  ShieldCheck,
  Target,
} from 'lucide-react';
import { api } from '../api/client.js';
import { dagNodes, dagModules } from '../data/agentFlow.js';

function unwrapList(payload) {
  if (Array.isArray(payload)) return payload;
  return payload?.items || payload?.logs || payload?.records || [];
}

function getFeishuConfig(config) {
  return config?.notification || config?.configs?.notification || config?.data?.notification || {};
}

export function SystemDashboard() {
  const [data, setData] = useState({});
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    setError('');
    const calls = await Promise.allSettled([
      api.health(),
      api.mockStatus(),
      api.competitors(),
      api.analysisRecords(),
      api.infraStatus(),
      api.ragStats(),
      api.config(),
      api.systemInfo(),
    ]);
    const [health, mock, competitors, records, infra, rag, config, systemInfo] = calls.map((item) =>
      item.status === 'fulfilled' ? item.value : null,
    );
    const firstError = calls.find((item) => item.status === 'rejected');
    setData({ health, mock, competitors, records, infra, rag, config, systemInfo });
    if (firstError) setError(firstError.reason?.message || '部分接口暂时不可用');
    setLoading(false);
  };

  useEffect(() => {
    load();
  }, []);

  const metrics = useMemo(() => {
    const competitors = unwrapList(data.competitors);
    const records = unwrapList(data.records);
    const logs = unwrapList(data.infra?.decision_logs || data.infra?.logs);
    const feishu = getFeishuConfig(data.config);
    return [
      {
        label: '后端状态',
        value: data.health?.status === 'ok' ? '正常' : '待连接',
        icon: Activity,
        tone: data.health?.status === 'ok' ? 'good' : 'warn',
      },
      {
        label: '竞品对象',
        value: `${competitors.length}`,
        icon: Database,
        tone: 'info',
      },
      {
        label: '分析记录',
        value: `${records.length}`,
        icon: Bot,
        tone: 'info',
      },
      {
        label: '飞书配置',
        value: feishu.feishu_webhook_url || feishu.webhook_url ? '已配置' : '未配置',
        icon: MessageCircle,
        tone: feishu.feishu_webhook_url || feishu.webhook_url ? 'good' : 'warn',
      },
      {
        label: '日志记录',
        value: `${logs.length || data.infra?.log_count || 0}`,
        icon: ShieldCheck,
        tone: 'info',
      },
      {
        label: '知识库片段',
        value: `${data.rag?.chunks || data.rag?.chunk_count || 0}`,
        icon: Database,
        tone: 'info',
      },
    ];
  }, [data]);

  const latestRecords = unwrapList(data.records).slice(0, 4);
  const featuredAgents = [
    { id: 'monitor', icon: Activity, tone: 'blue', tags: ['多源', '变更'] },
    { id: 'research', icon: Database, tone: 'green', tags: ['检索', '研判'] },
    { id: 'compare', icon: Bot, tone: 'blue', tags: ['矩阵', '评分'] },
    { id: 'battlecard', icon: Target, tone: 'orange', tags: ['打法', '建议'] },
    { id: 'reviewer', icon: ShieldCheck, tone: 'orange', tags: ['审查', '修复'] },
    { id: 'citation', icon: Link2, tone: 'blue', tags: ['证据', '溯源'] },
  ].map((item) => ({ ...item, node: dagNodes.find((node) => node.id === item.id) }));

  return (
    <div className="page-stack">
      <section className="panel hero-panel dashboard-hero">
        <div>
          <h2>总览</h2>
          <div className="dashboard-status-line">
            <span className={data.health?.status === 'ok' ? 'status-pill good' : 'status-pill warn'}>
              {data.health?.status === 'ok' ? '后端在线' : '待连接'}
            </span>
            <span className="status-pill">记录 {unwrapList(data.records).length}</span>
            <span className="status-pill">竞品 {unwrapList(data.competitors).length}</span>
          </div>
        </div>
        <button className="secondary-button" type="button" onClick={load} disabled={loading}>
          <RefreshCw className={loading ? 'spin' : ''} size={18} />
          刷新
        </button>
      </section>

      {error && (
        <div className="notice warn">
          <CircleAlert size={18} />
          <span>{error}</span>
        </div>
      )}

      <section className="metric-grid">
        {metrics.map((item) => {
          const Icon = item.icon;
          return (
            <article className={`metric-card ${item.tone}`} key={item.label}>
              <Icon size={22} />
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </article>
          );
        })}
      </section>

      <section className="split-grid">
        <article className="panel dashboard-agent-panel">
          <div className="panel-heading">
            <div>
              <div className="panel-kicker">Agent 编队</div>
              <h3>核心能力</h3>
            </div>
            <CircleCheck size={20} />
          </div>
          <div className="dashboard-agent-grid">
            {featuredAgents.map((item) => {
              const Icon = item.icon;
              const mod = dagModules.find((m) => m.id === item.node?.module);
              return (
                <article className={`dashboard-agent-card ${item.tone}`} key={item.id}>
                  <div>
                    <Icon size={20} />
                    <span style={{ color: mod?.color }}>{mod?.label}</span>
                  </div>
                  <strong>{item.node?.label}</strong>
                  <small>{item.node?.desc}</small>
                  <p>{item.tags.map((tag) => <b key={tag}>{tag}</b>)}</p>
                </article>
              );
            })}
          </div>
        </article>

        <article className="panel dashboard-record-panel">
          <div className="panel-heading">
            <div>
              <div className="panel-kicker">最近报告</div>
              <h3>分析记录</h3>
            </div>
          </div>
          {latestRecords.length ? (
            <div className="record-list">
              {latestRecords.map((record) => (
                <div className="record-row" key={record.id}>
                  <strong>{record.competitor_name}</strong>
                  <span>质量评分 {Number(record.quality_score || 0).toFixed(1)}/10</span>
                  <small>{String(record.created_at || '').slice(0, 19).replace('T', ' ')}</small>
                </div>
              ))}
            </div>
          ) : (
            <p className="empty-text">暂无分析记录，进入智能体工作台发起一次任务。</p>
          )}
        </article>
      </section>
    </div>
  );
}
