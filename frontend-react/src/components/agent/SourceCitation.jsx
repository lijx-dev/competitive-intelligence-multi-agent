/**
 * SourceCitation — 来源溯源标签组件（类似 Perplexity 的来源小药丸）。
 */

function extractDomain(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

function isRealSourceUrl(url) {
  if (!url) return false;
  try {
    const parsed = new URL(url);
    if (!['http:', 'https:'].includes(parsed.protocol)) return false;
    return !parsed.hostname.replace(/^www\./, '').endsWith('example.com');
  } catch {
    return false;
  }
}

export function SourceCitation({ url, label, trust }) {
  if (!isRealSourceUrl(url)) return null;
  const domain = extractDomain(url);
  return (
    <a href={url} target="_blank" rel="noreferrer" className="source-cite" title={url}>
      <span className="source-cite-label">{label || '来源'}</span>
      <span className="source-cite-domain">{domain}</span>
      <span className="source-cite-arrow">{'\u2197'}</span>
      {trust != null && <span className="source-cite-trust">{Math.round(trust * 100)}%</span>}
    </a>
  );
}

export function SourceCitationList({ sources }) {
  if (!sources?.length) return null;
  const items = sources
    .map((s) => {
      const url = typeof s === 'string' ? s : s.url || s.source_url || s.link || s.href || '';
      return {
        url,
        label: typeof s === 'string' ? undefined : s.title || s.label || s.source || s.source_type,
        trust: typeof s === 'string' ? undefined : s.confidence || s.domain_score || s.reliability,
      };
    })
    .filter((item) => isRealSourceUrl(item.url));

  if (!items.length) return null;

  return (
    <div className="source-cite-list">
      {items.map((item, i) => (
        <SourceCitation key={`${item.url}-${i}`} url={item.url} label={item.label} trust={item.trust} />
      ))}
    </div>
  );
}
