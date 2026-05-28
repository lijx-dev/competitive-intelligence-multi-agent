/**
 * AgentOutputCard — 按节点类型分发的结构化结果卡片。
 *
 * 取代 JSON.stringify，为每种 Agent 输出提供定制化可视化。
 */

import { SourceCitation, SourceCitationList } from './SourceCitation.jsx';
import { MarkdownText } from '../common/MarkdownText.jsx';
import { formatAgentOutputAsMarkdown } from '../../utils/agentMarkdown.js';

/* ─────────────── 辅助组件 ─────────────── */

function ScoreBar({ value, max = 10, color = 'var(--blue)' }) {
  const pct = Math.min(Math.max((value / max) * 100, 0), 100);
  return (
    <div className="score-bar">
      <div className="score-bar-fill" style={{ width: `${pct}%`, background: color }} />
    </div>
  );
}

function SeverityBadge({ severity }) {
  const level = (severity || '').toUpperCase();
  const cls = level === 'HIGH' ? 'severity-high' : level === 'MEDIUM' ? 'severity-medium' : 'severity-low';
  return <span className={`severity-badge ${cls}`}>{level || 'INFO'}</span>;
}

function sourceTypeLabel(type) {
  const labels = {
    url: '网页',
    document: '文档',
    survey: '问卷',
    interview: '访谈',
    agent_output: 'Agent',
  };
  return labels[type] || type || '来源';
}

function jumpToLocator(locator, sourceAgent) {
  if (!locator && !sourceAgent) return;
  const nodeId = String(locator || '').match(/^agent:\/\/([^/]+)/)?.[1] || sourceAgent || '';
  const el = nodeId ? document.querySelector(`[data-agent-output="${nodeId}"]`) : null;
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    el.classList.add('agent-output-flash');
    window.setTimeout(() => el.classList.remove('agent-output-flash'), 1200);
  }
}

function SourceLocatorChip({ source }) {
  if (!source) return null;
  if (source.url) return <SourceCitation url={source.url} label={source.label || sourceTypeLabel(source.source_type)} trust={source.reliability} />;
  return (
    <button
      className="source-locator-chip"
      type="button"
      title={source.locator}
      onClick={() => jumpToLocator(source.locator, source.source_agent)}
    >
      <span>{sourceTypeLabel(source.source_type)}</span>
      <strong>{source.label || source.locator}</strong>
    </button>
  );
}

/* ─────────────── 各节点卡片 ─────────────── */

function MonitorCard({ data }) {
  const changes = data.changes_detected || [];
  return (
    <div className="output-card">
      <div className="output-card-header">
        <h4>变化发现</h4>
        <span className="output-card-count">{changes.length} 条</span>
      </div>
      {changes.map((c, i) => (
        <div className="change-item" key={i}>
          <div className="change-item-head">
            <SeverityBadge severity={c.severity} />
            <strong>{c.title}</strong>
          </div>
          <p>{c.summary}</p>
          {c.source_url && <SourceCitation url={c.source_url} />}
        </div>
      ))}
      {changes.length === 0 && <p className="empty-text">未检测到竞品变化</p>}
    </div>
  );
}

function ResearchCard({ data }) {
  const results = data.research_results || [];
  return (
    <div className="output-card">
      <div className="output-card-header">
        <h4>研究发现</h4>
        <span className="output-card-count">{results.length} 个维度</span>
      </div>
      {results.map((r, i) => (
        <div className="research-item" key={i}>
          <div className="research-item-head">
            <strong>{r.topic}</strong>
            <span className="confidence-text">{((r.confidence || 0) * 100).toFixed(0)}%</span>
          </div>
          <ScoreBar value={(r.confidence || 0) * 10} color="var(--blue)" />
          <p>{r.summary}</p>
          {r.key_findings?.length > 0 && (
            <ul className="findings-list">
              {r.key_findings.map((f, j) => <li key={j}>{f}</li>)}
            </ul>
          )}
          <SourceCitationList sources={r.sources} />
        </div>
      ))}
    </div>
  );
}

function SurveyCard({ data }) {
  const sr = data.survey_results || data;
  const sat = sr.satisfaction_avg || 0;
  const pains = sr.top_pain_points || [];
  const findings = sr.key_findings || [];
  const personas = sr.personas || [];
  const interviews = sr.interviews || [];

  return (
    <div className="output-card">
      <div className="output-card-header">
        <h4>用户调研</h4>
        <span className="quality-badge-large" style={{ '--qb-color': sat >= 7 ? 'var(--green)' : sat >= 5 ? 'var(--orange)' : 'var(--red)' }}>
          {sat.toFixed(1)}
        </span>
      </div>

      {pains.length > 0 && (
        <div className="survey-section">
          <small className="section-label">TOP 痛点</small>
          <div className="tag-list">
            {pains.map((p, i) => <span className="tag tag--orange" key={i}>{p}</span>)}
          </div>
        </div>
      )}

      {findings.length > 0 && (
        <div className="survey-section">
          <small className="section-label">核心发现</small>
          <ul className="findings-list">
            {findings.map((f, i) => <li key={i}>{f}</li>)}
          </ul>
        </div>
      )}

      {personas.length > 0 && (
        <div className="survey-section">
          <small className="section-label">用户画像 ({personas.length})</small>
          <div className="persona-grid">
            {personas.map((p, i) => (
              <div className="persona-mini-card" key={i}>
                <div className="persona-head">
                  <strong>{p.label}</strong>
                  <span>{p.satisfaction_score}/10</span>
                </div>
                <small>{p.description}</small>
                {p.pain_points?.length > 0 && (
                  <div className="tag-list">
                    {p.pain_points.slice(0, 3).map((pt, j) => <span className="tag" key={j}>{pt}</span>)}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {interviews.length > 0 && (
        <div className="survey-section">
          <small className="section-label">访谈摘要 ({interviews.length})</small>
          {interviews.map((iv, i) => (
            <div className="interview-block" key={i}>
              <strong>{iv.persona}</strong>
              {iv.key_quotes?.map((q, j) => <blockquote className="interview-quote" key={j}>{q}</blockquote>)}
              {iv.insights?.map((ins, j) => <p className="interview-insight" key={j}>{ins}</p>)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function CompareCard({ data }) {
  const mx = data.comparison_matrix || data;
  const dims = mx.dimensions || [];

  return (
    <div className="output-card">
      <div className="output-card-header">
        <h4>对比分析</h4>
        <span className="output-card-count">{dims.length} 维度</span>
      </div>
      <table className="compare-table">
        <thead>
          <tr>
            <th>维度</th>
            <th>我方</th>
            <th>竞品</th>
            <th>分析</th>
          </tr>
        </thead>
        <tbody>
          {dims.map((d, i) => (
            <tr key={i}>
              <td><strong>{d.dimension}</strong></td>
              <td>
                <div className="score-cell">
                  <ScoreBar value={d.our_score} color="var(--blue)" />
                  <span>{d.our_score}</span>
                </div>
              </td>
              <td>
                <div className="score-cell">
                  <ScoreBar value={d.competitor_score} color="var(--muted)" />
                  <span>{d.competitor_score}</span>
                </div>
              </td>
              <td><small>{d.notes}</small></td>
            </tr>
          ))}
        </tbody>
      </table>
      {mx.overall_assessment && (
        <div className="compare-summary">
          <small className="section-label">综合评估</small>
          <p>{mx.overall_assessment}</p>
        </div>
      )}
    </div>
  );
}

function BattlecardCard({ data }) {
  const bc = data.battlecard || data;
  return (
    <div className="output-card">
      <div className="output-card-header">
        <h4>对战卡</h4>
      </div>
      <div className="battlecard-columns">
        <div>
          <small className="section-label" style={{ color: 'var(--green)' }}>我方优势</small>
          <ul className="bc-list bc-list--green">
            {(bc.our_strengths || []).map((s, i) => <li key={i}>{s}</li>)}
          </ul>
          <small className="section-label" style={{ color: 'var(--orange)' }}>我方不足</small>
          <ul className="bc-list bc-list--orange">
            {(bc.our_weaknesses || []).map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        </div>
        <div>
          <small className="section-label">竞品优势</small>
          <ul className="bc-list">
            {(bc.competitor_strengths || []).map((s, i) => <li key={i}>{s}</li>)}
          </ul>
          <small className="section-label">竞品不足</small>
          <ul className="bc-list bc-list--green">
            {(bc.competitor_weaknesses || []).map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        </div>
        <div>
          <small className="section-label" style={{ color: 'var(--purple)' }}>核心差异化</small>
          <ul className="bc-list bc-list--purple">
            {(bc.key_differentiators || []).map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        </div>
      </div>

      {bc.objection_handling && Object.keys(bc.objection_handling).length > 0 && (
        <div className="survey-section">
          <small className="section-label">异议处理</small>
          {Object.entries(bc.objection_handling).map(([q, a], i) => (
            <details className="objection-card" key={i}>
              <summary>{q}</summary>
              <p>{a}</p>
            </details>
          ))}
        </div>
      )}

      {bc.elevator_pitch && (
        <div className="elevator-pitch">
          <small className="section-label">电梯演讲</small>
          <p>{bc.elevator_pitch}</p>
        </div>
      )}
    </div>
  );
}

function ReviewerCard({ data }) {
  const rf = data.review_feedback || data;
  const score = rf.overall_score || data.quality_score || 0;
  const pass = rf.approved !== false && score >= 7;
  const subScores = [
    { label: '准确性', value: rf.accuracy_score },
    { label: '完整性', value: rf.completeness_score },
    { label: '引用度', value: rf.citation_score },
    { label: '可操作性', value: rf.actionability_score },
  ].filter((s) => s.value != null);

  return (
    <div className="output-card">
      <div className="output-card-header">
        <h4>质量报告</h4>
        <span className={`quality-pill ${pass ? 'quality-pill--pass' : 'quality-pill--fail'}`}>
          {pass ? '通过' : '打回'}
        </span>
      </div>
      <div className="reviewer-score-block">
        <span className="quality-badge-large" style={{ '--qb-color': score >= 7 ? 'var(--green)' : score >= 5 ? 'var(--orange)' : 'var(--red)' }}>
          {score.toFixed(1)}
        </span>
        <div className="sub-scores">
          {subScores.map((s, i) => (
            <div className="sub-score-row" key={i}>
              <small>{s.label}</small>
              <ScoreBar value={s.value} color={s.value >= 7 ? 'var(--green)' : s.value >= 5 ? 'var(--orange)' : 'var(--red)'} />
              <span>{s.value}</span>
            </div>
          ))}
        </div>
      </div>
      {rf.revision_instructions && (
        <div className="reviewer-instructions">
          <small className="section-label">审查意见</small>
          <p>{rf.revision_instructions}</p>
        </div>
      )}
      {rf.issues?.length > 0 && (
        <div className="reviewer-issues">
          <small className="section-label">待修复问题</small>
          <ul>{rf.issues.map((issue, i) => <li key={i}>{typeof issue === 'string' ? issue : issue.description || JSON.stringify(issue)}</li>)}</ul>
        </div>
      )}
    </div>
  );
}

function CitationCard({ data }) {
  const cr = data.citation_report || data;
  const dist = cr.reliability_distribution || {};
  const details = cr.source_details || (cr.source_list || []).map((item) => ({
    label: item,
    url: String(item).startsWith('http') ? item : '',
    locator: item,
    source_type: String(item).startsWith('http') ? 'url' : 'agent_output',
  }));
  const total = cr.total_sources || 0;
  const coverage = cr.evidence_coverage != null ? cr.evidence_coverage : (total ? (cr.verified_sources || 0) / total : 0);
  const typeRows = Object.entries(cr.source_type_counts || {});
  const distRows = Object.entries(dist);

  return (
    <div className="output-card">
      <div className="output-card-header">
        <h4>来源验证</h4>
        <span className="output-card-count">{total} 个来源</span>
      </div>
      <div className="citation-metrics">
        <div className="citation-metric">
          <span className="citation-metric-value">{cr.verified_sources || 0}</span>
          <small>已验证</small>
        </div>
        <div className="citation-metric">
          <span className="citation-metric-value">{cr.broken_links || 0}</span>
          <small>失效链接</small>
        </div>
        <div className="citation-metric">
          <span className="citation-metric-value">{((cr.overall_reliability_score || 0) * 100).toFixed(0)}%</span>
          <small>可信度</small>
        </div>
        <div className="citation-metric">
          <span className="citation-metric-value">{(coverage * 100).toFixed(0)}%</span>
          <small>覆盖率</small>
        </div>
      </div>
      {distRows.length ? (
        <div className="citation-dist">
          <small className="section-label">可信度分布</small>
          <div className="citation-dist-bar">
            {distRows.map(([bucket, count]) => (
              <div className={`dist-seg dist-seg--${bucket}`} style={{ flex: count }} key={bucket}>
                {count} {bucket === 'high' ? '高' : bucket === 'medium' ? '中' : bucket === 'low' ? '低' : bucket}
              </div>
            ))}
          </div>
        </div>
      ) : null}
      {typeRows.length > 0 && (
        <div className="source-type-counts">
          {typeRows.map(([type, count]) => (
            <span key={type}>{sourceTypeLabel(type)} {count}</span>
          ))}
        </div>
      )}
      {details.length > 0 && (
        <div className="source-detail-list">
          {details.slice(0, 12).map((item, index) => (
            <SourceLocatorChip source={item} key={item.id || item.locator || item.url || index} />
          ))}
        </div>
      )}
    </div>
  );
}

function FactCheckCard({ data }) {
  const fc = data.fact_check_result || data;
  const rows = fc.cross_verified || [];
  const v = fc.verified_count ?? rows.filter((item) => item.status === 'verified').length;
  const partial = fc.partially_verified_count ?? rows.filter((item) => item.status === 'partially_verified').length;
  const unverified = fc.unverified_count ?? rows.filter((item) => item.status === 'unverified').length;
  const total = v + partial + unverified;
  const conf = ((fc.overall_confidence ?? fc.coverage_rate) || 0) * 100;
  const statusText = fc.status === 'verified' ? '全部通过' : fc.status || '待验证';

  return (
    <div className="output-card">
      <div className="output-card-header">
        <h4>交叉验证</h4>
        <span className={`quality-pill ${fc.status === 'verified' ? 'quality-pill--pass' : 'quality-pill--warn'}`}>
          {statusText}
        </span>
      </div>
      <div className="factcheck-metrics">
        <div className="citation-metric">
          <span className="citation-metric-value">{v}/{total}</span>
          <small>验证通过</small>
        </div>
        <div className="citation-metric">
          <span className="citation-metric-value">{partial}</span>
          <small>部分验证</small>
        </div>
        <div className="citation-metric">
          <span className="citation-metric-value">{conf.toFixed(0)}%</span>
          <small>整体置信度</small>
        </div>
      </div>
      <ScoreBar value={conf / 10} color={conf >= 80 ? 'var(--green)' : conf >= 50 ? 'var(--orange)' : 'var(--red)'} />
      {(fc.verification_summary || fc.summary) && <p className="factcheck-summary">{fc.verification_summary || fc.summary}</p>}
      {rows.length > 0 && (
        <div className="factcheck-list">
          {rows.slice(0, 8).map((item, index) => (
            <div className="factcheck-row" key={`${item.source_agent}-${index}`}>
              <strong>{item.source_agent}</strong>
              <span>{item.status}</span>
              <p>{item.claim}</p>
              {(item.supporting_evidence || []).slice(0, 3).map((evidence, i) => (
                <button className="source-locator-chip mini" type="button" key={i} onClick={() => jumpToLocator(evidence, item.source_agent)}>
                  <span>证据</span>
                  <strong>{evidence}</strong>
                </button>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function GenericCard({ nodeId, data }) {
  return (
    <div className="output-card">
      <div className="output-card-header">
        <h4>{nodeId}</h4>
      </div>
      <div className="markdown-result-card">
        <MarkdownText content={formatAgentOutputAsMarkdown(nodeId, data)} />
      </div>
    </div>
  );
}

/* ─────────────── 分发入口 ─────────────── */

export function AgentOutputCard({ nodeId, data }) {
  let content;
  switch (nodeId) {
    case 'monitor':      content = <MonitorCard data={data} />; break;
    case 'research':     content = <ResearchCard data={data} />; break;
    case 'survey':       content = <SurveyCard data={data} />; break;
    case 'fact_check':   content = <FactCheckCard data={data} />; break;
    case 'compare':      content = <CompareCard data={data} />; break;
    case 'battlecard':   content = <BattlecardCard data={data} />; break;
    case 'reviewer':     content = <ReviewerCard data={data} />; break;
    case 'citation':     content = <CitationCard data={data} />; break;
    default:             content = <GenericCard nodeId={nodeId} data={data} />;
  }
  return <div data-agent-output={nodeId}>{content}</div>;
}
