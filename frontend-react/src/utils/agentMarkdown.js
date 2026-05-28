function listOf(value) {
  return Array.isArray(value) ? value.filter(Boolean) : [];
}

function num(value) {
  return Number.isFinite(Number(value)) ? Number(value) : 0;
}

function lines(items, mapper = (item) => item, limit = 6) {
  return listOf(items).slice(0, limit).map((item) => `- ${mapper(item)}`);
}

function stringify(value) {
  if (value == null || value === '') return '-';
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.map(stringify).join('、');
  if (typeof value === 'object') return Object.entries(value).map(([key, item]) => `${key}: ${stringify(item)}`).join('；');
  return String(value);
}

function genericMarkdown(nodeId, data) {
  const body = Object.entries(data || {})
    .filter(([key]) => !key.startsWith('_'))
    .map(([key, value]) => {
      if (Array.isArray(value)) {
        return `#### ${key}\n${lines(value, stringify, 8).join('\n') || '- 暂无内容'}`;
      }
      if (value && typeof value === 'object') {
        return `#### ${key}\n${Object.entries(value).map(([k, v]) => `- **${k}**：${stringify(v)}`).join('\n')}`;
      }
      return `- **${key}**：${stringify(value)}`;
    })
    .join('\n\n');
  return `### ${nodeId} 输出\n${body || '- 暂无结构化输出'}`;
}

export function formatAgentOutputAsMarkdown(nodeId, data = {}) {
  if (!data || typeof data !== 'object') return `### ${nodeId}\n${stringify(data)}`;
  if (data.error) return `### 执行失败\n- **节点**：${nodeId}\n- **原因**：${data.error}`;

  switch (nodeId) {
    case 'monitor': {
      const changes = listOf(data.changes_detected);
      return [
        '### 监控采集结果',
        `发现 **${changes.length}** 条竞品动态。`,
        ...lines(changes, (item) => `**${item.title || '未命名动态'}**：${item.summary || '-'}${item.severity ? `（${item.severity}）` : ''}`, 6),
      ].join('\n');
    }
    case 'alert': {
      const alerts = listOf(data.alerts_sent);
      return [
        '### 变更告警结果',
        alerts.length ? `生成 **${alerts.length}** 条告警。` : '没有达到告警阈值的变更。',
        ...lines(alerts, (item) => `**${item.title || item.severity || '告警'}**：${item.message || item.summary || stringify(item)}`, 5),
      ].join('\n');
    }
    case 'research': {
      const results = listOf(data.research_results);
      const blocks = results.slice(0, 5).map((item) => [
        `#### ${item.topic || '研究主题'}`,
        item.summary || '暂无摘要。',
        ...lines(item.key_findings, (finding) => finding, 4),
      ].join('\n'));
      return ['### 深度研究结果', `完成 **${results.length}** 个研究维度。`, ...blocks].join('\n\n');
    }
    case 'survey': {
      const sr = data.survey_results || data;
      const personas = listOf(sr.personas);
      const personaLines = personas.slice(0, 5).map((p) => {
        const pains = listOf(p.pain_points).slice(0, 3).join('、') || '暂无痛点';
        return `- **${p.label || p.persona_id || '用户画像'}**：满意度 ${num(p.satisfaction_score).toFixed(1)}/10，痛点：${pains}`;
      });
      return [
        '### 用户调研结果',
        `平均满意度 **${num(sr.satisfaction_avg).toFixed(1)}/10**。`,
        '#### 核心发现',
        ...(lines(sr.key_findings, (item) => item, 6).length ? lines(sr.key_findings, (item) => item, 6) : ['- 暂无核心发现']),
        '#### TOP 痛点',
        ...(lines(sr.top_pain_points, (item) => item, 5).length ? lines(sr.top_pain_points, (item) => item, 5) : ['- 暂无痛点']),
        '#### 用户画像',
        ...(personaLines.length ? personaLines : ['- 暂无用户画像']),
      ].join('\n');
    }
    case 'fact_check': {
      const fc = data.fact_check_result || data;
      const verified = num(fc.verified_count);
      const total = verified + num(fc.unverified_count);
      return [
        '### 交叉验证结果',
        `- **验证通过**：${verified}/${total || verified}`,
        `- **整体置信度**：${(num(fc.overall_confidence) * 100).toFixed(0)}%`,
        fc.verification_summary ? `- **摘要**：${fc.verification_summary}` : '- 暂无验证摘要',
      ].join('\n');
    }
    case 'compare': {
      const mx = data.comparison_matrix || data;
      const dims = listOf(mx.dimensions);
      const table = [
        '| 维度 | 我方 | 竞品 | 判断 |',
        '| --- | ---: | ---: | --- |',
        ...dims.slice(0, 8).map((d) => `| ${d.dimension || '-'} | ${num(d.our_score).toFixed(1)} | ${num(d.competitor_score).toFixed(1)} | ${d.notes || '-'} |`),
      ];
      return ['### 对比分析结果', ...table, mx.overall_assessment ? `\n#### 综合评估\n${mx.overall_assessment}` : ''].join('\n');
    }
    case 'battlecard': {
      const bc = data.battlecard || data;
      return [
        '### 对战卡结果',
        '#### 我方优势',
        ...(lines(bc.our_strengths, (item) => item, 5).length ? lines(bc.our_strengths, (item) => item, 5) : ['- 暂无']),
        '#### 核心差异化',
        ...(lines(bc.key_differentiators, (item) => item, 5).length ? lines(bc.key_differentiators, (item) => item, 5) : ['- 暂无']),
        bc.elevator_pitch ? `#### 电梯演讲\n${bc.elevator_pitch}` : '',
      ].join('\n');
    }
    case 'reviewer': {
      const rf = data.review_feedback || data;
      const score = num(rf.overall_score || data.quality_score);
      return [
        '### 质量审查结果',
        `- **总分**：${score.toFixed(1)}/10`,
        `- **结论**：${rf.approved !== false && score >= 7 ? '通过审查' : '需要定向修复'}`,
        rf.revision_instructions ? `- **审查意见**：${rf.revision_instructions}` : '',
        ...lines(rf.issues, (issue) => issue.description || stringify(issue), 5),
      ].filter(Boolean).join('\n');
    }
    case 'citation': {
      const cr = data.citation_report || data;
      return [
        '### 来源溯源结果',
        `- **来源总数**：${num(cr.total_sources)}`,
        `- **已验证来源**：${num(cr.verified_sources)}`,
        `- **失效链接**：${num(cr.broken_links)}`,
        `- **整体可信度**：${(num(cr.overall_reliability_score) * 100).toFixed(0)}%`,
        ...lines(cr.missing_citations, (item) => `缺失引用：${item}`, 5),
      ].join('\n');
    }
    case 'feishu_push':
      return `### 飞书推送结果\n- **状态**：${data.feishu_push_status || '已执行'}`;
    default:
      return genericMarkdown(nodeId, data);
  }
}
