import { useEffect, useMemo, useState, useCallback } from 'react';
import {
  Activity,
  ArrowRight,
  BarChart3,
  Bot,
  CheckCircle,
  ChevronDown,
  Clock,
  FileText,
  Grid3X3,
  Loader2,
  Play,
  RefreshCw,
  Rocket,
  Send,
  Settings,
  Table2,
  Terminal,
  XCircle,
  Zap,
} from 'lucide-react';
import { api } from '../api/client.js';

// ── 12节点DAG定义 ──
const DAG_NODES = [
  { id: 'monitor', label: '网页监控', icon: '🔍' },
  { id: 'alert', label: '告警检测', icon: '🚨' },
  { id: 'research', label: '5维深度研究', icon: '📚' },
  { id: 'multimodal', label: '多模态分析', icon: '🖼️' },
  { id: 'fact_check', label: '交叉验证', icon: '🔬' },
  { id: 'compare', label: '8维对比矩阵', icon: '📊' },
  { id: 'schema_validation', label: 'Schema校验', icon: '✅' },
  { id: 'battlecard', label: '销售战术卡', icon: '🎯' },
  { id: 'reviewer', label: '质量审查', icon: '📋' },
  { id: 'targeted_fix', label: '定向修复', icon: '🔧' },
  { id: 'citation', label: '引用溯源', icon: '📎' },
  { id: 'ontology', label: '知识图谱', icon: '🗺️' },
];

function statusIcon(status) {
  if (status === 'completed') return '🟢';
  if (status === 'running') return '🔵';
  if (status === 'failed') return '🔴';
  return '⚪';
}

function NodeProgressBar({ nodeStatus }) {
  return (
    <div className="feishu-node-grid">
      {DAG_NODES.map((node) => {
        const s = nodeStatus?.[node.id] || 'pending';
        return (
          <div key={node.id} className={`node-chip node-${s}`} title={`${node.label}: ${s}`}>
            <span className="node-icon">{statusIcon(s)}</span>
            <span className="node-label">{node.label}</span>
          </div>
        );
      })}
    </div>
  );
}

function CommandPreview({ onSend }) {
  const [input, setInput] = useState('');
  const [mode, setMode] = useState('mock');

  const examples = [
    '/ci 快手电商',
    '分析一下SHEIN',
    '帮我做Temu竞品分析',
    '对比抖音和快手',
  ];

  const handleSend = () => {
    if (!input.trim()) return;
    onSend?.(input.trim(), mode);
    setInput('');
  };

  return (
    <article className="panel">
      <div className="panel-heading">
        <div>
          <div className="panel-kicker">命令测试</div>
          <h3>模拟飞书自然语言命令</h3>
        </div>
      </div>
      <p style={{ color: 'var(--muted)', marginBottom: 12, fontSize: 14 }}>
        输入飞书风格的命令，系统会自动解析竞品名称并启动分析。
      </p>

      <div className="command-input-row">
        <div className="field" style={{ flex: 1, marginBottom: 0 }}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="输入命令，如：/ci 快手电商 / 分析一下SHEIN"
          />
        </div>
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value)}
          style={{ width: 120 }}
        >
          <option value="mock">Mock演示</option>
          <option value="real">真实LLM</option>
        </select>
        <button className="primary-button" type="button" onClick={handleSend}>
          <Send size={16} />
          发送
        </button>
      </div>

      <div className="command-examples" style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {examples.map((ex) => (
          <button
            key={ex}
            className="ghost-button"
            type="button"
            style={{ fontSize: 12 }}
            onClick={() => setInput(ex)}
          >
            {ex}
          </button>
        ))}
      </div>
    </article>
  );
}

function TaskCard({ task, onRefresh }) {
  const progress = task.progress_pct || 0;
  const isComplete = task.is_complete;

  return (
    <div className={`task-card ${isComplete ? 'complete' : 'active'}`}>
      <div className="task-card-header">
        <div>
          <strong>{task.competitor || '未知'}</strong>
          <span className={`mode-badge ${task.mode}`}>
            {task.mode === 'mock' ? '🎭 Mock' : '🤖 真实'}
          </span>
        </div>
        <span className="task-id">#{task.task_id?.slice(-8) || ''}</span>
      </div>

      <div className="progress-bar-track" style={{ margin: '8px 0' }}>
        <div
          className={`progress-bar-fill ${isComplete ? 'complete' : ''}`}
          style={{ width: `${progress}%` }}
        />
        <span style={{ fontSize: 11, position: 'absolute', right: 4, top: -2 }}>{progress}%</span>
      </div>

      <div className="task-card-stats">
        <span className="stat">
          <CheckCircle size={12} /> {task.completed || 0} 完成
        </span>
        <span className="stat">
          <XCircle size={12} /> {task.failed || 0} 失败
        </span>
        <span className="stat">
          <Clock size={12} /> {task.total - (task.completed || 0) - (task.failed || 0)} 待执行
        </span>
      </div>

      {isComplete ? (
        <div className="task-badge complete">✅ 已完成</div>
      ) : (
        <div className="task-badge active">🔄 执行中</div>
      )}
    </div>
  );
}

export function FeishuSchedulerPage() {
  const [stats, setStats] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [commandResult, setCommandResult] = useState(null);
  const [sending, setSending] = useState(false);
  const [testing, setTesting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('dashboard');
  const [pollTaskId, setPollTaskId] = useState('');
  const [taskDetail, setTaskDetail] = useState(null);

  const loadAll = useCallback(async () => {
    setError('');
    try {
      const [statsRes, tasksRes] = await Promise.allSettled([
        api.fetchJson('/api/v1/feishu/scheduler/stats'),
        api.fetchJson('/api/v1/feishu/scheduler/tasks'),
      ]);
      if (statsRes.status === 'fulfilled') setStats(statsRes.value);
      if (tasksRes.status === 'fulfilled') {
        const t = tasksRes.value.tasks || [];
        setTasks(t);
      }
    } catch (err) {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  // 轮询任务详情
  useEffect(() => {
    if (!pollTaskId) return;
    const timer = setInterval(async () => {
      try {
        const detail = await api.fetchJson(`/api/v1/feishu/task-status/${pollTaskId}`);
        setTaskDetail(detail);
        if (detail.is_complete || detail.status === 'not_found') {
          clearInterval(timer);
          loadAll();
        }
      } catch (e) {
        // ignore
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [pollTaskId, loadAll]);

  const handleSendCommand = async (text, mode) => {
    setSending(true);
    setCommandResult(null);
    setError('');
    try {
      const res = await api.fetchJson('/api/v1/feishu/command', {
        method: 'POST',
        body: JSON.stringify({ text, mode }),
      });
      setCommandResult(res);
      if (res.task_id) {
        setPollTaskId(res.task_id);
      }
      loadAll();
    } catch (err) {
      setError(err.message || '命令发送失败');
    } finally {
      setSending(false);
    }
  };

  const handleTestScheduler = async () => {
    setTesting(true);
    setError('');
    try {
      const res = await api.fetchJson('/api/v1/feishu/scheduler/test', { method: 'POST' });
      setCommandResult(res);
      if (res.task_id) {
        setPollTaskId(res.task_id);
      }
      loadAll();
    } catch (err) {
      setError(err.message || '测试失败');
    } finally {
      setTesting(false);
    }
  };

  const activeCount = stats?.active_tasks ?? tasks.filter(t => !t.is_complete).length;
  const completedCount = stats?.completed_tasks ?? tasks.filter(t => t.is_complete).length;
  const pushRate = stats?.push_success_rate_pct ?? 95;

  const tabs = [
    { id: 'dashboard', label: '调度看板', icon: BarChart3 },
    { id: 'tasks', label: '任务队列', icon: Grid3X3, count: tasks.length },
    { id: 'detail', label: '节点进度', icon: Activity },
    { id: 'command', label: '命令测试', icon: Terminal },
  ];

  return (
    <div className="page-stack">
      {/* ── 顶部 KPI 卡片 ── */}
      <section className="metric-grid">
        <article className="metric-card info">
          <Rocket size={22} />
          <span>活跃任务</span>
          <strong>{activeCount}</strong>
        </article>
        <article className="metric-card good">
          <CheckCircle size={22} />
          <span>已完成</span>
          <strong>{completedCount}</strong>
        </article>
        <article className="metric-card info">
          <Send size={22} />
          <span>推送成功率</span>
          <strong>{pushRate}%</strong>
        </article>
        <article className="metric-card info">
          <Zap size={22} />
          <span>总任务数</span>
          <strong>{tasks.length}</strong>
        </article>
      </section>

      {/* ── 一键测试大按钮 ── */}
      <div className="action-bar">
        <button
          className="primary-button large"
          type="button"
          onClick={handleTestScheduler}
          disabled={testing}
        >
          {testing ? <Loader2 className="spin" size={20} /> : <Rocket size={20} />}
          一键测试飞书调度
        </button>
        <button className="ghost-button" type="button" onClick={loadAll}>
          <RefreshCw size={16} />
          刷新数据
        </button>
      </div>

      {/* ── 命令结果提示 ── */}
      {commandResult && (
        <div className={`notice ${commandResult.parsed ? 'good' : 'warn'}`}>
          {commandResult.parsed ? <CheckCircle size={18} /> : <XCircle size={18} />}
          <div>
            <strong>{commandResult.message}</strong>
            {commandResult.task_id && (
              <span style={{ fontSize: 12, opacity: 0.7, display: 'block' }}>
                task_id: <code>{commandResult.task_id}</code>
              </span>
            )}
          </div>
        </div>
      )}
      {error && (
        <div className="notice warn">
          <XCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      {/* ── Tab 切换 ── */}
      <div className="trace-tabs">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              className={activeTab === tab.id ? 'active' : ''}
              type="button"
              onClick={() => setActiveTab(tab.id)}
            >
              <Icon size={15} />
              {tab.label}
              {tab.count != null && <span className="tab-badge">{tab.count}</span>}
            </button>
          );
        })}
      </div>

      {/* ── 调度看板 ── */}
      {activeTab === 'dashboard' && (
        <div className="split-grid">
          <article className="panel">
            <div className="panel-heading">
              <div>
                <div className="panel-kicker">实时看板</div>
                <h3>飞书CLI全局总调度官</h3>
              </div>
            </div>
            <p style={{ color: 'var(--muted)', marginBottom: 16, fontSize: 14 }}>
              飞书群内自然语言命令 → 自动解析竞品 → 12节点DAG执行 → 实时进度卡片 → 分析完成推送报告
            </p>
            <div className="scheduler-flow">
              <div className="flow-step">
                <Terminal size={20} />
                <strong>命令解析</strong>
                <p>/ci 快手 或 分析一下SHEIN</p>
              </div>
              <ArrowRight size={16} className="flow-arrow" />
              <div className="flow-step">
                <Bot size={20} />
                <strong>确认卡片</strong>
                <p>飞书群即时回复</p>
              </div>
              <ArrowRight size={16} className="flow-arrow" />
              <div className="flow-step">
                <Activity size={20} />
                <strong>12节点DAG</strong>
                <p>进度逐节点更新</p>
              </div>
              <ArrowRight size={16} className="flow-arrow" />
              <div className="flow-step">
                <FileText size={20} />
                <strong>报告推送</strong>
                <p>云文档 + 多维表格</p>
              </div>
            </div>

            <div style={{ marginTop: 20 }}>
              <div className="panel-heading" style={{ marginBottom: 8 }}>
                <h3 style={{ fontSize: 14 }}>系统配置状态</h3>
              </div>
              <div className="config-summary">
                <div className="config-row">
                  <span>飞书Webhook</span>
                  <span className={`status-dot-inline ${pushRate > 0 ? 'active' : 'inactive'}`}>
                    {pushRate > 0 ? '已配置' : '未配置'}
                  </span>
                </div>
                <div className="config-row">
                  <span>Bitable同步</span>
                  <span className="status-dot-inline inactive">需配置 FEISHU_BITABLE_APP_TOKEN</span>
                </div>
                <div className="config-row">
                  <span>云文档生成</span>
                  <span className="status-dot-inline inactive">需安装 lark-cli</span>
                </div>
                <div className="config-row">
                  <span>命令解析</span>
                  <span className="status-dot-inline active">内置策略（无需外部依赖）</span>
                </div>
              </div>
            </div>
          </article>

          <article className="panel">
            <div className="panel-heading">
              <div>
                <div className="panel-kicker">DAG节点总览</div>
                <h3>12节点执行状态</h3>
              </div>
            </div>
            <NodeProgressBar nodeStatus={taskDetail?.node_status || {}} />
            {!taskDetail && (
              <p style={{ color: 'var(--muted)', fontSize: 13, textAlign: 'center', marginTop: 20 }}>
                发送一条命令查看实时节点状态
              </p>
            )}
          </article>
        </div>
      )}

      {/* ── 任务队列 ── */}
      {activeTab === 'tasks' && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <div className="panel-kicker">任务历史</div>
              <h3>飞书调度任务队列</h3>
            </div>
          </div>
          {tasks.length === 0 ? (
            <p className="empty-text">暂无任务记录。点击「一键测试飞书调度」发起演示任务。</p>
          ) : (
            <div className="task-grid">
              {tasks.map((task) => (
                <TaskCard key={task.task_id} task={task} onRefresh={loadAll} />
              ))}
            </div>
          )}
        </section>
      )}

      {/* ── 节点进度详情 ── */}
      {activeTab === 'detail' && (
        <>
          {taskDetail ? (
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <div className="panel-kicker">实时进度</div>
                  <h3>{taskDetail.competitor || '未知'} — {taskDetail.progress_pct}% 完成</h3>
                </div>
                <span className={`status-dot-inline ${taskDetail.is_complete ? 'active' : ''}`}>
                  {taskDetail.is_complete ? '已完成' : '执行中'}
                </span>
              </div>
              <NodeProgressBar nodeStatus={taskDetail.node_status || {}} />
              <div style={{ marginTop: 16 }}>
                <div className="progress-bar-track" style={{ height: 8 }}>
                  <div
                    className={`progress-bar-fill ${taskDetail.is_complete ? 'complete' : ''}`}
                    style={{ width: `${taskDetail.progress_pct}%` }}
                  />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, fontSize: 13, color: 'var(--muted)' }}>
                  <span>完成 {taskDetail.completed_nodes}/{taskDetail.total_nodes}</span>
                  <span>失败 {taskDetail.failed_nodes}</span>
                  <span>{taskDetail.mode === 'mock' ? '🎭 Mock' : '🤖 Real'}</span>
                </div>
              </div>
            </section>
          ) : (
            <section className="panel">
              <p className="empty-text">发送一条命令后，点击任务查看进度详情。</p>
            </section>
          )}
        </>
      )}

      {/* ── 命令测试 ── */}
      {activeTab === 'command' && (
        <div className="split-grid">
          <CommandPreview onSend={handleSendCommand} />
          <article className="panel">
            <div className="panel-heading">
              <div>
                <div className="panel-kicker">解析能力</div>
                <h3>支持的命令格式</h3>
              </div>
            </div>
            <div className="command-format-list">
              <div className="format-item">
                <code>/ci 快手电商</code>
                <span>结构化快捷命令（推荐）</span>
              </div>
              <div className="format-item">
                <code>分析一下SHEIN</code>
                <span>纯自然语言</span>
              </div>
              <div className="format-item">
                <code>帮我做Temu竞品分析</code>
                <span>自然语言 + 竞品关键词</span>
              </div>
              <div className="format-item">
                <code>对比抖音和快手</code>
                <span>比较模式（取第一个竞品）</span>
              </div>
              <div className="format-item">
                <code>研究一下小红书电商</code>
                <span>学术风格命令</span>
              </div>
            </div>
            <div style={{ marginTop: 16, padding: '12px', background: 'var(--surface2)', borderRadius: 8, fontSize: 13 }}>
              <strong>已注册竞品关键词</strong>：快手电商、抖音电商、Temu、SHEIN、阿里电商AI、京东电商、小红书电商、Amazon、Shopee、Lazada、Notion、Crayon、Klue 等
            </div>
          </article>
        </div>
      )}
    </div>
  );
}
