import { HighlightText } from './HighlightText.jsx';

function splitInline(text) {
  const parts = String(text || '').split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={index}><HighlightText text={part.slice(2, -2)} /></strong>;
    }
    return <HighlightText key={index} text={part} />;
  });
}

function isTableDivider(line) {
  return /^\s*\|?[\s:-]+\|[\s|:-]+\|?\s*$/.test(line);
}

function parseTable(lines, startIndex) {
  const rows = [];
  let i = startIndex;
  while (i < lines.length && lines[i].includes('|')) {
    if (!isTableDivider(lines[i])) {
      rows.push(lines[i].split('|').map((cell) => cell.trim()).filter(Boolean));
    }
    i += 1;
  }
  return { rows, nextIndex: i };
}

export function MarkdownText({ content = '', compact = false }) {
  const lines = String(content || '').split(/\r?\n/);
  const blocks = [];
  let i = 0;

  while (i < lines.length) {
    const raw = lines[i];
    const line = raw.trim();
    if (!line) {
      i += 1;
      continue;
    }

    if (line.includes('|') && i + 1 < lines.length && isTableDivider(lines[i + 1])) {
      const { rows, nextIndex } = parseTable(lines, i);
      blocks.push({ type: 'table', rows });
      i = nextIndex;
      continue;
    }

    if (line.startsWith('### ')) {
      blocks.push({ type: 'h3', text: line.slice(4) });
    } else if (line.startsWith('#### ')) {
      blocks.push({ type: 'h4', text: line.slice(5) });
    } else if (line.startsWith('- ')) {
      const items = [];
      while (i < lines.length && lines[i].trim().startsWith('- ')) {
        items.push(lines[i].trim().slice(2));
        i += 1;
      }
      blocks.push({ type: 'list', items });
      continue;
    } else if (line.startsWith('> ')) {
      blocks.push({ type: 'quote', text: line.slice(2) });
    } else {
      blocks.push({ type: 'p', text: line });
    }
    i += 1;
  }

  return (
    <div className={`markdown-text ${compact ? 'markdown-text--compact' : ''}`}>
      {blocks.map((block, index) => {
        if (block.type === 'h3') return <h3 key={index}>{splitInline(block.text)}</h3>;
        if (block.type === 'h4') return <h4 key={index}>{splitInline(block.text)}</h4>;
        if (block.type === 'quote') return <blockquote key={index}>{splitInline(block.text)}</blockquote>;
        if (block.type === 'list') {
          return (
            <ul key={index}>
              {block.items.map((item, itemIndex) => <li key={itemIndex}>{splitInline(item)}</li>)}
            </ul>
          );
        }
        if (block.type === 'table') {
          const [head = [], ...body] = block.rows;
          return (
            <div className="markdown-table-wrap" key={index}>
              <table>
                <thead>
                  <tr>{head.map((cell, cellIndex) => <th key={cellIndex}>{splitInline(cell)}</th>)}</tr>
                </thead>
                <tbody>
                  {body.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {row.map((cell, cellIndex) => <td key={cellIndex}>{splitInline(cell)}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        return <p key={index}>{splitInline(block.text)}</p>;
      })}
    </div>
  );
}
