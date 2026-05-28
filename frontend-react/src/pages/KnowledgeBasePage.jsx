import { useEffect, useState } from 'react';
import { BookOpen, Database, Search } from 'lucide-react';
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

  useEffect(() => {
    load();
  }, []);

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

  return (
    <div className="page-stack">
      {error && <div className="notice warn">{error}</div>}

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
        <article className="panel">
          <div className="panel-heading">
            <div>
              <div className="panel-kicker">结构化对象</div>
              <h3>竞品库</h3>
            </div>
          </div>
          <div className="table-list">
            {state.competitors.map((item) => (
              <div className="table-row" key={item.id}>
                <strong>{item.name}</strong>
                <span>{Array.isArray(item.urls) ? `${item.urls.length} 个来源` : '无来源'}</span>
                <small>{item.updated_at}</small>
              </div>
            ))}
            {!state.competitors.length && <p className="empty-text">暂无竞品对象。</p>}
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
