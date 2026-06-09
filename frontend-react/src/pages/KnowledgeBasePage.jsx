import { useEffect, useState } from 'react';
import {
  BookOpen, Database, Search, Plus, X, Check, Edit3, Trash2, Loader2,
} from 'lucide-react';
import { api } from '../api/client.js';

function asArray(value) {
  if (Array.isArray(value)) return value;
  return value?.items || value?.records || [];
}

export function KnowledgeBasePage() {
  const [state, setState] = useState({
    competitors: [],
    records: [],
    product: null,
    rag: null,
    evolution: null,
  });
  const [query, setQuery] = useState('');
  const [queryResult, setQueryResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState('');

  // ★ CRUD 状态
  const [showAdd, setShowAdd] = useState(false);
  const [newName, setNewName] = useState('');
  const [newUrls, setNewUrls] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState('');
  const [editUrls, setEditUrls] = useState('');
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    setError('');
    const calls = await Promise.allSettled([
      api.competitors(),
      api.analysisRecords(),
      api.ourProduct(),
      api.ragStats(),
      api.evolutionStats(),
    ]);
    setState({
      competitors: calls[0].status === 'fulfilled' ? asArray(calls[0].value) : [],
      records: calls[1].status === 'fulfilled' ? asArray(calls[1].value) : [],
      product: calls[2].status === 'fulfilled' ? calls[2].value : null,
      rag: calls[3].status === 'fulfilled' ? calls[3].value : null,
      evolution: calls[4].status === 'fulfilled' ? calls[4].value : null,
    });
    const rejected = calls.find((item) => item.status === 'rejected');
    if (rejected) setError(rejected.reason?.message || '知识库接口暂时不可用');
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const searchKnowledge = async () => {
    if (!query.trim()) return;
    setError('');
    try {
      const payload = await api.ragQuery(query.trim(), 5);
      setQueryResult(payload);
    } catch (err) {
      setError(err.message || '检索失败');
    }
  };

  // ── CRUD 操作 ──
  const handleAdd = async () => {
    if (!newName.trim()) { setError('请输入竞品名称'); return; }
    setSaving(true); setError(''); setMsg('');
    try {
      const urlList = newUrls.split(/[\n,;；]+/).map((u) => u.trim()).filter(Boolean);
      await api.createCompetitor({ name: newName.trim(), urls: urlList });
      setMsg(`已添加竞品: ${newName.trim()}`);
      setNewName(''); setNewUrls(''); setShowAdd(false);
      await load();
    } catch (err) { setError(err.message || '添加失败'); }
    finally { setSaving(false); }
  };

  const handleEdit = (item) => {
    setEditingId(item.id);
    setEditName(item.name);
    setEditUrls((item.urls || []).join('\n'));
  };

  const handleSaveEdit = async (id) => {
    if (!editName.trim()) { setError('名称不能为空'); return; }
    setSaving(true); setError(''); setMsg('');
    try {
      const urlList = editUrls.split(/[\n,;；]+/).map((u) => u.trim()).filter(Boolean);
      await api.updateCompetitor(id, { name: editName.trim(), urls: urlList });
      setMsg(`已更新竞品: ${editName.trim()}`);
      setEditingId(null);
      await load();
    } catch (err) { setError(err.message || '更新失败'); }
    finally { setSaving(false); }
  };

  const handleDelete = async (item) => {
    if (!window.confirm(`确定删除竞品 "${item.name}" 吗？此操作不可撤销。`)) return;
    setSaving(true); setError(''); setMsg('');
    try {
      await api.deleteCompetitor(item.id);
      setMsg(`已删除竞品: ${item.name}`);
      await load();
    } catch (err) { setError(err.message || '删除失败'); }
    finally { setSaving(false); }
  };

  return (
    <div className="page-stack">
      {(error || msg) && (
        <div className={`notice ${error ? 'warn' : 'good'}`}>
          {error ? <X size={18} /> : <Check size={18} />}
          <span>{error || msg}</span>
        </div>
      )}

      <section className="metric-grid knowledge-metric-grid">
        <article className="metric-card info">
          <Database size={22} />
          <span>竞品数量</span>
          <strong>{state.competitors.length}</strong>
        </article>
        <article className="metric-card info">
          <BookOpen size={22} />
          <span>报告记录</span>
          <strong>{state.records.length}</strong>
        </article>
        <article className="metric-card info">
          <Database size={22} />
          <span>知识片段</span>
          <strong>{state.rag?.chunks || state.rag?.chunk_count || 0}</strong>
        </article>
        <article className="metric-card good">
          <BookOpen size={22} />
          <span>已验证快照</span>
          <strong>{state.evolution?.verified_snapshots || state.evolution?.verified_count || 0}</strong>
        </article>
      </section>

      <section className="split-grid">
        {/* ★ 竞品库 - 完整 CRUD */}
        <article className="panel">
          <div className="panel-heading">
            <div>
              <div className="panel-kicker">结构化对象</div>
              <h3>竞品库</h3>
            </div>
            <button className="primary-button small" type="button" onClick={() => { setShowAdd(true); setError(''); }}>
              <Plus size={16} /> 添加竞品
            </button>
          </div>

          {/* 添加表单 */}
          {showAdd && (
            <div className="crud-form">
              <label className="field">
                <span>竞品名称</span>
                <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="例如: 阿里巴巴" />
              </label>
              <label className="field">
                <span>监控URL（每行一个，或逗号分隔）</span>
                <textarea value={newUrls} onChange={(e) => setNewUrls(e.target.value)} placeholder="https://www.alibaba.com" rows={3} />
              </label>
              <div className="crud-actions">
                <button className="primary-button" type="button" onClick={handleAdd} disabled={saving}>
                  {saving ? <Loader2 className="spin" size={14} /> : <Check size={14} />} 保存
                </button>
                <button className="ghost-button" type="button" onClick={() => setShowAdd(false)}>
                  <X size={14} /> 取消
                </button>
              </div>
            </div>
          )}

          <div className="table-list">
            {state.competitors.map((item) => (
              <div className="table-row" key={item.id}>
                {editingId === item.id ? (
                  /* 编辑模式 */
                  <div className="crud-edit-row">
                    <input value={editName} onChange={(e) => setEditName(e.target.value)} style={{ flex: 1 }} />
                    <textarea value={editUrls} onChange={(e) => setEditUrls(e.target.value)} rows={2} style={{ flex: 2 }} />
                    <button className="primary-button small" type="button" onClick={() => handleSaveEdit(item.id)} disabled={saving}>
                      {saving ? <Loader2 className="spin" size={12} /> : <Check size={12} />}
                    </button>
                    <button className="ghost-button" type="button" onClick={() => setEditingId(null)}>
                      <X size={12} />
                    </button>
                  </div>
                ) : (
                  /* 展示模式 */
                  <>
                    <div style={{ flex: 1 }}>
                      <strong>{item.name}</strong>
                      <span style={{ display: 'block', fontSize: 12, color: 'var(--muted)' }}>
                        {Array.isArray(item.urls) ? `${item.urls.length} 个来源` : '无来源'}
                      </span>
                    </div>
                    <small style={{ fontSize: 11, color: 'var(--muted)' }}>
                      {(item.updated_at || item.created_at || '').slice(0, 10)}
                    </small>
                    <div className="crud-row-actions">
                      <button className="ghost-button" type="button" onClick={() => handleEdit(item)} title="编辑">
                        <Edit3 size={14} />
                      </button>
                      <button className="ghost-button danger" type="button" onClick={() => handleDelete(item)} title="删除">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </>
                )}
              </div>
            ))}
            {!state.competitors.length && <p className="empty-text">暂无竞品对象，点击「添加竞品」创建。</p>}
          </div>
        </article>

        <article className="panel">
          <div className="panel-heading">
            <div>
              <div className="panel-kicker">检索增强</div>
              <h3>知识库查询</h3>
            </div>
          </div>
          <div className="search-row">
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="输入竞品、功能或定价问题" />
            <button className="primary-button" type="button" onClick={searchKnowledge}>
              <Search size={18} />
              检索
            </button>
          </div>
          {queryResult ? (
            <pre className="json-block">{JSON.stringify(queryResult, null, 2)}</pre>
          ) : (
            <p className="empty-text">输入问题后会调用后端检索接口。</p>
          )}
        </article>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <div className="panel-kicker">我方产品</div>
            <h3>{state.product?.name || '尚未配置'}</h3>
          </div>
        </div>
        <div className="schema-grid">
          <div>
            <span>核心功能</span>
            <strong>{Array.isArray(state.product?.core_features) ? state.product.core_features.join('、') : '待补充'}</strong>
          </div>
          <div>
            <span>定价模式</span>
            <strong>{state.product?.pricing_model || '待补充'}</strong>
          </div>
          <div>
            <span>目标市场</span>
            <strong>{state.product?.target_market || '待补充'}</strong>
          </div>
          <div>
            <span>竞争优势</span>
            <strong>
              {Array.isArray(state.product?.competitive_advantages)
                ? state.product.competitive_advantages.join('、')
                : '待补充'}
            </strong>
          </div>
        </div>
      </section>
    </div>
  );
}
