const HIGHLIGHT_TERMS = [
  '微信',
  '订阅制',
  '透明定价',
  '大文件传输',
  '广告',
  '免费',
  'Windows',
  'Mac',
  '安卓',
  'Android',
  'Battlecard',
  'comparison_matrix',
  '事实一致性',
  '质量评分',
  '来源',
  '风险',
  '严重',
  '价格',
  '功能',
  '生态',
  '用户',
  '数据',
  '置信度',
  '高优先级',
  '竞品',
  '我方',
  '优势',
  '短板',
  '差异化',
  'Token',
  '通过',
  '打回',
];

const pattern = new RegExp(
  `(${HIGHLIGHT_TERMS.map((item) => item.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`,
  'gi',
);

export function HighlightText({ text }) {
  const value = String(text || '');
  if (!value) return null;
  return value.split(pattern).map((part, index) => {
    const matched = HIGHLIGHT_TERMS.some((term) => term.toLowerCase() === part.toLowerCase());
    return matched ? <mark className="report-keyword" key={`${part}-${index}`}>{part}</mark> : part;
  });
}
