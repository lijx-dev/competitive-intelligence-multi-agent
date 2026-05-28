import { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Bell,
  Bot,
  CircleAlert,
  CircleCheck,
  Loader2,
  MessageCircle,
  Send,
  Settings,
  Zap,
} from 'lucide-react';
import { api } from '../api/client.js';

function feedbackList(payload) {
  if (Array.isArray(payload)) return payload;
  return payload?.records || payload?.items || payload?.feedback || [];
}

export function FeishuIntegrationPage() {
  const [config, setConfig] = useState(null);
  const [infra, setInfra] = useState(null);
  const [records, setRecords] = useState([]);
  const [analysisRecords, setAnalysisRecords] = useState([]);
  const [form, setForm] = useState({ report_id: '', action: 'confirm', comment: '' });
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('monitor');

  const feishuConfig = useMemo(() => config?.notification || config?.configs?.notification || {}, [config]);
  const configured = Boolean(feishuConfig.feishu_webhook_url || feishuConfig.webhook_url);

  const load = async () => {
    setLoading(true);
    setError('');
    const calls = await Promise.allSettled([
      api.config(),
      api.feishuFeedback(),
      api.infraStatus(),
      api.analysisRecords(),
    ]);
    if (calls[0].status === 'fulfilled') setConfig(calls[0].value);
    if (calls[1].status === 'fulfilled') setRecords(feedbackList(calls[1].value));
    if (calls[2].status === 'fulfilled') setInfra(calls[2].value);
    if (calls[3].status === 'fulfilled') {
      const recs = Array.isArray(calls[3].value) ? calls[3].value : calls[3].value?.items || [];
      setAnalysisRecords(recs);
    }
    const rejected = calls.find((item) => item.status === 'rejected');
    if (rejected) setError(rejected.reason?.message || '接口暂时不可用');
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const testPush = async () => {
    setTesting(true); setMessage(''); setError('');
    try {
      const payload = await api.feishuTest();
      setMessage(payload?.message || '飞书测试卡片已发送');
    } catch (err) {
      setError(err.message || '飞书推送测试失败');
    } finally { setTesting(false); }
  };

  const submitFeedback = async () => {
    if (!form.report_id.trim()) { setError('请输入报告编号'); return; }
    setSubmitting(true); setMessage(''); setError('');
    try {
      await api.submitFeishuFeedback({
        report_id: form.report_id.trim(),
        action: form.action,
        comment: form.comment,
      });
      setMessage('反馈已写入数据库，将触发演化引擎更新置信度');
      setForm((f) => ({ ...f, comment: '' }));
      await load();
    } catch (err) {
      setError(err.message || '提交反馈失败');
    } finally { setSubmitting(false); }
  };

  // 提取告警事件（从分析记录中找到有告警的）
  const alerts = analysisRecords
    .filter((r) => r.analysis_result?.alerts_sent?.length > 0)
    .flatMap((r) => (r.analysis_result.alerts_sent || []).map((a) => ({ ...a, competitor: r.competitor_name, record_id: r.id })));

  const tabs = [
    { id: 'monitor', label: 'Agent 监控', icon: Bot },
    { id: 'alerts', label: '告警记录', icon: Bell, count: alerts.length },
    { id: 'push', label: '飞书推送', icon: Send },
    { id: 'feedback', label: '人工反馈', icon: MessageCircle, count: records.length },
  ];

  return (
    <div className="page-stack">
      {(message || error) && (
        <div className={`notice ${error ? 'warn' : 'good'}`}>
          {error ? <CircleAlert size={18} /> : <CircleCheck size={18} />}
          <span>{error || message}</span>
        </div>
      )}

      {/* ── 状态卡片 ── */}
      <section className="metric-grid feishu-metric-grid">
        <article className={`metric-card ${configured ? 'good' : 'warn'}`}>
          <MessageCircle size={22} />
          <span>飞书机器人</span>
          <strong>{configured ? '已配置' : '未配置'}</strong>
        </article>
        <article className="metric-card info">
          <Bot size={22} />
          <span>活跃 Agent</span>
          <strong>{infra?.active_agents || infra?.agent_count || 11}</strong>
        </article>
        <article className="metric-card info">
          <Bell size={22} />
          <span>累计告警</span>
          <strong>{alerts.length}</strong>
        </article>
        <article className="metric-card info">
          <Zap size={22} />
          <span>人工反馈</span>
          <strong>{records.length}</strong>
        </article>
      </section>

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

      {/* ── Agent 监控 ── */}
      {activeTab === 'monitor' && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <div className="panel-kicker">实时监控</div>
              <h3>Agent 运行状态概览</h3>
            </div>
          </div>
          <p style={{ color: 'var(--muted)', marginBottom: 16, fontSize: 14 }}>
            飞书机器人会在以下情况自动推送告警：竞品发布重大更新（HIGH 级别）、Agent 质量评分低于阈值、分析流程异常中断。
          </p>
          <div className="monitor-grid">
            <div className="monitor-card">
              <Settings size={18} />
              <h4>Webhook 配置</h4>
              <p>{configured ? '飞书 Webhook 已配置，告警将自动推送到群组' : '未配置 Webhook，请在后端 .env 中设置 FEISHU_WEBHOOK_URL'}</p>
              <span className={`status-dot ${configured ? 'active' : 'inactive'}`} />
            </div>
            <div className="monitor-card">
              <AlertTriangle size={18} />
              <h4>告警规则</h4>
              <p>严重度 HIGH 的竞品变更 → 立即推送<br />质量评分 &lt; 7.0 → 触发修复并通知<br />流程异常 → 错误告警</p>
              <span className="status-dot active" />
            </div>
            <div className="monitor-card">
              <Bot size={18} />
              <h4>推送内容</h4>
              <p>分析报告摘要卡片<br />对比矩阵变更通知<br />对战卡更新提醒<br />质量审查结果</p>
              <span className="status-dot active" />
            </div>
          </div>
        </section>
      )}

      {/* ── 告警记录 ── */}
      {activeTab === 'alerts' && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <div className="panel-kicker">变更告警</div>
              <h3>AlertAgent 推送的竞品动态告警</h3>
            </div>
          </div>
          <div className="trace-table feishu-alert-frame">
            <div className="trace-table-head">
              <span>竞品</span><span>严重度</span><span>告警标题</span><span>推送渠道</span><span>时间</span>
            </div>
            {alerts.map((a, i) => (
              <div className="trace-table-row" key={i}>
                <span>{a.competitor || '-'}</span>
                <span className={`severity-inline ${(a.severity || '').toLowerCase()}`}>{a.severity || 'INFO'}</span>
                <strong>{a.title || a.message || '-'}</strong>
                <span>{(a.sent_to || []).join(', ') || '-'}</span>
                <small>{(a.sent_at || '').slice(0, 19)}</small>
              </div>
            ))}
            {!alerts.length && <p className="empty-text">暂无告警记录，运行一次分析后 AlertAgent 会自动推送 HIGH 级别变更。</p>}
          </div>
        </section>
      )}

      {/* ── 飞书推送 ── */}
      {activeTab === 'push' && (
        <section className="split-grid">
          <article className="panel">
            <div className="panel-heading">
              <div>
                <div className="panel-kicker">推送测试</div>
                <h3>向飞书群发送测试卡片</h3>
              </div>
            </div>
            <p style={{ color: 'var(--muted)', marginBottom: 16, fontSize: 14 }}>
              点击下方按钮将向配置的飞书群发送一条测试消息卡片，验证 Webhook 是否生效。
            </p>
            <button className="primary-button" type="button" onClick={testPush} disabled={testing}>
              {testing ? <Loader2 className="spin" size={18} /> : <Send size={18} />}
              发送测试卡片
            </button>
          </article>

          <article className="panel">
            <div className="panel-heading">
              <div>
                <div className="panel-kicker">推送配置</div>
                <h3>飞书机器人状态</h3>
              </div>
            </div>
            <div className="config-summary">
              <div className="config-row">
                <span>Webhook URL</span>
                <strong>{configured ? '已配置' : '未配置'}</strong>
              </div>
              <div className="config-row">
                <span>Webhook Secret</span>
                <strong>{feishuConfig.feishu_webhook_secret ? '已配置' : '未配置'}</strong>
              </div>
              <div className="config-row">
                <span>状态</span>
                <span className={`status-dot-inline ${configured ? 'active' : 'inactive'}`}>
                  {configured ? '在线' : '离线'}
                </span>
              </div>
            </div>
          </article>
        </section>
      )}

      {/* ── 人工反馈 ── */}
      {activeTab === 'feedback' && (
        <>
          <section className="split-grid">
            <article className="panel">
              <div className="panel-heading">
                <div>
                  <div className="panel-kicker">人工反馈</div>
                  <h3>提交飞书回调反馈</h3>
                </div>
              </div>
              <p style={{ color: 'var(--muted)', marginBottom: 12, fontSize: 14 }}>
                模拟飞书卡片按钮回调：确认报告准确性、纠正错误结论或标记需修复项。反馈会触发演化引擎更新置信度。
              </p>
              <label className="field">
                <span>报告编号</span>
                <input value={form.report_id} onChange={(e) => setForm((f) => ({ ...f, report_id: e.target.value }))} placeholder="输入分析记录 ID" />
              </label>
              <label className="field">
                <span>反馈动作</span>
                <select value={form.action} onChange={(e) => setForm((f) => ({ ...f, action: e.target.value }))}>
                  <option value="confirm">确认正确 (+置信度)</option>
                  <option value="correct">纠正错误 (-置信度)</option>
                  <option value="ack">已读知悉</option>
                </select>
              </label>
              <label className="field">
                <span>反馈说明</span>
                <textarea
                  value={form.comment}
                  onChange={(e) => setForm((f) => ({ ...f, comment: e.target.value }))}
                  placeholder="可选：描述需要修正的内容"
                  rows={3}
                />
              </label>
              <button className="primary-button" type="button" onClick={submitFeedback} disabled={submitting}>
                {submitting ? <Loader2 className="spin" size={18} /> : <CircleCheck size={18} />}
                提交反馈
              </button>
            </article>

            <article className="panel">
              <div className="panel-heading">
                <div>
                  <div className="panel-kicker">反馈闭环</div>
                  <h3>飞书反馈如何驱动演化</h3>
                </div>
              </div>
              <div className="feedback-flow">
                <div className="feedback-step">
                  <span>1</span>
                  <div>
                    <strong>Agent 生成报告</strong>
                    <p>11 个 Agent 协作输出竞品分析</p>
                  </div>
                </div>
                <div className="feedback-step">
                  <span>2</span>
                  <div>
                    <strong>飞书推送报告卡片</strong>
                    <p>报告摘要+按钮推送到飞书群</p>
                  </div>
                </div>
                <div className="feedback-step">
                  <span>3</span>
                  <div>
                    <strong>团队成员反馈</strong>
                    <p>确认/纠正/补充，写入数据库</p>
                  </div>
                </div>
                <div className="feedback-step">
                  <span>4</span>
                  <div>
                    <strong>演化引擎更新</strong>
                    <p>置信度调整，Prompt 模板排序优化</p>
                  </div>
                </div>
              </div>
            </article>
          </section>

          <section className="panel">
            <div className="panel-heading">
              <div>
                <div className="panel-kicker">反馈历史</div>
                <h3>所有飞书反馈记录</h3>
              </div>
            </div>
            <div className="trace-table">
              <div className="trace-table-head">
                <span>报告ID</span><span>动作</span><span>说明</span><span>时间</span>
              </div>
              {records.map((item) => (
                <div className="trace-table-row" key={item.id}>
                  <span>{item.report_id}</span>
                  <span className={`action-badge ${item.action}`}>{item.action === 'confirm' ? '确认' : item.action === 'correct' ? '纠正' : item.action}</span>
                  <span>{item.comment || '-'}</span>
                  <small>{(item.created_at || '').slice(0, 19)}</small>
                </div>
              ))}
              {!records.length && <p className="empty-text">暂无反馈记录。</p>}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
