// Keep original Unicode offsets so numeric badges still match the cited answer.
export function answerBlocks(raw: string) {
  type Item = {text: string; start: number};
  const blocks: {kind: 'p' | 'ul' | 'ol'; items: Item[]}[] = [];
  let offset = 0;
  let separated = true;
  for (const chunk of raw.split(/(?<=\n)/)) {
    const line = chunk.replace(/\r?\n$/, '');
    const prefix = line.match(/^\s*(?:[-+*]\s+|\d+[.)]\s+)/)?.[0] ?? '';
    const kind = prefix ? (/^\s*\d/.test(prefix) ? 'ol' : 'ul') : 'p';
    if (!line.trim()) separated = true;
    else {
      const item = {text: line.slice(prefix.length), start: offset + Array.from(prefix).length};
      const last = blocks[blocks.length - 1];
      if (last && !separated && last.kind === kind) last.items.push(item);
      else blocks.push({kind, items:[item]});
      separated = false;
    }
    offset += Array.from(chunk).length;
  }
  return blocks;
}
